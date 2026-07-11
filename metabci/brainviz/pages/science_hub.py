# -*- coding: utf-8 -*-
"""
Science Hub — 科普广场
Paradigm cards + Electrode head diagram
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QScrollArea,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from metabci.brainviz.theme import (
    TEXT, TEXT2, TEXT3, ACCENT, SURFACE, SURFACE2, BORDER, BG,
    COLOR_ATTENTION, COLOR_SSVEP, COLOR_P300, COLOR_MI,
)
from metabci.brainviz.paradigm import PARADIGM_LIST, BaseParadigm
from metabci.brainviz.widgets.head_diagram import HeadDiagram


PARADIGM_COLORS = {
    'focus': COLOR_ATTENTION,
    'ssvep': COLOR_SSVEP,
    'p300':  COLOR_P300,
    'mi':    COLOR_MI,
}


class ParadigmCard(QFrame):
    clicked = Signal(BaseParadigm)

    def __init__(self, para: BaseParadigm, color: str):
        super().__init__()
        self._para = para
        self._color = color
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName('card')
        self.setMinimumSize(220, 130)
        self._setup()

    def _setup(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        # Color dot + name
        header = QHBoxLayout()
        dot = QLabel('●')
        dot.setStyleSheet(f'color:{self._color};font-size:18px;border:none;background:transparent;')
        header.addWidget(dot)
        name = QLabel(self._para.name)
        name.setFont(QFont('sans-serif', 20, QFont.Weight.Bold))
        name.setStyleSheet(f'color:{TEXT};border:none;background:transparent;')
        header.addWidget(name)
        header.addStretch()
        layout.addLayout(header)

        # Description
        desc = QLabel(self._para.description)
        desc.setWordWrap(True)
        desc.setStyleSheet(f'color:{TEXT2};font-size:13px;border:none;background:transparent;')
        layout.addWidget(desc)

        # Electrodes + region
        elecs = ', '.join(e.name for e in self._para.active_electrodes)
        region = self._para.active_electrodes[0].region if self._para.active_electrodes else ''
        info = QLabel(f'{elecs}  ·  {region}')
        info.setStyleSheet(
            f'color:{self._color};font-size:12px;font-weight:600;'
            f'border:none;background:transparent;'
        )
        layout.addWidget(info)

        layout.addStretch()

    def set_selected(self, sel: bool):
        self._selected = sel
        self.setObjectName('selectedCard' if sel else 'card')
        self.style().polish(self)

    def mousePressEvent(self, event):
        self.clicked.emit(self._para)


class ScienceHubPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self._mw = main_window
        self._paradigm: BaseParadigm = PARADIGM_LIST[0]
        self._cards: dict[str, ParadigmCard] = {}
        self._setup()

    def _setup(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 24)
        layout.setSpacing(24)

        # —— Title ——
        title = QLabel('科普广场')
        title.setObjectName('pageTitle')
        layout.addWidget(title)

        sub = QLabel('选择 BCI 范式，查看对应的脑电采集电极位置与工作原理')
        sub.setStyleSheet(f'color:{TEXT2};font-size:13px;')
        layout.addWidget(sub)

        # —— Paradigm cards: 2x2 grid ——
        cards_grid = QGridLayout()
        cards_grid.setSpacing(16)

        for i, para in enumerate(PARADIGM_LIST):
            color = PARADIGM_COLORS.get(para.paradigm_id, ACCENT)
            card = ParadigmCard(para, color)
            card.clicked.connect(self._on_paradigm)
            self._cards[para.paradigm_id] = card
            row, col = divmod(i, 2)
            cards_grid.addWidget(card, row, col)

        layout.addLayout(cards_grid)

        # —— Bottom: Head Diagram (4:3, left) + Explanation Card (right) ——
        bottom = QHBoxLayout()
        bottom.setSpacing(20)

        # Head diagram — 4:3, left aligned
        head_card = QFrame()
        head_card.setObjectName('card')
        head_card.setMinimumSize(575, 250)  # 2.3:1
        hc_layout = QVBoxLayout(head_card)
        hc_layout.setContentsMargins(12, 10, 12, 12)
        hc_layout.setSpacing(4)

        head_label = QLabel('国际 10-20 电极系统')
        head_label.setFont(QFont('sans-serif', 11, QFont.Weight.Bold))
        head_label.setStyleSheet(f'color:{TEXT};border:none;background:transparent;')
        head_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hc_layout.addWidget(head_label)

        self._head = HeadDiagram()
        hc_layout.addWidget(self._head, 1)

        bottom.addWidget(head_card)

        # Explanation card — right side
        self._explain_card = QFrame()
        self._explain_card.setObjectName('card')
        ec_layout = QVBoxLayout(self._explain_card)
        ec_layout.setContentsMargins(20, 16, 20, 16)
        ec_layout.setSpacing(6)

        self._explain_title = QLabel('')
        self._explain_title.setFont(QFont('sans-serif', 16, QFont.Weight.Bold))
        self._explain_title.setStyleSheet(f'color:{TEXT};border:none;background:transparent;')
        ec_layout.addWidget(self._explain_title)

        self._explain_electrodes = QLabel('')
        self._explain_electrodes.setFont(QFont('sans-serif', 12))
        self._explain_electrodes.setStyleSheet(f'color:{ACCENT};border:none;background:transparent;font-weight:600;')
        ec_layout.addWidget(self._explain_electrodes)

        self._explain_body = QLabel('')
        self._explain_body.setWordWrap(True)
        self._explain_body.setFont(QFont('sans-serif', 11))
        self._explain_body.setStyleSheet(f'color:{TEXT2};border:none;background:transparent;')
        self._explain_body.setTextFormat(Qt.TextFormat.PlainText)
        self._explain_body.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll = QScrollArea()
        scroll.setWidget(self._explain_body)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f'background:transparent;border:none;')
        ec_layout.addWidget(scroll, 1)

        ec_layout.addStretch()
        bottom.addWidget(self._explain_card, 1)

        layout.addLayout(bottom)

        # Init
        self._cards[PARADIGM_LIST[0].paradigm_id].set_selected(True)
        self._head.set_paradigm(
            PARADIGM_LIST[0].active_electrodes, PARADIGM_LIST[0].all_electrodes
        )
        self._update_explain(PARADIGM_LIST[0])

    def _on_paradigm(self, para: BaseParadigm):
        self._paradigm = para
        self._mw.current_paradigm = para
        for pid, card in self._cards.items():
            card.set_selected(pid == para.paradigm_id)
        self._head.set_paradigm(para.active_electrodes, para.all_electrodes)
        self._update_explain(para)

    def _update_explain(self, para: BaseParadigm):
        color = PARADIGM_COLORS.get(para.paradigm_id, ACCENT)
        self._explain_title.setText(f'{para.name}')
        self._explain_title.setStyleSheet(
            f'color:{color};font-size:20px;font-weight:800;border:none;background:transparent;'
        )

        elec_names = ', '.join(e.name for e in para.active_electrodes)
        regions = ', '.join(set(e.region for e in para.active_electrodes))
        self._explain_electrodes.setText(f'活动电极  {elec_names}    {regions}')

        body_parts = []
        if para.explain_summary:
            body_parts.append(para.explain_summary)
        if para.explain_principle:
            body_parts.append(para.explain_principle)
        if para.pipeline_steps:
            steps = '\n'.join(
                f'{i+1}. {s}' for i, s in enumerate(para.pipeline_steps)
            )
            body_parts.append(f'— 信号流程 —\n{steps}')

        self._explain_body.setText('\n\n'.join(body_parts))
