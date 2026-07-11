#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
串口 EEG → LSL 网络流中继

同学运行此脚本: 读取串口 EEG 数据 → 发布为 LSL 流
你用平台连接该 LSL 流 (支持跨网络)

用法:
  python serial_to_lsl.py --port COM3 --baud 115200
  python serial_to_lsl.py --port /dev/tty.usbserial --baud 115200 --srate 250

依赖: pip install pyserial pylsl numpy
"""

import argparse
import json
import os
import struct
import sys
import time
import logging
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("serial2lsl")

CONFIG_PATH = os.path.expanduser("~/.metabci_serial_config.json")


def load_frame_config():
    """加载帧格式配置 (和平台共用)"""
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH) as f:
        return json.load(f)


def make_lsl_outlet(n_channels: int, srate: float):
    """创建 LSL 流出口"""
    from pylsl import StreamInfo, StreamOutlet
    info = StreamInfo(
        "MetaBCI-EEG-Relay", "EEG", n_channels, srate,
        "float32", "metabci_relay_001"
    )
    return StreamOutlet(info)


def parse_frame(buf: bytes, fields: list) -> list[float] | None:
    """解析一帧数据 (与 serial_worker.py 一致的解析逻辑)"""
    offset = 0
    values = []
    for f in fields:
        bc = f.get("byte_count", 1)
        if offset + bc > len(buf):
            return None
        raw_bytes = buf[offset:offset + bc]
        offset += bc
        if f.get("is_length") or f.get("field_type") in ("帧头", "帧尾", "校验"):
            continue
        if not f.get("show_panel", True):
            continue
        is_signed = not f.get("convert_type", "Hex").startswith("UInt")
        byte_order = "big" if f.get("big_endian") else "little"
        if f.get("convert_type") in ("Float", "Double"):
            fmt = ">f" if f.get("big_endian") else "<f"
            val = struct.unpack(fmt, raw_bytes[:4])[0] if len(raw_bytes) >= 4 else 0.0
        else:
            val = int.from_bytes(raw_bytes, byte_order, signed=is_signed)
        values.append(float(val))
    return values if values else None


def main():
    parser = argparse.ArgumentParser(description="串口 EEG → LSL 网络流中继")
    parser.add_argument("--port", required=True, help="串口设备路径 (COM3, /dev/ttyUSB0, ...)")
    parser.add_argument("--baud", type=int, default=115200, help="波特率")
    parser.add_argument("--srate", type=float, default=250.0, help="采样率")
    parser.add_argument("--config", default=None, help="帧格式配置文件 (默认 ~/.metabci_serial_config.json)")
    args = parser.parse_args()

    # 加载帧格式
    config_path = args.config or CONFIG_PATH
    cfg = load_frame_config() if config_path == CONFIG_PATH else None
    if config_path != CONFIG_PATH and os.path.exists(config_path):
        with open(config_path) as f:
            cfg = json.load(f)

    frame_fields = cfg.get("frame_fields", []) if cfg else []
    data_fields = [f for f in frame_fields
                   if f.get("show_panel") and f.get("field_type") not in ("帧头", "帧尾", "校验")]
    n_channels = len(data_fields)
    field_names = [f.get("name", f"Ch{i}") for i, f in enumerate(data_fields)]

    if n_channels == 0:
        logger.error("未找到数据字段！请先配置帧格式 (设置→帧格式)")
        logger.error(f"配置文件: {config_path}")
        sys.exit(1)

    logger.info(f"通道: {field_names} ({n_channels}ch)")
    logger.info(f"采样率: {args.srate} Hz")

    # 创建 LSL 流
    try:
        outlet = make_lsl_outlet(n_channels, args.srate)
        logger.info("LSL 流已创建: MetaBCI-EEG-Relay")
    except ImportError:
        logger.error("pylsl 未安装: pip install pylsl")
        sys.exit(1)

    # 打开串口
    try:
        import serial
        ser = serial.Serial(port=args.port, baudrate=args.baud,
                            bytesize=8, parity="N", stopbits=1, timeout=0.01)
        logger.info(f"串口已打开: {args.port} @ {args.baud}")
    except ImportError:
        logger.error("pyserial 未安装: pip install pyserial")
        sys.exit(1)
    except Exception as e:
        logger.error(f"串口打开失败: {e}")
        sys.exit(1)

    # 查找帧头和帧尾
    header_hex = "AA"
    tail_hex = "55"
    for f in frame_fields:
        if f.get("field_type") == "帧头":
            header_hex = f.get("value", "AA").replace(" ", "")
        elif f.get("field_type") == "帧尾":
            tail_hex = f.get("value", "55").replace(" ", "")

    header_bytes = bytes.fromhex(header_hex)
    tail_bytes = bytes.fromhex(tail_hex)
    frame_len = sum(f.get("byte_count", 1) for f in frame_fields)

    logger.info(f"帧长度: {frame_len} bytes, 帧头: {header_hex}, 帧尾: {tail_hex}")
    logger.info("正在中继数据... Ctrl+C 停止")

    buf = b""
    sample_count = 0
    start_time = time.time()
    samples = []  # 批量发送缓冲

    try:
        while True:
            n = ser.in_waiting
            raw = ser.read(n if n > 0 else frame_len * 2)
            if not raw:
                continue

            if frame_fields:
                buf += raw
                while len(buf) >= len(header_bytes):
                    idx = buf.find(header_bytes)
                    if idx < 0:
                        break
                    buf = buf[idx:]
                    if len(buf) < frame_len:
                        break
                    # 帧尾校验
                    if buf[frame_len - len(tail_bytes):frame_len] != tail_bytes:
                        buf = buf[1:]
                        continue
                    data = parse_frame(buf[:frame_len], frame_fields)
                    if data:
                        samples.append(data[:n_channels])
                        sample_count += 1
                    buf = buf[frame_len:]
            else:
                # 无帧格式: 按单字节处理
                for b in raw:
                    if b == 0x0A:
                        continue
                    vals = [float(b)]
                    while len(vals) < n_channels:
                        vals.append(0.0)
                    samples.append(vals[:n_channels])
                    sample_count += 1

            # 批量推送 LSL (每 0.1s 或积累 25 个样本)
            if len(samples) >= 25:
                chunk = np.array(samples, dtype=np.float32).T  # (n_channels, n_samples)
                outlet.push_chunk(chunk.tolist())
                samples = []

            # 每秒打印统计
            elapsed = time.time() - start_time
            if elapsed >= 1.0:
                sps = sample_count / elapsed
                logger.info(f"中继: {sample_count} 样本, {sps:.0f} SPS, "
                            f"LSL 通道: {field_names}")
                start_time = time.time()
                sample_count = 0

    except KeyboardInterrupt:
        logger.info("中继已停止")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
