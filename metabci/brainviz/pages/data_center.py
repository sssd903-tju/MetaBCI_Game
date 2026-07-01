# -*- coding: utf-8 -*-
"""Data Center — 数据中心 (recording, playback, export)"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from metabci.brainviz.theme import TEXT2, TEXT3


class DataCenterPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 32)

        title = QLabel('数据中心')
        title.setObjectName('pageTitle')
        layout.addWidget(title)

        sub = QLabel('数据录制 · 离线回放 · 导出 — 待实现 (Phase 3)')
        sub.setStyleSheet(f'color:{TEXT2};font-size:13px;')
        layout.addWidget(sub)

        ph = QLabel('Data Management Coming Soon')
        ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph.setStyleSheet(f'color:{TEXT3};font-size:16px;margin-top:60px;')
        layout.addWidget(ph, 1)
