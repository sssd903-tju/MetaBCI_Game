# -*- coding: utf-8 -*-
"""
串口配置对话框 — 参数设置 + 接收区监控
连接由主界面统一管理
"""

import json, os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QFormLayout, QTextEdit, QCheckBox, QDialogButtonBox,
    QGroupBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from metabci.brainviz.theme import TEXT, TEXT2, ACCENT, SURFACE, BORDER


class SerialDialog(QDialog):
    rx_data = Signal(str, bool)
    config_changed = Signal(object)  # 配置变更 → 同步到主界面

    def __init__(self, parent=None, current_port=''):
        super().__init__(parent)
        self.setWindowTitle('串口参数设置')
        self.setMinimumSize(560, 550)
        self._config_path = os.path.expanduser('~/.metabci_serial_config.json')
        self._current_port = current_port
        self._frame_fields: list = []
        self._setup()
        self._load_config()
        self.rx_data.connect(self._on_rx_data, Qt.ConnectionType.QueuedConnection)

    def _setup(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10); layout.setContentsMargins(16, 12, 16, 12)

        title = QLabel('串口参数设置')
        title.setFont(QFont('sans-serif', 16, QFont.Weight.Bold))
        title.setStyleSheet(f'color:{TEXT};'); layout.addWidget(title)

        # —— 串口参数 ——
        form = QFormLayout(); form.setSpacing(8)

        self._port_combo = QComboBox(); self._port_combo.setMinimumWidth(220)
        self._refresh_ports()
        port_row = QHBoxLayout()
        port_row.addWidget(self._port_combo)
        refresh_btn = QPushButton('刷新'); refresh_btn.clicked.connect(self._refresh_ports)
        port_row.addWidget(refresh_btn)
        form.addRow('串口:', port_row)

        self._baud_combo = QComboBox()
        for b in ['9600','19200','38400','57600','115200','230400','460800']:
            self._baud_combo.addItem(b)
        self._baud_combo.setCurrentText('115200')
        form.addRow('波特率:', self._baud_combo)

        self._data_combo = QComboBox()
        for d in ['5','6','7','8']: self._data_combo.addItem(d)
        self._data_combo.setCurrentText('8')
        form.addRow('数据位:', self._data_combo)

        self._stop_combo = QComboBox()
        for s in ['1','1.5','2']: self._stop_combo.addItem(s)
        form.addRow('停止位:', self._stop_combo)

        self._parity_combo = QComboBox()
        for p in ['无','奇校验','偶校验']: self._parity_combo.addItem(p)
        form.addRow('校验:', self._parity_combo)

        layout.addLayout(form)

        # 帧格式按钮
        self._frame_btn = QPushButton('帧格式配置')
        self._frame_btn.clicked.connect(self._open_frame)
        layout.addWidget(self._frame_btn)

        # —— 接收区 ——
        rx_group = QGroupBox('接收区')
        rx_layout = QVBoxLayout(rx_group)

        rx_toolbar = QHBoxLayout()
        self._hex_cb = QCheckBox('HEX 显示')
        self._hex_cb.setChecked(True)
        self._hex_cb.setStyleSheet(f'color:{TEXT};font-weight:500;')
        rx_toolbar.addWidget(self._hex_cb)
        rx_toolbar.addStretch()
        clear_btn = QPushButton('清空')
        clear_btn.clicked.connect(lambda: self._rx_text.clear())
        rx_toolbar.addWidget(clear_btn)
        rx_layout.addLayout(rx_toolbar)

        self._rx_text = QTextEdit()
        self._rx_text.setReadOnly(True)
        self._rx_text.setFont(QFont('Menlo', 11))
        self._rx_text.setStyleSheet(f'background:{SURFACE};color:{TEXT};border:1px solid {BORDER};border-radius:6px;')
        self._rx_text.setMinimumHeight(180)
        rx_layout.addWidget(self._rx_text)
        layout.addWidget(rx_group, 1)

        # —— 按钮 ——
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self._on_cancel)
        layout.addWidget(btns)

    # ============================================================
    # 接收区 (跨线程安全)
    # ============================================================

    def append_rx(self, text: str, is_hex: bool):
        self.rx_data.emit(text, is_hex)

    def _on_rx_data(self, text: str, is_hex: bool):
        if is_hex != self._hex_cb.isChecked():
            return
        self._rx_text.append(text)
        if self._rx_text.document().blockCount() > 200:
            cursor = self._rx_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor, 50)
            cursor.removeSelectedText()

    # ============================================================
    # 串口扫描
    # ============================================================

    def _open_frame(self):
        from metabci.brainviz.frame_parse_dialog import FrameParseDialog
        dlg = FrameParseDialog(self)
        if self._frame_fields:
            dlg._fields = list(self._frame_fields)
            dlg._refresh_table()
        if dlg.exec() == FrameParseDialog.DialogCode.Accepted:
            self._frame_fields = dlg.get_fields()
            self._save_config()

    def _refresh_ports(self):
        self._port_combo.clear()
        try:
            from serial.tools import list_ports
            for p in list_ports.comports():
                self._port_combo.addItem(f'{p.device} — {p.description}', p.device)
            if self._port_combo.count() == 0:
                self._port_combo.addItem('(未发现串口)')
        except ImportError:
            self._port_combo.addItem('请安装 pyserial')
        except Exception as e:
            self._port_combo.addItem(f'错误: {e}')

    # ============================================================
    # 持久化
    # ============================================================

    def _save_config(self):
        data = {
            'port': self._port_combo.currentData() or '',
            'baudrate': self._baud_combo.currentText(),
            'bytesize': self._data_combo.currentText(),
            'stopbits': self._stop_combo.currentText(),
            'parity': self._parity_combo.currentText(),
            'hex_display': self._hex_cb.isChecked(),
            'frame_fields': [
                {
                    'field_type': f.field_type, 'name': f.name, 'value': f.value,
                    'byte_count': f.byte_count, 'is_length': f.is_length,
                    'show_panel': f.show_panel, 'big_endian': f.big_endian,
                    'convert_type': f.convert_type,
                }
                for f in self._frame_fields
            ],
        }
        try:
            with open(self._config_path, 'w') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_config(self):
        try:
            if not os.path.exists(self._config_path):
                return
            with open(self._config_path) as f:
                data = json.load(f)
            saved_port = data.get('port', '')
            if saved_port:
                idx = self._port_combo.findData(saved_port)
                if idx < 0:
                    self._port_combo.insertItem(0, f'{saved_port} (已保存)', saved_port)
                    idx = 0
                if idx >= 0:
                    self._port_combo.setCurrentIndex(idx)
            for key in ['baudrate']:
                v = str(data.get(key, ''))
                if v:
                    idx = getattr(self, f'_baud_combo').findText(v)
                    if idx >= 0: getattr(self, f'_baud_combo').setCurrentIndex(idx)
            self._hex_cb.setChecked(data.get('hex_display', True))
            # 恢复帧字段
            ff_data = data.get('frame_fields', [])
            if ff_data:
                from metabci.brainviz.frame_field import FrameField
                self._frame_fields = []
                for fd in ff_data:
                    f = FrameField(
                        field_type=fd.get('field_type', '1Byte'),
                        name=fd.get('name', '未命名'),
                        byte_count=fd.get('byte_count', 1),
                        is_length=fd.get('is_length', False),
                        show_panel=fd.get('show_panel', True),
                        big_endian=fd.get('big_endian', False),
                        convert_type=fd.get('convert_type', 'Hex'),
                    )
                    f.value = fd.get('value', '')
                    self._frame_fields.append(f)
        except Exception:
            pass

    def _on_ok(self):
        self._save_config()
        self.config_changed.emit(self.get_config())
        self.accept()

    def _on_cancel(self):
        self._save_config()
        self.reject()

    def closeEvent(self, event):
        self._save_config()
        super().closeEvent(event)

    def get_config(self) -> dict:
        return {
            'port': self._port_combo.currentData() or '',
            'baudrate': int(self._baud_combo.currentText()),
            'bytesize': int(self._data_combo.currentText()),
            'stopbits': float(self._stop_combo.currentText()),
            'parity': self._parity_combo.currentText(),
            'hex_display': self._hex_cb.isChecked(),
        }
