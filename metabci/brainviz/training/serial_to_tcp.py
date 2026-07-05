#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
串口 EEG → TCP 直连中继 (Windows → Mac)

同学 (Windows) 运行此脚本:
  - 读取串口 EEG 数据
  - 帧解析
  - 通过 TCP 发送到你的 Mac

用法:
  python serial_to_tcp.py --port COM3 --baud 115200 --host 0.0.0.0 --tcp-port 9877

你 (Mac) 在线实验室选择 TCP 模式，输入同学的 IP:172.21.19.89:9877

依赖: pip install pyserial numpy
"""

import argparse
import json
import os
import socket
import struct
import sys
import time
import logging
import threading
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("serial2tcp")

CONFIG_PATH = os.path.expanduser("~/.metabci_serial_config.json")


def load_frame_config(config_path=None):
    path = config_path or CONFIG_PATH
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def parse_frame(buf: bytes, fields: list) -> list[float] | None:
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
    parser = argparse.ArgumentParser(description="串口 EEG → TCP 直连中继 (Windows → Mac)")
    parser.add_argument("--port", required=True, help="串口设备 (COM3, /dev/ttyUSB0, ...)")
    parser.add_argument("--baud", type=int, default=115200, help="波特率")
    parser.add_argument("--host", default="0.0.0.0", help="TCP 监听地址")
    parser.add_argument("--tcp-port", type=int, default=9877, help="TCP 端口")
    parser.add_argument("--config", default=None, help="帧格式配置文件")
    parser.add_argument("--batch", type=int, default=10, help="每批发送样本数")
    args = parser.parse_args()

    # 加载帧格式
    cfg = load_frame_config(args.config)
    frame_fields = cfg.get("frame_fields", []) if cfg else []
    data_fields = [f for f in frame_fields
                   if f.get("show_panel") and f.get("field_type") not in ("帧头", "帧尾", "校验")]
    n_channels = len(data_fields)
    field_names = [f.get("name", f"Ch{i}") for i, f in enumerate(data_fields)]

    if n_channels == 0:
        # 默认 3 通道
        n_channels = 3
        field_names = ["CH2", "CH1", "ECG"]
        frame_fields = [
            {"field_type": "帧头", "value": "AA", "byte_count": 1, "show_panel": False},
            {"field_type": "4Byte", "name": "CH2", "convert_type": "Int32", "show_panel": True, "big_endian": False, "byte_count": 4},
            {"field_type": "4Byte", "name": "CH1", "convert_type": "Int32", "show_panel": True, "big_endian": False, "byte_count": 4},
            {"field_type": "4Byte", "name": "ECG", "convert_type": "Int32", "show_panel": True, "big_endian": False, "byte_count": 4},
            {"field_type": "帧尾", "value": "55", "byte_count": 1, "show_panel": False},
        ]
        logger.info("使用默认帧格式: 帧头AA + CH2 CH1 ECG 4Byte Int32 + 帧尾55")

    logger.info(f"通道: {field_names} ({n_channels}ch)")

    # 打开串口
    try:
        import serial
        ser = serial.Serial(port=args.port, baudrate=args.baud,
                            bytesize=8, parity="N", stopbits=1, timeout=0.005)
        logger.info(f"串口已打开: {args.port} @ {args.baud}")
    except Exception as e:
        logger.error(f"串口失败: {e}")
        sys.exit(1)

    # 帧头尾
    header_hex = "AA"; tail_hex = "55"
    for f in frame_fields:
        if f.get("field_type") == "帧头": header_hex = f.get("value", "AA").replace(" ", "")
        elif f.get("field_type") == "帧尾": tail_hex = f.get("value", "55").replace(" ", "")
    header_bytes = bytes.fromhex(header_hex)
    tail_bytes = bytes.fromhex(tail_hex)
    frame_len = sum(f.get("byte_count", 1) for f in frame_fields)

    # TCP 服务器
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host, args.tcp_port))
    server.listen(1)
    logger.info(f"TCP 服务器: {args.host}:{args.tcp_port}  (等待 Mac 连接...)")

    # 等待客户端
    client, addr = server.accept()
    logger.info(f"Mac 已连接: {addr}")
    client.settimeout(5.0)
    # 发送通道信息
    info = json.dumps({"n_channels": n_channels, "srate": 250.0, "names": field_names})
    client.send((info + "\n").encode())

    buf = b""
    sample_count = 0
    start_time = time.time()
    batch = []

    try:
        while True:
            n = ser.in_waiting
            raw = ser.read(n if n > 0 else frame_len * 4)
            if not raw:
                continue

            buf += raw
            while len(buf) >= len(header_bytes):
                idx = buf.find(header_bytes)
                if idx < 0:
                    break
                buf = buf[idx:]
                if len(buf) < frame_len:
                    break
                if buf[frame_len - len(tail_bytes):frame_len] != tail_bytes:
                    buf = buf[1:]
                    continue
                data = parse_frame(buf[:frame_len], frame_fields)
                if data:
                    batch.append(data[:n_channels])
                    sample_count += 1
                buf = buf[frame_len:]

            # 批量发送 (JSON 数组，每行)
            if len(batch) >= args.batch:
                msg = json.dumps(batch) + "\n"
                try:
                    client.send(msg.encode())
                except (BrokenPipeError, ConnectionResetError):
                    logger.info("Mac 断开，等待重连...")
                    client.close()
                    client, addr = server.accept()
                    logger.info(f"重连: {addr}")
                    info = json.dumps({"n_channels": n_channels, "srate": 250.0, "names": field_names})
                    client.send((info + "\n").encode())
                batch = []

            # 每秒统计
            elapsed = time.time() - start_time
            if elapsed >= 1.0:
                sps = sample_count / elapsed
                logger.info(f"中继: {sample_count} 样本, {sps:.0f} SPS → {addr}")
                start_time = time.time()
                sample_count = 0

    except KeyboardInterrupt:
        logger.info("中继已停止")
    finally:
        client.close()
        server.close()
        ser.close()


if __name__ == "__main__":
    main()
