# -*- coding: utf-8 -*-
"""
10-20 电极定位图 — 亮色主题版
"""

import math
from PySide6.QtWidgets import QWidget, QToolTip, QSizePolicy
from PySide6.QtCore import QTimer, Qt, QPointF
from PySide6.QtGui import (
    QPainter, QPainterPath, QColor, QPen, QFont, QBrush, QRadialGradient,
)

from metabci.brainviz.theme import SURFACE, SURFACE2, TEXT, TEXT2, TEXT3, BORDER, BG
from metabci.brainviz.paradigm.base import Electrode


class HeadDiagram(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)

        self._all_electrodes: list[Electrode] = []
        self._active_names: set[str] = set()
        self._blink_phase = 0.0
        self._hit_areas: dict[str, tuple[float, float, float]] = {}

        self._blink_timer = QTimer()
        self._blink_timer.timeout.connect(self._tick)
        self._blink_timer.start(40)

    def set_paradigm(self, active_electrodes: list[Electrode], all_electrodes: list[Electrode]):
        self._active_names = {e.name for e in active_electrodes}
        self._all_electrodes = all_electrodes
        self.update()

    def _tick(self):
        self._blink_phase += 0.15
        if self._blink_phase > 2 * math.pi:
            self._blink_phase = 0.0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2 - 5
        head_rx, head_ry = 100, 105

        # Background — light
        p.setBrush(QColor(SURFACE))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w, h, 8, 8)

        # Head outline
        head_path = QPainterPath()
        head_path.addEllipse(QPointF(cx, cy), head_rx, head_ry)
        p.setPen(QPen(QColor(TEXT3), 1.5))
        p.setBrush(QColor('#f0f1f3'))
        p.drawPath(head_path)

        # Nose
        nose_path = QPainterPath()
        nose_path.moveTo(cx - 6, cy - head_ry + 4)
        nose_path.lineTo(cx + 6, cy - head_ry + 4)
        nose_path.lineTo(cx, cy - head_ry - 10)
        nose_path.closeSubpath()
        p.setPen(QPen(QColor(TEXT3), 1))
        p.setBrush(QColor(SURFACE2))
        p.drawPath(nose_path)

        # Midline + coronal line
        p.setPen(QPen(QColor(TEXT3), 0.5, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(cx, cy - head_ry), QPointF(cx, cy + head_ry))
        p.drawLine(QPointF(cx - head_rx, cy), QPointF(cx + head_rx, cy))

        # Draw electrodes
        self._hit_areas.clear()
        for elec in self._all_electrodes:
            px = cx + (elec.x - 0.5) * 2 * head_rx
            py = cy + (elec.y - 0.5) * 2 * head_ry
            is_active = elec.name in self._active_names
            r = 6.5 if is_active else 3

            if is_active:
                # Blinking glow
                glow_val = (math.sin(self._blink_phase) + 1) / 2
                glow_r = r + glow_val * 7

                gradient = QRadialGradient(QPointF(px, py), glow_r)
                active_color = QColor('#6366f1')  # accent indigo
                active_color.setAlpha(int(50 + glow_val * 70))
                gradient.setColorAt(0, active_color)
                active_color.setAlpha(0)
                gradient.setColorAt(1, active_color)
                p.setBrush(QBrush(gradient))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(px, py), glow_r, glow_r)

                # Electrode dot
                p.setBrush(QColor('#6366f1'))
                p.setPen(QPen(QColor('#4f46e5'), 1.5))
            else:
                p.setBrush(QColor(TEXT3))
                p.setPen(QPen(QColor(BORDER), 0.5))

            p.drawEllipse(QPointF(px, py), r, r)

            # Label for active
            if is_active:
                font = QFont('Menlo', 8, QFont.Weight.Bold)
                p.setFont(font)
                p.setPen(QColor(TEXT))
                lx = px - 10 if elec.x > 0.5 else px + 6
                ly = py + r + 12
                p.drawText(int(lx), int(ly), elec.name)

            self._hit_areas[elec.name] = (px, py, r + 4)

    def mouseMoveEvent(self, event):
        pos = event.position()
        for name, (px, py, r) in self._hit_areas.items():
            if (pos.x() - px) ** 2 + (pos.y() - py) ** 2 < r ** 2:
                for e in self._all_electrodes:
                    if e.name == name:
                        QToolTip.showText(
                            event.globalPosition().toPoint(),
                            f'{e.name}\n{e.region}\n{e.description}',
                            self,
                        )
                        return
        QToolTip.hideText()
