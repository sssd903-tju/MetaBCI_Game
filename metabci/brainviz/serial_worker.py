# -*- coding: utf-8 -*-
"""
串口数据采集线程 — HEX行/帧格式双模式
"""

import logging, time, json, os
from threading import Thread
import numpy as np

logger = logging.getLogger("brainviz.serial")


class SerialReader(Thread):
    def __init__(self, port: str, baudrate: int, buffer,
                 n_channels: int = 8, srate: float = 250.0,
                 frame_fields: list | None = None):
        super().__init__(daemon=True)
        self.port = port; self.baudrate = baudrate
        self._buffer = buffer; self.n_channels = n_channels
        self.srate = srate
        self._frame_fields = frame_fields or []
        self.running = False; self._ser = None
        self.rx_callback = None

    def run(self):
        try:
            import serial
            self._ser = serial.Serial(port=self.port, baudrate=self.baudrate,
                                      bytesize=8, parity='N', stopbits=1, timeout=0.3)
            logger.info(f"串口已打开: {self.port} @ {self.baudrate}")
        except Exception as e:
            logger.error(f"串口打开失败: {e}"); return

        self.running = True; buf = b''; sample_count = 0
        self._hex_buf = ''  # HEX 文本行缓冲

        while self.running:
            try:
                raw = self._ser.read(self._ser.in_waiting or 1)
                if not raw: continue

                # HEX 显示回调
                if self.rx_callback:
                    hex_str = ' '.join(f'{b:02X}' for b in raw)
                    self.rx_callback(hex_str, True)

                # 尝试帧解析
                if self._frame_fields:
                    buf += raw
                    # 寻找帧头
                    header_hex = self._get_header_hex()
                    header_bytes = bytes.fromhex(header_hex.replace(' ', ''))
                    while len(buf) > len(header_bytes):
                        idx = buf.find(header_bytes)
                        if idx < 0: break
                        buf = buf[idx:]
                        frame_data = self._parse_frame(buf)
                        if frame_data:
                            sample_count += 1
                            self._buffer.push([frame_data], None)
                            buf = buf[len(header_bytes) + sum(
                                f.byte_count for f in self._frame_fields):]
                        else:
                            buf = buf[1:]  # 解析失败，跳过一个字节
                else:
                    # 无帧格式 → 简单 HEX 行解析
                    for b in raw:
                        ch = chr(b)
                        if ch == '\n':
                            if self._hex_buf.strip():
                                hex_parts = self._hex_buf.strip().split()
                                vals = []
                                for h in hex_parts:
                                    try: vals.append(float(int(h, 16)))
                                    except ValueError: pass
                                if vals:
                                    while len(vals) < self.n_channels: vals.append(0.0)
                                    sample_count += 1
                                    self._buffer.push([vals[:self.n_channels]], None)
                            self._hex_buf = ''
                        else:
                            self._hex_buf += ch

            except Exception as e:
                logger.error(f"串口读取错误: {e}"); break

        if self._ser: self._ser.close()
        logger.info(f"串口关闭, 采集 {sample_count} 样本")

    def _get_header_hex(self) -> str:
        for f in self._frame_fields:
            if f.field_type == '帧头':
                return f.value.replace(' ', '')
        return 'AA'

    def _parse_frame(self, buf: bytes) -> list[float] | None:
        """解析一帧数据，返回通道数值列表"""
        fields = self._frame_fields
        if not fields: return None
        try:
            offset = 0
            values = []
            for f in fields:
                bc = f.byte_count
                if offset + bc > len(buf): return None
                raw_bytes = buf[offset:offset + bc]
                offset += bc
                if f.is_length or f.field_type in ('帧头', '帧尾'):
                    continue  # 跳过头尾和长度字段
                if f.field_type == '校验': continue
                # 解析数值
                val = 0
                if f.big_endian:
                    val = int.from_bytes(raw_bytes, 'big')
                else:
                    val = int.from_bytes(raw_bytes, 'little')
                # 根据转换类型处理
                if f.convert_type in ('Float', 'Double'):
                    import struct
                    fmt = '>f' if f.big_endian else '<f'
                    if len(raw_bytes) >= 4:
                        val = struct.unpack(fmt, raw_bytes[:4])[0]
                if f.show_panel:
                    values.append(float(val))
            return values if values else None
        except Exception:
            return None

    def stop(self):
        self.running = False
