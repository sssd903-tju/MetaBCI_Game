# -*- coding: utf-8 -*-
"""串口数据采集线程 — HEX/帧格式双模式"""

import logging, time
from threading import Thread
import numpy as np

logger = logging.getLogger("brainviz.serial")


class SerialReader(Thread):
    def __init__(self, port, baudrate, buffer, n_channels=8, srate=250.0, frame_fields=None):
        super().__init__(daemon=True)
        self.port = port; self.baudrate = baudrate
        self._buffer = buffer; self.n_channels = n_channels; self.srate = srate
        self._frame_fields = frame_fields or []
        self.running = False; self._ser = None
        self.rx_callback = None

    def run(self):
        try:
            import serial
            self._ser = serial.Serial(port=self.port, baudrate=self.baudrate,
                                      bytesize=8, parity='N', stopbits=1, timeout=0.01)
            logger.info(f"串口打开: {self.port} @ {self.baudrate}, 帧字段: {len(self._frame_fields)}")
        except Exception as e:
            logger.error(f"串口失败: {e}"); return

        self.running = True; buf = b''; sample_count = 0; parse_tries = 0

        while self.running:
            try:
                n = self._ser.in_waiting
                raw = self._ser.read(n if n > 0 else 28)  # 至少读2帧(28字节)或等待
                if not raw: continue

                if self.rx_callback:
                    self.rx_callback(' '.join(f'{b:02X}' for b in raw), True)

                if self._frame_fields:
                    buf += raw
                    header_hex = self._get_header_hex()
                    header_bytes = bytes.fromhex(header_hex.replace(' ', ''))
                    while len(buf) >= len(header_bytes):
                        idx = buf.find(header_bytes)
                        if idx < 0: break
                        buf = buf[idx:]
                        # 帧尾校验 — 避免把数据中的0xAA误认为帧头
                        if not self._verify_frame(buf):
                            buf = buf[1:]
                            continue
                        data = self._parse_frame(buf)
                        parse_tries += 1
                        if data:
                            sample_count += 1
                            self._buffer.push([data], None)
                            total = sum(f.byte_count for f in self._frame_fields)
                            buf = buf[total:]
                        else:
                            buf = buf[1:]
                else:
                    # 无帧格式: 简单HEX行解析
                    for b in raw:
                        if b == 0x0A:  # \n
                            pass  # skip
                        else:
                            try:
                                vals = [float(b)]
                                while len(vals) < self.n_channels: vals.append(0.0)
                                sample_count += 1
                                self._buffer.push([vals[:self.n_channels]], None)
                            except Exception: pass

            except Exception as e:
                logger.error(f"读取错误: {e}"); break

        if self._ser: self._ser.close()
        logger.info(f"串口关闭, 采集 {sample_count} 样本")

    def _get_header_hex(self) -> str:
        for f in self._frame_fields:
            if f.field_type == '帧头':
                return f.value.replace(' ', '')
        return 'AA'

    def _get_tail_hex(self) -> str:
        for f in self._frame_fields:
            if f.field_type == '帧尾':
                return f.value.replace(' ', '')
        return '55'

    def _verify_frame(self, buf: bytes) -> bool:
        """校验帧尾来确认这不是误识别的帧头"""
        tail_hex = self._get_tail_hex()
        if not tail_hex: return True
        total = sum(f.byte_count for f in self._frame_fields)
        tail_bytes = bytes.fromhex(tail_hex.replace(' ', ''))
        if len(buf) < total: return False
        # 帧尾在最后一字节
        return buf[total - len(tail_bytes):total] == tail_bytes

    def _parse_frame(self, buf: bytes) -> list[float] | None:
        fields = self._frame_fields
        if not fields: return None
        try:
            offset = 0; values = []
            for f in fields:
                bc = f.byte_count
                if offset + bc > len(buf): return None
                raw_bytes = buf[offset:offset + bc]
                offset += bc
                if f.is_length or f.field_type in ('帧头', '帧尾', '校验'):
                    continue
                # 根据转换类型决定有符号/无符号
                is_signed = not f.convert_type.startswith('UInt')
                byte_order = 'big' if f.big_endian else 'little'
                if f.convert_type in ('Float', 'Double'):
                    import struct
                    fmt = '>f' if f.big_endian else '<f'
                    val = struct.unpack(fmt, raw_bytes[:4])[0] if len(raw_bytes) >= 4 else 0.0
                else:
                    val = int.from_bytes(raw_bytes, byte_order, signed=is_signed)
                if f.show_panel:
                    values.append(float(val))
            return values if values else None
        except Exception:
            return None

    def stop(self):
        self.running = False
