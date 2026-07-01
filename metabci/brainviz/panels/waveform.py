# -*- coding: utf-8 -*-
"""
实时波形面板 — 多通道 EEG 滚动显示
"""

import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QComboBox, QHBoxLayout, QLabel

from metabci.brainviz.config import WAVEFORM_SECONDS, COLORS
from metabci.brainviz.data_buffer import EEGBuffer


class WaveformPanel(QWidget):
    """多通道实时波形"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buffer: EEGBuffer | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        toolbar = QHBoxLayout()
        title = QLabel("📈 实时波形")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 14px;")
        toolbar.addWidget(title)
        toolbar.addStretch()

        self._ch_sel = QComboBox()
        self._ch_sel.setFixedWidth(120)
        self._ch_sel.setStyleSheet(f"""
            QComboBox {{
                background: {COLORS['bg_panel']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['grid']}; padding: 2px 6px; border-radius: 4px;
            }}
        """)
        toolbar.addWidget(self._ch_sel)
        layout.addLayout(toolbar)

        self._plot = pg.PlotWidget()
        self._plot.setBackground(COLORS["bg_dark"])
        self._plot.getAxis("left").setPen(COLORS["text_secondary"])
        self._plot.getAxis("bottom").setPen(COLORS["text_secondary"])
        self._plot.getAxis("left").setLabel("μV", color=COLORS["text_secondary"])
        self._plot.getAxis("bottom").setLabel("s", color=COLORS["text_secondary"])
        self._plot.showGrid(x=True, y=True, alpha=0.2)
        self._plot.setYRange(-200, 200)
        self._plot.setXRange(0, WAVEFORM_SECONDS)

        self._curve = self._plot.plot(
            pen=pg.mkPen(color=COLORS["accent_green"], width=1.2)
        )
        layout.addWidget(self._plot)

    def set_buffer(self, buf: EEGBuffer):
        self._buffer = buf
        self._ch_sel.clear()
        for ch in range(buf.n_channels):
            self._ch_sel.addItem(f"通道 {ch + 1}")
        self._ch_sel.setCurrentIndex(0)

    def refresh(self):
        if self._buffer is None or self._buffer.sample_count == 0:
            return
        ch = self._ch_sel.currentIndex()
        time, data = self._buffer.get_recent(ch, WAVEFORM_SECONDS)
        if len(time) > 1:
            self._curve.setData(time, data)
