# -*- coding: utf-8 -*-
"""
🧮 算法解码 Tab — 分类结果 + 置信度 (按范式切换)
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from metabci.brainviz.config import COLORS
from metabci.brainviz.widgets.science_card import ScienceCard


class DecodeTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        placeholder = QLabel("🧮 Classification & Confidence — 待实现 (Phase 2)")
        placeholder.setStyleSheet(f"""
            color: {COLORS['text_secondary']}; font-size: 16px;
            background: {COLORS['surface']}; border-radius: 8px; padding: 40px;
        """)
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(placeholder, 1)

        self._science = ScienceCard("Algorithm Decoding", "")
        self._science.setMaximumHeight(200)
        layout.addWidget(self._science)

    def set_science(self, title: str, content: str):
        self._science.set_content(title, content)
