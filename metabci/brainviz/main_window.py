# -*- coding: utf-8 -*-
"""
MainWindow — MetaBCI Platform (sidebar + stacked pages)
Layout from prototype, content adapted for BCI pipeline visualization.
"""

import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QStackedWidget, QPushButton, QStatusBar,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from metabci.brainviz.config import WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT, PLOT_REFRESH_MS
from metabci.brainviz.data_buffer import EEGBuffer
from metabci.brainviz.theme import TEXT, TEXT2, TEXT3, ACCENT, SURFACE2, BORDER, BG

logger = logging.getLogger("brainviz")


# ============================================================
# Sidebar Nav Button
# ============================================================

class NavButton(QPushButton):
    def __init__(self, icon, text, page_name, badge=''):
        super().__init__()
        self.page_name = page_name
        label = f'{icon}  {text}'
        if badge: label += f'    {badge}'
        self.setText(label)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(40)
        self._active = False
        self._update_style()

    def set_active(self, active):
        self._active = active
        self._update_style()

    def _update_style(self):
        if self._active:
            self.setStyleSheet(f"""
                QPushButton {{
                    text-align: left; padding: 10px 16px; border: none;
                    border-radius: 6px; background: {ACCENT}; color: #ffffff;
                    font-size: 14px; font-weight: 600;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    text-align: left; padding: 10px 16px; border: none;
                    border-radius: 6px; background: transparent; color: {TEXT2};
                    font-size: 14px; font-weight: 500;
                }}
                QPushButton:hover {{
                    background: {SURFACE2}; color: {TEXT};
                }}
            """)


# ============================================================
# Main Window
# ============================================================

class MainWindow(QMainWindow):
    PAGES = {
        'science_hub':  '科普广场',
        'live_lab':     '在线实验室',
        'game_platform':'游戏平台',
        'algo_lab':     '算法工坊',
        'data_center':  '数据中心',
    }

    def __init__(self, simulate: bool = False):
        super().__init__()
        self._simulate = simulate
        self._buffer: EEGBuffer | None = None
        self._inlet = None; self._pull_thread = None
        self._srate = 250.0; self._n_channels = 8
        self._nav_buttons: dict[str, NavButton] = {}
        self._page_cache: dict = {}
        self.current_paradigm = None  # shared across pages

        self.setWindowTitle(WINDOW_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self._setup_ui()

        # Connect LSL on startup
        self._scan_lsl()

    # ============================================================
    # UI
    # ============================================================

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # —— Sidebar ——
        sidebar = QWidget()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(220)
        sb = QVBoxLayout()
        sb.setContentsMargins(12, 20, 12, 16)
        sb.setSpacing(4)

        # Logo
        logo = QLabel('MetaBCI')
        logo.setStyleSheet(f'font-size:22px;font-weight:800;color:{ACCENT};padding:0 8px 16px;')
        sb.addWidget(logo)

        section = QLabel('功能导航')
        section.setStyleSheet(f'font-size:11px;color:{TEXT3};letter-spacing:1px;padding:8px 8px 4px;')
        sb.addWidget(section)

        # Nav items
        nav_items = [
            ('', '科普广场', 'science_hub', ''),
            ('', '在线实验室', 'live_lab', ''),
            ('', '游戏平台', 'game_platform', ''),
            ('', '算法工坊', 'algo_lab', ''),
            ('', '数据中心', 'data_center', ''),
        ]
        for icon, text, page, badge in nav_items:
            btn = NavButton(icon, text, page, badge)
            btn.clicked.connect(lambda checked, p=page: self.navigate(p))
            self._nav_buttons[page] = btn
            sb.addWidget(btn)

        sb.addStretch()

        # Device status
        self._device_status = QLabel('未连接设备')
        self._device_status.setStyleSheet(
            f'font-size:12px;color:{TEXT2};padding:12px 8px;border-top:1px solid {BORDER};'
        )
        sb.addWidget(self._device_status)

        sidebar.setLayout(sb)
        root.addWidget(sidebar)

        # —— Content Stack ——
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f'background:{BG};')

        # Lazy placeholders
        for page_name in self.PAGES:
            ph = QWidget()
            phl = QVBoxLayout(ph)
            lbl = QLabel(self.PAGES[page_name])
            lbl.setStyleSheet(f'color:{TEXT3};font-size:16px;')
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            phl.addWidget(lbl)
            self._stack.addWidget(ph)

        root.addWidget(self._stack)
        central.setLayout(root)

        # Start at science hub
        self.navigate('science_hub')

    # ============================================================
    # Navigation
    # ============================================================

    def navigate(self, page_name: str):
        for name, btn in self._nav_buttons.items():
            btn.set_active(name == page_name)

        if page_name not in self._page_cache:
            page = self._create_page(page_name)
            self._page_cache[page_name] = page
            idx = list(self.PAGES.keys()).index(page_name)
            old = self._stack.widget(idx)
            self._stack.insertWidget(idx, page)
            if old and old is not page:
                old.deleteLater()

        if page_name in self._page_cache:
            self._stack.setCurrentWidget(self._page_cache[page_name])

    def _create_page(self, name: str) -> QWidget:
        if name == 'science_hub':
            from metabci.brainviz.pages.science_hub import ScienceHubPage
            return ScienceHubPage(self)
        elif name == 'live_lab':
            from metabci.brainviz.pages.live_lab import LiveLabPage
            return LiveLabPage(self)
        elif name == 'data_center':
            from metabci.brainviz.pages.data_center import DataCenterPage
            return DataCenterPage(self)
        elif name == 'algo_lab':
            from metabci.brainviz.pages.algo_lab import AlgoLabPage
            return AlgoLabPage(self)
        elif name == 'game_platform':
            from metabci.brainviz.pages.game_platform import GamePlatformPage
            return GamePlatformPage(self)
        return QWidget()

    # ============================================================
    # LSL
    # ============================================================

    def _scan_lsl(self):
        try:
            from pylsl import resolve_byprop
            streams = resolve_byprop("type", "EEG", timeout=2.0)
            if streams:
                s = streams[0]
                self._device_status.setText(f'● {s.name()} ({s.channel_count()}ch)')
                self._device_status.setStyleSheet(
                    f'font-size:12px;color:#22c55e;padding:12px 8px;border-top:1px solid {BORDER};'
                )
            else:
                self._device_status.setText('○ 未发现脑电设备')
        except Exception:
            self._device_status.setText('○ LSL unavailable')

    def closeEvent(self, event):
        if self._pull_thread:
            self._pull_thread.running = False
        event.accept()
