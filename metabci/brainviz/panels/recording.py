# -*- coding: utf-8 -*-
"""
数据管理面板 — 录制 / 回放 / 导出
"""

import time
import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFileDialog,
)
from PySide6.QtCore import Qt

from metabci.brainviz.config import COLORS
from metabci.brainviz.data_buffer import EEGBuffer


class RecordingPanel(QWidget):
    """数据录制与管理"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buffer: EEGBuffer | None = None
        self._recording = False
        self._record_start = 0.0
        self._recorded: list[dict] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # 标题
        title = QLabel("💾 数据管理")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 16px;")
        layout.addWidget(title)

        # 控制按钮
        btn_row = QHBoxLayout()

        self._record_btn = QPushButton("⏺ 开始录制")
        self._record_btn.setStyleSheet(self._btn_style())
        self._record_btn.clicked.connect(self._toggle_record)
        btn_row.addWidget(self._record_btn)

        export_btn = QPushButton("📥 导出 .npy")
        export_btn.setStyleSheet(self._btn_style())
        export_btn.clicked.connect(self._export_npy)
        btn_row.addWidget(export_btn)

        export_csv_btn = QPushButton("📥 导出 .csv")
        export_csv_btn.setStyleSheet(self._btn_style())
        export_csv_btn.clicked.connect(self._export_csv)
        btn_row.addWidget(export_csv_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 录制状态
        self._status_lbl = QLabel("就绪")
        self._status_lbl.setStyleSheet(
            f"color: {COLORS['text_secondary']}; padding: 8px;"
            f"background: {COLORS['bg_panel']}; border-radius: 6px;"
        )
        layout.addWidget(self._status_lbl)

        # 日志
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(f"""
            QTextEdit {{
                background: {COLORS['bg_dark']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['grid']}; border-radius: 6px;
                font-family: monospace; font-size: 11px;
            }}
        """)
        layout.addWidget(self._log)

        layout.addStretch()

    def set_buffer(self, buf: EEGBuffer):
        self._buffer = buf

    def _toggle_record(self):
        if self._recording:
            self._stop_record()
        else:
            self._start_record()

    def _start_record(self):
        if self._buffer is None:
            self._log_message("⚠ 无数据源，无法录制")
            return
        self._recording = True
        self._record_start = time.time()
        self._recorded.clear()
        self._record_btn.setText("⏹ 停止录制")
        self._record_btn.setStyleSheet(self._btn_style(active=True))
        self._status_lbl.setText("🔴 录制中...")
        self._status_lbl.setStyleSheet(
            f"color: {COLORS['danger']}; padding: 8px; font-weight: bold;"
            f"background: {COLORS['bg_panel']}; border-radius: 6px;"
        )
        self._log_message("开始录制...")

    def _stop_record(self):
        self._recording = False
        self._record_btn.setText("⏺ 开始录制")
        self._record_btn.setStyleSheet(self._btn_style())
        dur = time.time() - self._record_start
        self._status_lbl.setText(f"就绪 (上次录制: {dur:.1f}s)")
        self._status_lbl.setStyleSheet(
            f"color: {COLORS['text_secondary']}; padding: 8px;"
            f"background: {COLORS['bg_panel']}; border-radius: 6px;"
        )

        # 保存缓冲区快照
        if self._buffer:
            data = np.column_stack([
                self._buffer.get_channel(ch)
                for ch in range(self._buffer.n_channels)
            ])
            self._recorded.append({
                "data": data,
                "time": self._buffer.get_time(),
                "srate": self._buffer.srate,
                "duration": dur,
            })

        self._log_message(f"录制完成: {dur:.1f}s, {data.shape[0]} 样本")

    def _export_npy(self):
        if not self._recorded:
            self._log_message("⚠ 无录制数据")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 NPY", "", "NumPy (*.npy)"
        )
        if path:
            np.save(path, self._recorded[-1]["data"])
            self._log_message(f"已导出: {path}")

    def _export_csv(self):
        if not self._recorded:
            self._log_message("⚠ 无录制数据")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 CSV", "", "CSV (*.csv)"
        )
        if path:
            rec = self._recorded[-1]
            header = ",".join(f"Ch{ch+1}" for ch in range(rec["data"].shape[1]))
            np.savetxt(path, rec["data"], delimiter=",", header=header, comments="")
            self._log_message(f"已导出: {path}")

    def _log_message(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self._log.append(f"[{ts}] {msg}")

    @staticmethod
    def _btn_style(active: bool = False) -> str:
        bg = COLORS["danger"] if active else COLORS["bg_panel"]
        return f"""
            QPushButton {{
                background: {bg}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['grid']};
                padding: 6px 14px; border-radius: 4px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {COLORS['accent_green']}; }}
        """
