# -*- coding: utf-8 -*-
"""
分类结果面板 — 专注度 / 频带能量 / 分类状态
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QFrame
)

from metabci.brainviz.config import COLORS, BANDS


class ClassificationPanel(QWidget):
    """实时指标展示"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QLabel("🎯 实时指标")
        title.setStyleSheet(f"color: {COLORS['on_surface']}; font-size: 14px;")
        layout.addWidget(title)

        # 专注度
        focus_card = self._card()
        fl = QVBoxLayout(focus_card)
        fh = QHBoxLayout()
        fh.addWidget(self._lbl("专注度", bold=True))
        fh.addStretch()
        self._focus_val = QLabel("-- %")
        self._focus_val.setStyleSheet(
            f"color: {COLORS['accent_green']}; font-size: 24px; font-weight: bold;"
        )
        fh.addWidget(self._focus_val)
        fl.addLayout(fh)

        self._focus_bar = QProgressBar()
        self._focus_bar.setRange(0, 100)
        self._focus_bar.setValue(0)
        self._focus_bar.setTextVisible(False)
        self._focus_bar.setFixedHeight(8)
        self._focus_bar.setStyleSheet(f"""
            QProgressBar {{ background: {COLORS['bg_dark']}; border: none; border-radius: 4px; }}
            QProgressBar::chunk {{ background: {COLORS['accent_green']}; border-radius: 4px; }}
        """)
        fl.addWidget(self._focus_bar)
        layout.addWidget(focus_card)

        # 频带能量
        bands_card = self._card()
        bl = QVBoxLayout(bands_card)
        bl.addWidget(self._lbl("频带能量", bold=True))

        self._band_bars: dict[str, QProgressBar] = {}
        self._band_vals: dict[str, QLabel] = {}
        for band_name, (lo, hi) in BANDS.items():
            row = QHBoxLayout()
            row.addWidget(self._lbl(f"{band_name} ({lo}-{hi}Hz)", 11, COLORS["text_secondary"], 120))

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            bar.setStyleSheet(f"""
                QProgressBar {{ background: {COLORS['bg_dark']}; border: none; border-radius: 3px; }}
                QProgressBar::chunk {{ background: {COLORS['accent_blue']}; border-radius: 3px; }}
            """)
            row.addWidget(bar)

            val_lbl = self._lbl("--", 10, COLORS["text_secondary"], 36)
            row.addWidget(val_lbl)

            self._band_bars[band_name] = bar
            self._band_vals[band_name] = val_lbl
            bl.addLayout(row)

        layout.addWidget(bands_card)

        # 分类状态
        status_card = self._card()
        sl = QVBoxLayout(status_card)
        sl.addWidget(self._lbl("分类状态", bold=True))
        self._status_lbl = QLabel("等待数据...")
        self._status_lbl.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 12px;"
            f"padding: 4px; background: {COLORS['bg_dark']}; border-radius: 4px;"
        )
        self._status_lbl.setWordWrap(True)
        sl.addWidget(self._status_lbl)
        layout.addWidget(status_card)
        layout.addStretch()

    def update_focus(self, pct: int):
        self._focus_val.setText(f"{pct}%")
        self._focus_bar.setValue(pct)
        c = (COLORS["accent_green"] if pct >= 65
             else COLORS["warning"] if pct >= 35
             else COLORS["danger"])
        self._focus_val.setStyleSheet(f"color: {c}; font-size: 24px; font-weight: bold;")

    def update_bands(self, power_map: dict[str, float], max_power: float = 1.0):
        for band_name, bar in self._band_bars.items():
            p = power_map.get(band_name, 0.0)
            pct = min(100, int(p / max(max_power, 1e-10) * 100))
            bar.setValue(pct)
            self._band_vals[band_name].setText(f"{p:.1f}")

    def set_status(self, text: str):
        self._status_lbl.setText(text)

    @staticmethod
    def _lbl(text: str, size: int = 12, color: str = COLORS["on_surface"],
             width: int | None = None, bold: bool = False) -> QLabel:
        lbl = QLabel(text)
        w = f"font-weight: bold;" if bold else ""
        lbl.setStyleSheet(f"color: {color}; font-size: {size}px; {w}")
        if width:
            lbl.setFixedWidth(width)
        return lbl

    @staticmethod
    def _card() -> QFrame:
        f = QFrame()
        f.setStyleSheet(f"""
            QFrame {{ background: {COLORS['bg_panel']}; border-radius: 8px; padding: 8px; }}
        """)
        return f
