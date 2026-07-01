# -*- coding: utf-8 -*-
"""
科普折叠卡片 — qt-material 风格
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QTextBrowser,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class ScienceCard(QWidget):
    toggled = Signal(bool)

    def __init__(self, title: str = "", content: str = "", parent=None):
        super().__init__(parent)
        self._expanded = False
        self._title = title
        self._content = content
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QPushButton()
        self._header.setFont(QFont("sans-serif", 12, QFont.Weight.Bold))
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.clicked.connect(self._toggle)
        layout.addWidget(self._header)

        self._text = QTextBrowser()
        self._text.setOpenExternalLinks(True)
        self._text.setMaximumHeight(160)
        self._text.setVisible(False)
        layout.addWidget(self._text)

        self._update_header()

    def set_content(self, title: str, content: str):
        self._title = title
        self._content = content
        self._text.setHtml(content)
        self._update_header()

    def _toggle(self):
        self._expanded = not self._expanded
        self._text.setVisible(self._expanded)
        self._update_header()
        self.toggled.emit(self._expanded)

    def _update_header(self):
        a = "▼" if self._expanded else "▶"
        self._header.setText(f"  {a}  {self._title}")
