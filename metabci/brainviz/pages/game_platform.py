# -*- coding: utf-8 -*-
"""游戏平台 — Godot 游戏范式启动与管理"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from metabci.brainviz.theme import TEXT, TEXT2, TEXT3, ACCENT, SURFACE, BORDER

GAMES = [
    ('🧠', '凝神一矢', '专注度检测 · 射箭', '控制专注度让准星命中靶心', '#4CAF50',
     '前额叶 Fp1/Fp2 采集专注度信号，实时控制准星向靶心靠拢。专注度越高，准星越稳、越准！'),
    ('🌊', '深海下潜', '专注度检测 · 探索', '保持专注照亮海底收集标本', '#4CAF50',
     '探照灯光圈随专注度变化，高专注时视野开阔、氧气消耗慢。收集5种海洋标本即可通关。'),
    ('👁', '思维贪吃蛇', 'SSVEP · 方向控制', '注视闪烁目标用脑电波控制方向', '#FF6F00',
     '四个方向以不同频率闪烁（8/10/12/15Hz），盯着哪个方向看，蛇就往哪走！'),
    ('🔨', '打地鼠', 'SSVEP · 目标选择', '注视闪烁的洞口打中地鼠', '#FF6F00',
     '2×2 到 4×4 动态网格，每个洞以不同频率闪烁。看哪个洞，锤子就落在哪里。'),
    ('🃏', '卡牌读心', 'P300 · 目标检测', '心里默想一张牌，电脑能猜到', '#E91E63',
     '6张卡牌随机闪烁，默想目标那张。大脑的 P300 信号会暴露你的选择！'),
    ('💪', '运动想象', 'MI · 方向控制', '想象左右手运动来控制方向', '#29B6F6',
     '不需要动手，光靠想象就能控制。想象左手→向左跳，想象右手→向右跳。'),
]


class GamePlatformPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self._mw = main_window
        self._setup()

    def _setup(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 16); layout.setSpacing(16)

        title = QLabel('游戏平台'); title.setObjectName('pageTitle')
        layout.addWidget(title)

        sub = QLabel('选择 BCI 游戏范式，启动 Godot 游戏引擎进行互动体验')
        sub.setStyleSheet(f'color:{TEXT2};font-size:13px;')
        layout.addWidget(sub)

        # 游戏卡片网格 (3×2 填满)
        grid = QGridLayout(); grid.setSpacing(14)
        for i, (icon, name, paradigm, desc, color, detail) in enumerate(GAMES):
            card = self._game_card(icon, name, paradigm, desc, color, detail)
            row, col = divmod(i, 3)
            grid.addWidget(card, row, col)
        layout.addLayout(grid, 1)

        # 底部提示
        hint = QLabel('请先在科普广场选择范式，再启动对应游戏。Godot 引擎需单独运行。')
        hint.setStyleSheet(f'color:{TEXT3};font-size:11px;padding:8px;')
        layout.addWidget(hint)

    def _game_card(self, icon: str, name: str, paradigm: str, desc: str, color: str, detail: str) -> QFrame:
        f = QFrame()
        f.setObjectName('card'); f.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(f); layout.setContentsMargins(24, 20, 24, 20); layout.setSpacing(8)

        header = QHBoxLayout()
        ic = QLabel(icon); ic.setStyleSheet('font-size:36px;border:none;background:transparent;')
        header.addWidget(ic)
        title = QLabel(name)
        title.setFont(QFont('sans-serif', 18, QFont.Weight.Bold))
        title.setStyleSheet(f'color:{TEXT};border:none;background:transparent;')
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        tag = QLabel(paradigm)
        tag.setStyleSheet(f'color:{color};font-size:11px;font-weight:600;border:none;background:transparent;')
        layout.addWidget(tag)

        d = QLabel(desc); d.setWordWrap(True)
        d.setStyleSheet(f'color:{TEXT2};font-size:13px;border:none;background:transparent;')
        layout.addWidget(d)

        detail_lbl = QLabel(detail); detail_lbl.setWordWrap(True)
        detail_lbl.setStyleSheet(f'color:{TEXT3};font-size:11px;line-height:1.5;border:none;background:transparent;')
        layout.addWidget(detail_lbl)

        layout.addStretch()
        return f
