# -*- coding: utf-8 -*-
"""
数据中心 — 实验文件浏览 + 回放（回放查看器待完善）
"""

import os, json, time
import numpy as np
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QSlider, QGroupBox, QSplitter,
)
from PySide6.QtCore import Qt

from metabci.brainviz.theme import TEXT, TEXT2, TEXT3, ACCENT, SURFACE, BORDER, GREEN

DATA_DIR = os.path.expanduser('~/MetaBCI_Recordings')


class DataCenterPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self._mw = main_window
        os.makedirs(DATA_DIR, exist_ok=True)
        self._setup()

    def _setup(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 12); layout.setSpacing(12)

        title = QLabel('数据中心'); title.setObjectName('pageTitle')
        layout.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # —— 左: 文件列表 ——
        left = QWidget()
        ll = QVBoxLayout(left); ll.setContentsMargins(0,0,0,0); ll.setSpacing(8)

        files_group = QGroupBox('实验记录')
        fl = QVBoxLayout(files_group)
        self._file_list = QListWidget()
        self._file_list.setStyleSheet(f'background:{SURFACE};border:1px solid {BORDER};border-radius:4px;')
        self._file_list.currentItemChanged.connect(self._on_select)
        self._refresh_files()
        fl.addWidget(self._file_list)

        btns = QHBoxLayout()
        for text, slot in [('导入', self._import), ('删除', self._delete), ('导出 npy', lambda: self._export('npy')), ('导出 csv', lambda: self._export('csv'))]:
            btn = QPushButton(text); btn.setStyleSheet('padding:4px 10px;font-size:11px;')
            btn.clicked.connect(slot); btns.addWidget(btn)
        btns.addStretch()
        fl.addLayout(btns)
        ll.addWidget(files_group)
        splitter.addWidget(left)

        # —— 右: 回放查看器 ——
        right = QWidget()
        rl = QVBoxLayout(right); rl.setContentsMargins(0,0,0,0); rl.setSpacing(10)

        # 文件信息
        self._info_label = QLabel('选择一个实验记录')
        self._info_label.setStyleSheet(f'color:{TEXT2};font-size:13px;padding:8px;background:{SURFACE};border-radius:6px;')
        rl.addWidget(self._info_label)

        # 回放进度
        self._pb_slider = QSlider(Qt.Orientation.Horizontal)
        self._pb_slider.setRange(0, 1000)
        self._pb_slider.setEnabled(False)
        rl.addWidget(self._pb_slider)

        self._pb_time = QLabel('--:-- / --:--')
        self._pb_time.setStyleSheet(f'color:{TEXT3};')
        rl.addWidget(self._pb_time)

        # 回放查看器占位 (后续添加波形+频谱+事件轴)
        viewer = QLabel('回放查看器\n— 波形 / 频谱 / 事件时间轴 —\n待实现')
        viewer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        viewer.setStyleSheet(f'color:{TEXT3};font-size:14px;background:{SURFACE};border:1px dashed {BORDER};border-radius:8px;padding:60px;')
        rl.addWidget(viewer, 1)

        splitter.addWidget(right)
        splitter.setSizes([320, 600])
        layout.addWidget(splitter, 1)

    # ============================================================
    # 文件管理
    # ============================================================

    def _refresh_files(self):
        self._file_list.clear()
        for dname in sorted(os.listdir(DATA_DIR), reverse=True):
            dpath = os.path.join(DATA_DIR, dname)
            if not os.path.isdir(dpath): continue
            meta_path = os.path.join(dpath, 'meta.json')
            info = dname
            if os.path.exists(meta_path):
                try:
                    with open(meta_path) as f:
                        m = json.load(f)
                    info = f"{m.get('paradigm','?')} · {m.get('duration',0):.0f}s · {m.get('n_channels',0)}ch · {dname[:8]}"
                except Exception: pass
            self._file_list.addItem(info)

    def _on_select(self, item: QListWidgetItem | None, _=None):
        if item is None: return
        dname = item.text().split(' · ')[-1] if ' · ' in item.text() else item.text()
        dpath = os.path.join(DATA_DIR, dname)
        meta_path = os.path.join(dpath, 'meta.json')
        if os.path.exists(meta_path):
            try:
                with open(meta_path) as f:
                    m = json.load(f)
                self._info_label.setText(
                    f"范式: {m.get('paradigm','?')}  |  "
                    f"时长: {m.get('duration',0):.0f}s  |  "
                    f"通道: {m.get('n_channels',0)}  |  "
                    f"采样率: {m.get('srate',0)}Hz  |  "
                    f"日期: {m.get('date','?')}"
                )
            except Exception: pass

    def _delete(self):
        item = self._file_list.currentItem()
        if item is None: return
        dname = item.text().split(' · ')[-1] if ' · ' in item.text() else item.text()
        dpath = os.path.join(DATA_DIR, dname)
        if os.path.isdir(dpath):
            import shutil; shutil.rmtree(dpath)
        self._refresh_files()

    def _import(self):
        fpath, _ = QFileDialog.getOpenFileName(self, '导入', '', 'NumPy (*.npy);;All (*)')
        if not fpath: return
        try:
            data = np.load(fpath)
            tstamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            dpath = os.path.join(DATA_DIR, f'imported_{tstamp}')
            os.makedirs(dpath, exist_ok=True)
            np.save(os.path.join(dpath, 'raw.npy'), data)
            meta = {'srate': 250, 'n_channels': data.shape[1] if data.ndim > 1 else 1,
                    'duration': data.shape[0] / 250, 'samples': data.shape[0],
                    'date': tstamp, 'paradigm': 'imported'}
            with open(os.path.join(dpath, 'meta.json'), 'w') as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            self._refresh_files()
        except Exception as e:
            QMessageBox.critical(self, '导入失败', str(e))

    def _export(self, fmt: str):
        item = self._file_list.currentItem()
        if item is None: return
        dname = item.text().split(' · ')[-1] if ' · ' in item.text() else item.text()
        dpath = os.path.join(DATA_DIR, dname)
        raw_path = os.path.join(dpath, 'raw.npy')
        if not os.path.exists(raw_path):
            QMessageBox.warning(self, '提示', '没有原始数据文件')
            return
        dest, _ = QFileDialog.getSaveFileName(self, f'导出 {fmt.upper()}', dname, f'{fmt.upper()} (*.{fmt})')
        if not dest: return
        data = np.load(raw_path)
        if fmt == 'csv':
            header = ','.join(f'Ch{ch+1}' for ch in range(data.shape[1]))
            np.savetxt(dest, data, delimiter=',', header=header, comments='')
        elif fmt == 'npy':
            np.save(dest, data)
        QMessageBox.information(self, '导出成功', f'已导出: {dest}')
