# -*- coding: utf-8 -*-
"""
Signal Tab — 实时波形 + 频谱
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtGui import QFont
from metabci.brainviz.widgets.science_card import ScienceCard


class SignalTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 8)
        layout.setSpacing(12)

        # Placeholder — Phase 2
        placeholder = QLabel("Real-time Waveform . . .")
        placeholder.setFont(QFont("sans-serif", 16))
        placeholder.setStyleSheet("color: #585B70;")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(placeholder, 1)

        # Metrics
        metrics = QLabel("Channel: Fp1  |  Quality: --  |  SNR: --")
        metrics.setFont(QFont("sans-serif", 10))
        metrics.setStyleSheet("color: #6C7086;")
        layout.addWidget(metrics)

        # Science
        self._science = ScienceCard("Signal Acquisition · 信号采集", "")
        self._science.setMaximumHeight(200)
        layout.addWidget(self._science)

    def set_science(self, title: str, content: str):
        self._science.set_content(f"{title}", content)
