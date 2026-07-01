# -*- coding: utf-8 -*-
"""
FrameField — 数据帧字段模型
"""

from dataclasses import dataclass, field


@dataclass
class FrameField:
    field_type: str = '1Byte'
    name: str = '未命名'
    value: str = ''
    byte_count: int = 1
    is_length: bool = False
    show_panel: bool = True
    big_endian: bool = False
    convert_type: str = 'Hex'

    def __post_init__(self):
        self._resolve_type()
        self.value = self.constrain_value()

    def _resolve_type(self):
        type_map = {
            '帧头':   (1, False),
            '帧序号': (1, False),
            '帧ID':   (1, False),
            '帧长度': (1, True),
            '1Byte':  (1, False),
            '2Byte':  (2, False),
            '3Byte':  (3, False),
            '4Byte':  (4, False),
            '8Byte':  (8, False),
            '校验':   (1, False),
            '帧尾':   (1, False),
        }
        if self.field_type in type_map:
            self.byte_count, self.is_length = type_map[self.field_type]
        val_map = {
            '帧头': 'AA', '帧尾': '55', '帧序号': '00',
            '帧ID': '00', '帧长度': '00', '校验': '00',
        }
        if not self.value or self.value in ('00', '7E', 'BB', '00 ', '00 00', '00 00 00 00'):
            self.value = val_map.get(self.field_type, '00')

    def constrain_value(self) -> str:
        hex_parts = self.value.strip().split()
        clean = []
        for h in hex_parts:
            try:
                int(h, 16)
                clean.append(h.upper().zfill(2))
            except ValueError:
                pass
        if len(clean) > self.byte_count:
            clean = clean[:self.byte_count]
        while len(clean) < self.byte_count:
            clean.append('00')
        return ' '.join(clean)


CONVERT_TYPES = [
    'Hex', 'UInt8', 'Int8', 'UInt16', 'Int16',
    'UInt32', 'Int32', 'UInt64', 'Int64',
    'Float', 'Double', 'ASCII', 'UTF8', 'BCD',
]
