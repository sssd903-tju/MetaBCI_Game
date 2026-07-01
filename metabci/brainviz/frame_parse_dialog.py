# -*- coding: utf-8 -*-
"""
帧解析配置器 — 串口数据帧拆解规则配置
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QStackedWidget, QFormLayout, QComboBox, QLineEdit, QCheckBox,
    QFrame, QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from metabci.brainviz.frame_field import FrameField, CONVERT_TYPES
from metabci.brainviz.theme import TEXT, TEXT2, TEXT3, ACCENT, SURFACE, SURFACE2, BORDER, BG


FIELD_TYPES = [
    '帧头', '帧序号', '帧ID', '帧长度',
    '1Byte', '2Byte', '3Byte', '4Byte', '8Byte',
    '校验', '帧尾',
]

L_TAG_STYLE = 'background:#E9B8BD;color:#fff;border-radius:5px;padding:2px 6px;font-size:10px;font-weight:bold;'


class FrameParseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('接收格式解析')
        self.resize(1200, 900)
        self.setMinimumSize(900, 650)
        self._fields: list[FrameField] = []
        self._current_index = -1
        self._setup()
        self._on_select(-1)

    # ============================================================
    # UI
    # ============================================================

    def _setup(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16); root.setSpacing(12)

        # —— 顶部标题 ——
        title_row = QHBoxLayout()
        title = QLabel('添加字段')
        title.setFont(QFont('sans-serif', 18, QFont.Weight.Bold))
        title.setStyleSheet(f'color:{TEXT};')
        title_row.addWidget(title)
        desc = QLabel('（点击对应按钮添加需要的字段）')
        desc.setStyleSheet(f'color:{TEXT3};font-size:13px;')
        title_row.addWidget(desc)
        title_row.addStretch()
        root.addLayout(title_row)

        # —— 按钮区 (11个字段类型按钮) ——
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        for ft in FIELD_TYPES:
            btn = QPushButton(ft)
            btn.setFixedHeight(42); btn.setMinimumWidth(75)
            btn.setStyleSheet(f"""
                QPushButton {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:4px; font-size:13px; }}
                QPushButton:hover {{ background:{SURFACE2}; }}
                QPushButton:pressed {{ background:#DCDCDC; }}
            """)
            btn.clicked.connect(lambda checked, t=ft: self._add_field(t))
            btn_row.addWidget(btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # —— 主体: 左侧字段列表 (63%) + 右侧属性 (37%) ——
        body = QHBoxLayout(); body.setSpacing(12)

        # 左侧
        left = QWidget()
        left_layout = QHBoxLayout(left); left_layout.setContentsMargins(0,0,0,0); left_layout.setSpacing(4)

        # 左侧工具按钮 (▲ ▼ 复制)
        tool_col = QVBoxLayout(); tool_col.setSpacing(4)
        for text, slot in [('上移', self._move_up), ('下移', self._move_down), ('复制', self._copy_field)]:
            btn = QPushButton(text)
            btn.setStyleSheet(f'padding:4px 6px;font-size:11px;background:{SURFACE};border:1px solid {BORDER};border-radius:4px;')
            btn.clicked.connect(slot)
            tool_col.addWidget(btn)
        tool_col.addStretch()
        left_layout.addLayout(tool_col)

        # 字段列表 Table
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(['序号', '字段名', '值', ''])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 45)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(3, 50)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet(f'QTableWidget{{background:{SURFACE};border:1px solid {BORDER};border-radius:6px;gridline-color:{BORDER};}}')
        self._table.cellClicked.connect(self._on_table_click)
        self._table.currentCellChanged.connect(lambda r, c, pr, pc: self._on_select(r))
        left_layout.addWidget(self._table)
        body.addWidget(left, 63)

        # 右侧
        right = QWidget()
        right_layout = QVBoxLayout(right); right_layout.setContentsMargins(0,0,0,0); right_layout.setSpacing(8)

        prop_title = QLabel('字段属性设置')
        prop_title.setFont(QFont('sans-serif', 16, QFont.Weight.Bold))
        prop_title.setStyleSheet(f'color:{TEXT};')
        right_layout.addWidget(prop_title)

        self._prop_stack = QStackedWidget()

        # 属性页1: 普通字段
        pg_normal = QWidget()
        nf = QFormLayout(pg_normal); nf.setSpacing(10)
        nf.setContentsMargins(8, 8, 8, 8)

        self._convert_combo = QComboBox()
        for ct in CONVERT_TYPES: self._convert_combo.addItem(ct)
        self._convert_combo.currentTextChanged.connect(self._on_prop_changed)
        nf.addRow('数据转换:', self._convert_combo)

        self._name_edit = QLineEdit('未命名')
        self._name_edit.textChanged.connect(self._on_prop_changed)
        nf.addRow('数据名称:', self._name_edit)

        self._endian_cb = QCheckBox('高字节在前')
        self._endian_cb.toggled.connect(self._on_prop_changed)
        nf.addRow('字节顺序:', self._endian_cb)

        self._show_cb = QCheckBox('显示到面板')
        self._show_cb.setChecked(True)
        self._show_cb.toggled.connect(self._on_prop_changed)
        nf.addRow('面板显示:', self._show_cb)

        self._prop_stack.addWidget(pg_normal)

        # 属性页2: 长度字段
        pg_length = QWidget()
        lf = QFormLayout(pg_length); lf.setSpacing(10)
        lf.setContentsMargins(8, 8, 8, 8)

        self._len_combo = QComboBox()
        for i in range(1, 9): self._len_combo.addItem(str(i))
        self._len_combo.currentTextChanged.connect(self._on_prop_changed)
        lf.addRow('字节数设置:', self._len_combo)

        self._len_show_cb = QCheckBox('显示到面板')
        self._len_show_cb.setChecked(True)
        self._len_show_cb.toggled.connect(self._on_prop_changed)
        lf.addRow('面板显示:', self._len_show_cb)

        self._prop_stack.addWidget(pg_length)

        right_layout.addWidget(self._prop_stack)
        right_layout.addStretch()
        body.addWidget(right, 37)

        root.addLayout(body, 1)

        # —— 确认/取消 ——
        from PySide6.QtWidgets import QDialogButtonBox
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ============================================================
    # 字段操作
    # ============================================================

    def _add_field(self, field_type: str):
        f = FrameField(field_type=field_type)
        self._fields.append(f)
        self._refresh_table()
        self._table.selectRow(len(self._fields) - 1)
        self._on_select(len(self._fields) - 1)

    def _move_up(self):
        if self._current_index > 0:
            self._fields[self._current_index], self._fields[self._current_index - 1] = \
                self._fields[self._current_index - 1], self._fields[self._current_index]
            self._current_index -= 1
            self._refresh_table()
            self._table.selectRow(self._current_index)

    def _move_down(self):
        if 0 <= self._current_index < len(self._fields) - 1:
            self._fields[self._current_index], self._fields[self._current_index + 1] = \
                self._fields[self._current_index + 1], self._fields[self._current_index]
            self._current_index += 1
            self._refresh_table()
            self._table.selectRow(self._current_index)

    def _copy_field(self):
        if self._current_index >= 0:
            f = self._fields[self._current_index]
            new_f = FrameField(
                field_type=f.field_type, name=f.name, byte_count=f.byte_count,
                is_length=f.is_length, show_panel=f.show_panel,
                big_endian=f.big_endian, convert_type=f.convert_type,
            )
            self._fields.insert(self._current_index + 1, new_f)
            self._current_index += 1
            self._refresh_table()
            self._table.selectRow(self._current_index)

    def _delete_field(self, index: int):
        if 0 <= index < len(self._fields):
            del self._fields[index]
            self._refresh_table()
            self._on_select(-1)

    # ============================================================
    # Table 刷新
    # ============================================================

    def _refresh_table(self):
        self._table.setRowCount(0)
        for i, f in enumerate(self._fields):
            self._table.insertRow(i)
            # 序号
            idx_item = QTableWidgetItem(str(i))
            idx_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(i, 0, idx_item)

            # 字段名 (带 L 标签)
            name_w = QWidget()
            name_w.setStyleSheet('background:transparent;')
            nl = QHBoxLayout(name_w); nl.setContentsMargins(4,0,4,0); nl.setSpacing(6)
            nl.addWidget(QLabel(f.field_type))
            if f.is_length:
                l_tag = QLabel('L')
                l_tag.setStyleSheet(L_TAG_STYLE)
                nl.addWidget(l_tag)
            nl.addStretch()
            self._table.setCellWidget(i, 1, name_w)

            # 值 (限制输入)
            val_edit = QLineEdit(f.value)
            val_edit.setFont(QFont('Menlo', 12))
            val_edit.setMaxLength(f.byte_count * 3)  # "AA BB CC" = 字节数×3
            val_edit.setStyleSheet(f'border:none;background:transparent;color:{TEXT};')
            val_edit.textEdited.connect(lambda v, idx=i: self._on_value_edited(idx, v))
            self._table.setCellWidget(i, 2, val_edit)

            # 删除按钮
            del_btn = QPushButton('删')
            del_btn.setStyleSheet(f'padding:2px 6px;font-size:11px;background:{SURFACE2};border:1px solid {BORDER};border-radius:4px;color:#C4665A;')
            del_btn.clicked.connect(lambda checked, idx=i: self._delete_field(idx))
            del_w = QWidget(); dl = QHBoxLayout(del_w); dl.setContentsMargins(0,0,0,0)
            dl.addWidget(del_btn, 0, Qt.AlignmentFlag.AlignCenter)
            self._table.setCellWidget(i, 3, del_w)

            self._table.setRowHeight(i, 44)

    def _on_value_edited(self, index: int, text: str):
        """实时过滤：只允许 hex 字符和空格，每个字节最多2字符"""
        # 过滤非法字符
        filtered = ''.join(c.upper() for c in text if c.upper() in '0123456789ABCDEF ')
        # 限制每个 hex 组最多2字符
        parts = filtered.split()
        constrained_parts = []
        for p in parts:
            constrained_parts.append(p[:2])
        result = ' '.join(constrained_parts)
        # 如果过滤后变了，更新 editor
        if result != text:
            editor = self._table.cellWidget(index, 2)
            if editor and isinstance(editor, QLineEdit):
                cursor_pos = editor.cursorPosition()
                editor.blockSignals(True)
                editor.setText(result)
                editor.setCursorPosition(min(cursor_pos, len(result)))
                editor.blockSignals(False)
        # 保存
        if 0 <= index < len(self._fields):
            self._fields[index].value = result

    def _on_value_changed(self, index: int, value: str):
        if 0 <= index < len(self._fields):
            self._fields[index].value = value

    def _on_table_click(self, row: int, col: int):
        self._on_select(row)

    # ============================================================
    # 右侧属性
    # ============================================================

    def _on_select(self, index: int):
        self._current_index = index
        if index < 0 or index >= len(self._fields):
            self._prop_stack.setEnabled(False)
            return
        self._prop_stack.setEnabled(True)
        f = self._fields[index]
        is_special = f.field_type in ('帧头', '帧尾')

        if f.is_length or is_special:
            # 长度字段 / 帧头/帧尾 → 字节数设置
            self._prop_stack.setCurrentIndex(1)
            self._len_combo.blockSignals(True)
            self._len_combo.setCurrentText(str(f.byte_count))
            self._len_combo.blockSignals(False)
            self._len_show_cb.blockSignals(True)
            self._len_show_cb.setChecked(f.show_panel)
            self._len_show_cb.blockSignals(False)
        else:
            self._prop_stack.setCurrentIndex(0)
            self._convert_combo.blockSignals(True)
            self._convert_combo.setCurrentText(f.convert_type)
            self._convert_combo.blockSignals(False)
            self._name_edit.blockSignals(True)
            self._name_edit.setText(f.name)
            self._name_edit.blockSignals(False)
            self._endian_cb.blockSignals(True)
            self._endian_cb.setChecked(f.big_endian)
            self._endian_cb.blockSignals(False)
            self._show_cb.blockSignals(True)
            self._show_cb.setChecked(f.show_panel)
            self._show_cb.blockSignals(False)

    def _on_prop_changed(self):
        if self._current_index < 0 or self._current_index >= len(self._fields):
            return
        f = self._fields[self._current_index]
        is_special = f.field_type in ('帧头', '帧尾')
        if f.is_length or is_special:
            old_bc = f.byte_count
            f.byte_count = int(self._len_combo.currentText())
            f.show_panel = self._len_show_cb.isChecked()
            # 字节数变了 → 立即约束值并刷新表格
            if f.byte_count != old_bc:
                f.value = f.constrain_value()
                self._refresh_table()
                self._table.selectRow(self._current_index)
        else:
            f.convert_type = self._convert_combo.currentText()
            f.name = self._name_edit.text()
            f.big_endian = self._endian_cb.isChecked()
            f.show_panel = self._show_cb.isChecked()

    # ============================================================
    # 导出
    # ============================================================

    def get_fields(self) -> list[FrameField]:
        return self._fields
