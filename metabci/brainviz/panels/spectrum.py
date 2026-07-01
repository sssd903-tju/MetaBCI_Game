# -*- coding: utf-8 -*-
"""
频谱分析面板 — FFT 功率谱 + 频带标注
"""

import numpy as np
from scipy import signal as scipy_signal
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QComboBox, QHBoxLayout, QLabel

from metabci.brainviz.config import SPECTRUM_SECONDS, BANDS, BAND_COLORS, COLORS
from metabci.brainviz.data_buffer import EEGBuffer


class SpectrumPanel(QWidget):
    """实时频谱分析"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buffer: EEGBuffer | None = None
        self._last_update = 0.0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        toolbar = QHBoxLayout()
        title = QLabel("📊 频谱分析")
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
        self._plot.getAxis("left").setLabel("Power", color=COLORS["text_secondary"])
        self._plot.getAxis("bottom").setLabel("Hz", color=COLORS["text_secondary"])
        self._plot.showGrid(x=True, y=True, alpha=0.2)
        self._plot.setXRange(0, 50)
        self._plot.setLogMode(x=False, y=True)

        self._curve = self._plot.plot(
            pen=pg.mkPen(color=COLORS["accent_green"], width=1.5)
        )

        # 频带区域
        for band_name, (lo, hi) in BANDS.items():
            color = BAND_COLORS.get(band_name, "#888")
            region = pg.LinearRegionItem(
                values=[lo, hi], orientation="vertical",
                brush=(50, 50, 50, 30), movable=False,
            )
            region.setZValue(-10)
            self._plot.addItem(region)

        # 频带图例
        legend = QHBoxLayout()
        legend.addStretch()
        for band_name, color in BAND_COLORS.items():
            lbl = QLabel(band_name)
            lbl.setStyleSheet(
                f"color: {color}; font-size: 10px; padding: 1px 4px;"
            )
            legend.addWidget(lbl)
        legend.addStretch()
        layout.addLayout(legend)
        layout.addWidget(self._plot)

    def set_buffer(self, buf: EEGBuffer):
        self._buffer = buf
        self._ch_sel.clear()
        for ch in range(buf.n_channels):
            self._ch_sel.addItem(f"通道 {ch + 1}")
        self._ch_sel.setCurrentIndex(0)

    def refresh(self, elapsed: float):
        if self._buffer is None or self._buffer.sample_count == 0:
            return
        if elapsed - self._last_update < SPECTRUM_SECONDS:
            return
        self._last_update = elapsed

        ch = self._ch_sel.currentIndex()
        _, data = self._buffer.get_recent(ch, SPECTRUM_SECONDS)
        if len(data) < int(self._buffer.srate * 0.5):
            return

        srate = self._buffer.srate
        nperseg = min(len(data), int(srate))
        freqs, psd = scipy_signal.welch(
            data, fs=srate, nperseg=nperseg, noverlap=nperseg // 2
        )
        mask = freqs <= 50
        self._curve.setData(freqs[mask], psd[mask])
