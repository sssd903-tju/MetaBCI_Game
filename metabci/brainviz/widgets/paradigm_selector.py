# -*- coding: utf-8 -*-
"""
范式选择器 — 专业卡片式 (无 emoji)
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame, QButtonGroup,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont

from metabci.brainviz.paradigm.base import BaseParadigm
from metabci.brainviz.widgets.head_diagram import HeadDiagram


class ParadigmCard(QFrame):
    """单个范式卡片"""
    clicked = Signal(BaseParadigm)

    def __init__(self, para: BaseParadigm, parent=None):
        super().__init__(parent)
        self._para = para
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(220, 100)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"""
            ParadigmCard {{
                background: #1E1E2E;
                border: 2px solid #313244;
                border-left: 4px solid {self._para.color};
                border-radius: 8px;
                padding: 12px 14px;
            }}
            ParadigmCard:hover {{
                background: #262637;
                border-color: {self._para.color};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 标题行
        title_row = QHBoxLayout()
        title = QLabel(self._para.name)
        title.setFont(QFont("sans-serif", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #CDD6F4; border: none; background: transparent;")
        title_row.addWidget(title)
        title_row.addStretch()

        # 颜色指示点
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {self._para.color}; font-size: 14px; border: none; background: transparent;")
        title_row.addWidget(dot)
        layout.addLayout(title_row)

        # 描述
        desc = QLabel(self._para.description)
        desc.setFont(QFont("sans-serif", 10))
        desc.setStyleSheet("color: #6C7086; border: none; background: transparent;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # 活动电极
        elec_text = ", ".join(e.name for e in self._para.active_electrodes)
        region = self._para.active_electrodes[0].region if self._para.active_electrodes else ""
        elec_label = QLabel(f"{elec_text}  ·  {region}")
        elec_label.setFont(QFont("sans-serif", 9))
        elec_label.setStyleSheet(f"color: {self._para.color}; border: none; background: transparent;")
        layout.addWidget(elec_label)

    def set_selected(self, sel: bool):
        self._selected = sel
        if sel:
            self.setStyleSheet(f"""
                ParadigmCard {{
                    background: #262637;
                    border: 2px solid {self._para.color};
                    border-left: 4px solid {self._para.color};
                    border-radius: 8px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                ParadigmCard {{
                    background: #1E1E2E;
                    border: 2px solid #313244;
                    border-left: 4px solid {self._para.color};
                    border-radius: 8px;
                }}
            """)

    def mousePressEvent(self, event):
        self.clicked.emit(self._para)

    @property
    def paradigm(self) -> BaseParadigm:
        return self._para


class ParadigmSelector(QWidget):
    """范式选择栏 — 卡片 + 电极图"""

    paradigm_changed = Signal(BaseParadigm)

    def __init__(self, paradigms: list[BaseParadigm], parent=None):
        super().__init__(parent)
        self._paradigms = paradigms
        self._cards: dict[str, ParadigmCard] = {}
        self._current: BaseParadigm | None = None
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedHeight(130)
        self.setStyleSheet("background: #11111B; border-bottom: 1px solid #313244;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # 品牌标题
        brand_layout = QVBoxLayout()
        brand = QLabel("MetaBCI")
        brand.setFont(QFont("sans-serif", 22, QFont.Weight.Bold))
        brand.setStyleSheet("color: #CDD6F4; border: none; background: transparent;")
        brand_layout.addWidget(brand)
        sub = QLabel("Visualization Platform")
        sub.setFont(QFont("sans-serif", 9))
        sub.setStyleSheet("color: #6C7086; border: none; background: transparent;")
        brand_layout.addWidget(sub)
        brand_layout.addStretch()
        layout.addLayout(brand_layout)

        # 分隔线
        sep = QLabel("")
        sep.setFixedWidth(1)
        sep.setStyleSheet("background: #313244; border: none;")
        layout.addWidget(sep)

        # 范式卡片
        for para in self._paradigms:
            card = ParadigmCard(para)
            card.clicked.connect(self._select)
            self._cards[para.paradigm_id] = card
            layout.addWidget(card)

        layout.addStretch()

        # 电极定位图
        self._head = HeadDiagram()
        layout.addWidget(self._head)

        # 默认选中第一个
        if self._paradigms:
            self._select(self._paradigms[0])

    def _select(self, para: BaseParadigm):
        self._current = para
        for pid, card in self._cards.items():
            card.set_selected(pid == para.paradigm_id)
        self._head.set_paradigm(para.active_electrodes, para.all_electrodes)
        self.paradigm_changed.emit(para)

    @property
    def current(self) -> BaseParadigm | None:
        return self._current
