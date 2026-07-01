# -*- coding: utf-8 -*-
"""
MetaBCI Light Theme — from prototype, adapted for PySide6
"""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtCore import Qt

# Color tokens
BG       = '#f8f9fa'
SURFACE  = '#ffffff'
SURFACE2 = '#f0f1f3'
BORDER   = '#e2e4e8'
TEXT     = '#1a1d26'
TEXT2    = '#5f6775'
TEXT3    = '#9ca3af'
GREEN    = '#22c55e'
BLUE     = '#3b82f6'
YELLOW   = '#f59e0b'
RED      = '#ef4444'
ORANGE   = '#f97316'
ACCENT   = '#6366f1'
ACCENT2  = '#8b5cf6'

# Paradigm colors
COLOR_SSVEP     = ACCENT
COLOR_MI        = BLUE
COLOR_P300      = ORANGE
COLOR_ATTENTION = GREEN

STYLESHEET = f"""
QMainWindow, QDialog, QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
    font-size: 13px;
}}

QWidget#sidebar {{
    background-color: {SURFACE};
    border-right: 1px solid {BORDER};
}}

QPushButton {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {SURFACE2};
    border-color: {TEXT3};
}}
QPushButton:pressed {{ background-color: {BORDER}; }}

QLabel#pageTitle {{
    font-size: 22px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#sectionLabel {{
    font-size: 13px;
    color: {TEXT3};
    font-weight: 600;
}}

QFrame#card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 24px;
}}
QFrame#card:hover {{ border-color: {ACCENT}; background: #fafaff; }}
QFrame#selectedCard {{
    background: {SURFACE};
    border: 2px solid {ACCENT};
    border-radius: 12px;
    padding: 24px;
}}

QTabWidget::pane {{ border: none; background: {SURFACE}; }}
QTabBar::tab {{
    background: transparent; color: {TEXT2};
    padding: 10px 20px; border: none;
    border-bottom: 2px solid transparent; font-weight: 500;
}}
QTabBar::tab:selected {{
    color: {ACCENT}; font-weight: 600;
    border-bottom: 2px solid {ACCENT};
}}

QScrollBar:vertical {{
    background: transparent; width: 6px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 3px; min-height: 30px;
}}

QStatusBar {{
    background: {SURFACE}; color: {TEXT2};
    border-top: 1px solid {BORDER}; font-size: 12px;
}}

QTextBrowser {{
    background: {SURFACE}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 8px;
    font-size: 12px; padding: 8px;
}}
"""


def apply_theme(app):
    app.setStyle('Fusion')
    app.setStyleSheet(STYLESHEET)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(SURFACE))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(SURFACE2))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(SURFACE))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor('#ffffff'))
    app.setPalette(palette)
