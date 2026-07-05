# -*- coding: utf-8 -*-
"""
在线实验室 — 实时脑电监测 (LSL / 串口双模式)
"""

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QComboBox, QProgressBar, QGridLayout, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from metabci.brainviz.theme import (
    TEXT, TEXT2, TEXT3, ACCENT, SURFACE, SURFACE2, BORDER, GREEN, RED,
)
from metabci.brainviz.config import WAVEFORM_SECONDS, BANDS, BAND_COLORS
# [MetaBCI] EEGBuffer — ring buffer shared with brainflow LSL pipeline
from metabci.brainviz.data_buffer import EEGBuffer
# [MetaBCI] LiveWorker — follows brainflow.ProcessWorker pre/consume/post
from metabci.brainviz.live_worker import LiveWorker
from metabci.brainviz.widgets.science_card import ScienceCard


# [MetaBCI] 模块级 SSVEP 解码日志（供训练中心读取准确率）
_ssvep_decode_log: list = []


class LiveLabPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self._mw = main_window
        self._buffer = None; self._inlet = None
        self._thread = None; self._worker = None
        self._srate = 250.0; self._n_channels = 8
        self._paradigm_id = 'focus'; self._wave_paused = False
        self._recording = False; self._record_start = 0.0
        self._mode_lsl = True
        self._band_bars = {}; self._band_vals = {}
        # [MetaBCI] P300 解码器 + 桥接游戏事件
        self._p300_decoder = None
        main_window.game_bridge.game_event.connect(self._on_bridge_game_event)
        # 定时同步范式（即使用户不在本页面也能切换解码）
        from PySide6.QtCore import QTimer
        self._para_timer = QTimer(self)
        self._para_timer.timeout.connect(self._sync_paradigm)
        self._para_timer.start(1000)
        self._setup(); self._scan_devices()

    def showEvent(self, event):
        super().showEvent(event); self._sync_paradigm()
        self._wave_plot.update()
        # 不再 resume/pause — worker 始终运行以保证游戏数据不断

    def _sync_paradigm(self):
        para = self._mw.current_paradigm
        if para is None:
            para = type('obj', (object,), {'paradigm_id': 'focus', 'name': '专注度检测',
                'result_label': '检测结果', 'active_electrodes': [], 'science': {}})()

        # 通道名: 优先帧格式(串口) > LSL实际通道数 > 范式电极
        ch_names = self._get_frame_channel_names()
        if not ch_names:
            # LSL/串口模式用实际通道数, 不受范式电极数限制
            ch_names = [f'Ch{i}' for i in range(self._n_channels)]
        old_names = [self._ch_combo.itemText(i) for i in range(self._ch_combo.count())]
        if ch_names != old_names:
            current = self._ch_combo.currentText()
            self._ch_combo.blockSignals(True)
            self._ch_combo.clear()
            for name in ch_names:
                self._ch_combo.addItem(name)
            # 恢复之前的选择
            if current and current in ch_names:
                self._ch_combo.setCurrentText(current)
            self._ch_combo.blockSignals(False)

        if hasattr(para, 'result_label'):
            self._result_title.setText(para.result_label)
        if self._worker and hasattr(para, 'paradigm_id'):
            self._worker.set_paradigm(para.paradigm_id)
            self._paradigm_id = para.paradigm_id
        self._science.set_content(f'{para.name} · 实时监测', para.science.get('signal', ''))

    def _get_frame_channel_names(self):
        """从已保存的帧格式配置中读取通道名称和数量"""
        import json, os
        try:
            config_path = os.path.expanduser('~/.metabci_serial_config.json')
            if os.path.exists(config_path):
                with open(config_path) as f:
                    cfg = json.load(f)
                names = []
                for fd in cfg.get('frame_fields', []):
                    if fd.get('show_panel', True) and fd.get('field_type') not in ('帧头', '帧尾', '校验'):
                        name = fd.get('name', '')
                        if name and name != '未命名':
                            names.append(name)
                        else:
                            names.append(fd.get('field_type', 'Ch'))
                return names
        except Exception:
            pass
        return []

    # ============================================================
    # UI
    # ============================================================

    def _setup(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 12); layout.setSpacing(12)

        # —— 标题 + 模式切换 + 设备控制 ——
        h = QHBoxLayout()
        title = QLabel('在线实验室'); title.setObjectName('pageTitle'); h.addWidget(title)
        h.addStretch()

        # 串口设置 (仅串口模式可见, 在设备下拉框左侧)
        self._ser_cfg = QPushButton('设置')
        self._ser_cfg.setToolTip('串口参数设置')
        self._ser_cfg.clicked.connect(self._open_serial); self._ser_cfg.setVisible(False)
        h.addWidget(self._ser_cfg)

        self._dev_combo = QComboBox(); self._dev_combo.setMinimumWidth(240); h.addWidget(self._dev_combo)

        self._scan_btn = QPushButton('扫描'); self._scan_btn.clicked.connect(self._scan_devices)
        h.addWidget(self._scan_btn)

        self._mode_btn = QPushButton('串口')
        self._mode_btn.setStyleSheet(f'background:#f59e0b;color:#fff;font-weight:bold;padding:6px 12px;border-radius:4px;border:none;')
        self._mode_btn.clicked.connect(self._toggle_mode)
        h.addWidget(self._mode_btn)

        self._conn_btn = QPushButton('连接')
        self._conn_btn.setStyleSheet(f'background:{GREEN};color:#fff;font-weight:bold;padding:6px 14px;border-radius:4px;border:none;')
        self._conn_btn.clicked.connect(self._toggle); h.addWidget(self._conn_btn)
        layout.addLayout(h)

        # —— 2×2 网格 ——
        grid = QGridLayout(); grid.setSpacing(10)

        # 波形
        wave_card, wl, wave_title = self._card('实时波形')
        tr = QHBoxLayout(); tr.addWidget(wave_title); tr.addStretch()
        btn_s = 'padding:2px 8px;font-size:11px;'
        self._show_preproc = False
        self._preproc_btn = QPushButton('原始'); self._preproc_btn.setStyleSheet(btn_s)
        self._preproc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preproc_btn.clicked.connect(self._toggle_preproc_view); tr.addWidget(self._preproc_btn)

        self._pause_btn = QPushButton('暂停'); self._pause_btn.setStyleSheet(btn_s)
        self._pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pause_btn.clicked.connect(self._toggle_pause); tr.addWidget(self._pause_btn)
        reset_btn = QPushButton('重置'); reset_btn.setStyleSheet(btn_s)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self._reset_wave); tr.addWidget(reset_btn)

        clear_btn = QPushButton('清除'); clear_btn.setStyleSheet(btn_s)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_wave)
        tr.addWidget(clear_btn)

        # [MetaBCI] 基线校准按钮 (专注度检测)
        self._baseline_btn = QPushButton('基线校准')
        self._baseline_btn.setStyleSheet('padding:2px 10px;font-size:11px;background:#4CAF50;color:#fff;border:none;border-radius:3px;')
        self._baseline_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._baseline_btn.setToolTip('采集10秒基线: 请保持放松状态后点击')
        self._baseline_btn.clicked.connect(self._start_baseline)
        self._baseline_status = QLabel('')
        self._baseline_status.setStyleSheet(f'color:{TEXT3};font-size:10px;border:none;')
        tr.addWidget(self._baseline_btn)
        tr.addWidget(self._baseline_status)

        wl.replaceWidget(wave_title, QWidget()); wl.insertLayout(0, tr)
        wl.setContentsMargins(8, 4, 8, 8)

        self._wave_plot = pg.PlotWidget()
        self._wave_plot.setBackground('w')
        for ax in ['left', 'bottom']: self._wave_plot.getAxis(ax).setPen('#aaa')
        self._wave_plot.showGrid(x=True, y=True, alpha=0.15)
        self._wave_plot.enableAutoRange(axis='y')
        self._wave_plot.setXRange(0, WAVEFORM_SECONDS)
        self._wave_curve = self._wave_plot.plot(pen=pg.mkPen(color=ACCENT, width=1.2))
        self._wave_plot.sigRangeChanged.connect(self._on_range_changed)
        wl.addWidget(self._wave_plot)
        # 通道 + 心率 + 录制 同一行
        bot_row = QHBoxLayout()
        self._ch_combo = QComboBox(); self._ch_combo.setFixedWidth(100)
        self._ch_combo.currentIndexChanged.connect(self._on_channel_changed)
        bot_row.addWidget(self._ch_combo)

        self._hr_label = QLabel('')
        self._hr_label.setStyleSheet('color:#E91E63;font-weight:bold;font-size:13px;border:none;')
        bot_row.addWidget(self._hr_label)

        bot_row.addStretch()
        self._rec_btn = QPushButton('● 录制'); self._rec_btn.setStyleSheet(btn_s)
        self._rec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rec_btn.clicked.connect(self._toggle_recording)
        bot_row.addWidget(self._rec_btn)
        self._rec_status = QLabel('')
        self._rec_status.setStyleSheet(f'color:{TEXT3};font-size:10px;border:none;')
        bot_row.addWidget(self._rec_status)
        wl.addLayout(bot_row)

        grid.addWidget(wave_card, 0, 0)

        # 频谱
        spec_card, sl, spec_title = self._card('频谱图')
        spec_tr = QHBoxLayout(); spec_tr.addWidget(spec_title); spec_tr.addStretch()
        spec_reset = QPushButton('重置'); spec_reset.setStyleSheet(btn_s)
        spec_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        spec_reset.clicked.connect(lambda: (
            self._spec_curve.clear(),
            self._spec_plot.setXRange(0, 100),
            self._spec_plot.setLogMode(x=False, y=True),
            self._spec_plot.enableAutoRange(axis='y')
        ))
        spec_tr.addWidget(spec_reset)
        sl.replaceWidget(spec_title, QWidget()); sl.insertLayout(0, spec_tr)
        sl.setContentsMargins(8, 4, 8, 8)

        self._spec_plot = pg.PlotWidget(); self._spec_plot.setBackground('w')
        for ax in ['left', 'bottom']: self._spec_plot.getAxis(ax).setPen('#aaa')
        self._spec_plot.showGrid(x=True, y=True, alpha=0.15)
        self._spec_plot.setXRange(0, 100); self._spec_plot.setLogMode(x=False, y=True)
        self._spec_curve = self._spec_plot.plot(pen=pg.mkPen(color=ACCENT, width=1.5))
        for bn, (lo, hi) in BANDS.items():
            r = pg.LinearRegionItem(values=[lo, hi], orientation='vertical', brush=(200,200,200,30), movable=False)
            r.setZValue(-10); self._spec_plot.addItem(r)
        sl.addWidget(self._spec_plot); grid.addWidget(spec_card, 0, 1)

        # 结果
        class_card, cl, _ = self._card(''); self._result_title = class_card.findChild(QLabel)
        self._result_title.setText('检测结果'); cl.setContentsMargins(16, 16, 16, 16)
        self._result_val = QLabel('--')
        self._result_val.setFont(QFont('sans-serif', 48, QFont.Weight.Bold))
        self._result_val.setStyleSheet(f'color:{ACCENT};border:none;background:transparent;')
        self._result_val.setAlignment(Qt.AlignmentFlag.AlignCenter); cl.addWidget(self._result_val)
        self._result_bar = QProgressBar(); self._result_bar.setRange(0,100)
        self._result_bar.setValue(0); self._result_bar.setTextVisible(False); self._result_bar.setFixedHeight(10)
        cl.addWidget(self._result_bar)
        self._result_detail = QLabel('')
        self._result_detail.setFont(QFont('sans-serif', 12))
        self._result_detail.setStyleSheet(f'color:{TEXT2};border:none;background:transparent;')
        self._result_detail.setAlignment(Qt.AlignmentFlag.AlignCenter); cl.addWidget(self._result_detail)
        grid.addWidget(class_card, 1, 0)

        # 频带
        band_card, bl, _ = self._card('频带能量'); bl.setContentsMargins(16, 12, 16, 12); bl.setSpacing(6)
        bl.addWidget(QLabel('δ · θ · α · β · γ'))
        for bn in BANDS:
            row = QHBoxLayout()
            lbl = QLabel(bn); lbl.setFixedWidth(60)
            lbl.setStyleSheet(f'color:{BAND_COLORS.get(bn,"#888")};font-weight:600;font-size:12px;border:none;background:transparent;')
            row.addWidget(lbl)
            bar = QProgressBar(); bar.setRange(0,100); bar.setValue(0); bar.setTextVisible(False); bar.setFixedHeight(7)
            bar.setStyleSheet(f'QProgressBar{{background:{SURFACE2};border:none;border-radius:3px;}}QProgressBar::chunk{{background:{BAND_COLORS.get(bn,"#888")};border-radius:3px;}}')
            row.addWidget(bar)
            val = QLabel('--'); val.setFixedWidth(40); val.setFont(QFont('Menlo',10))
            val.setStyleSheet(f'color:{TEXT2};border:none;background:transparent;'); row.addWidget(val)
            self._band_bars[bn] = bar; self._band_vals[bn] = val; bl.addLayout(row)
        grid.addWidget(band_card, 1, 1)
        grid.setColumnStretch(0,3); grid.setColumnStretch(1,2)
        grid.setRowStretch(0,2); grid.setRowStretch(1,1)
        layout.addLayout(grid, 1)

        # 科普
        self._science = ScienceCard('实时监测', '实时脑电监测中……观察当你放松、专注或紧张时，这些数值如何变化！')
        self._science.setMaximumHeight(160); layout.addWidget(self._science)

    @staticmethod
    def _card(title: str):
        f = QFrame(); f.setObjectName('panel')
        layout = QVBoxLayout(f); layout.setContentsMargins(0,0,0,0); layout.setSpacing(2)
        lbl = QLabel(title); lbl.setFont(QFont('sans-serif', 11, QFont.Weight.Bold))
        lbl.setStyleSheet(f'color:{TEXT};border:none;background:transparent;padding:4px 8px;')
        layout.addWidget(lbl)
        return f, layout, lbl

    # ============================================================
    # 模式切换 + 扫描 + 连接
    # ============================================================

    def _toggle_mode(self):
        self._mode_lsl = not self._mode_lsl
        if self._mode_lsl:
            self._mode_btn.setText('串口')
            self._mode_btn.setStyleSheet(f'background:#f59e0b;color:#fff;font-weight:bold;padding:6px 12px;border-radius:4px;border:none;')
        else:
            self._mode_btn.setText('LSL')
            self._mode_btn.setStyleSheet(f'background:{ACCENT};color:#fff;font-weight:bold;padding:6px 12px;border-radius:4px;border:none;')
        self._ser_cfg.setVisible(not self._mode_lsl)
        if self._inlet or self._thread: self._disconnect()
        self._scan_devices()

    def _scan_devices(self):
        self._dev_combo.clear()
        if self._mode_lsl: self._scan_lsl()
        else: self._scan_serial()

    def _scan_lsl(self):
        try:
            from pylsl import resolve_byprop
            for s in resolve_byprop('type', 'EEG', timeout=2.0):
                self._dev_combo.addItem(f'{s.name()} ({s.channel_count()}ch, {int(s.nominal_srate())}Hz)', ('lsl', s.name()))
            if self._dev_combo.count() == 0: self._dev_combo.addItem('未发现 LSL 设备')
        except Exception: self._dev_combo.addItem('LSL 不可用')

    def _scan_serial(self):
        try:
            from serial.tools import list_ports
            for p in list_ports.comports():
                self._dev_combo.addItem(f'{p.device} — {p.description}', ('serial', p.device))
            if self._dev_combo.count() == 0: self._dev_combo.addItem('未发现串口')
        except Exception: self._dev_combo.addItem('请安装 pyserial')

    def _toggle(self):
        if self._inlet or self._thread: self._disconnect()
        else: self._connect()

    def _connect(self):
        data = self._dev_combo.currentData()
        if not data: QMessageBox.warning(self, '提示', '请先选择设备'); return
        mode, name = data
        if mode == 'lsl': self._connect_lsl(name)
        else: self._connect_serial(name)

    def _connect_lsl(self, name: str):
        try:
            from pylsl import resolve_byprop, StreamInlet; from threading import Thread
            streams = resolve_byprop('name', name, timeout=3.0)
            if not streams: QMessageBox.warning(self, '提示', f'未找到: {name}'); return
            # [MetaBCI] StreamInlet — same as brainflow demos
            self._inlet = StreamInlet(streams[0])
            info = self._inlet.info(); self._srate = info.nominal_srate(); self._n_channels = info.channel_count()
            if self._buffer is None:
                self._buffer = EEGBuffer(n_channels=self._n_channels, srate=self._srate)

            class Pull(Thread):
                def __init__(s,i,b): super().__init__(daemon=True); s.i=i; s.b=b; s.r=True
                def run(s):
                    while s.r:
                        try:
                            c,t = s.i.pull_chunk(timeout=0.1, max_samples=128)
                            if c and len(c)>0: s.b.push(c,t)
                        except Exception: pass
            self._thread = Pull(self._inlet, self._buffer); self._thread.start()
            self._start_worker(); self._sync_paradigm()
            self._set_connected(name, f'{self._n_channels}ch, {int(self._srate)}Hz')
        except Exception as e: QMessageBox.critical(self, '连接失败', str(e))

    def _connect_serial(self, port: str):
        from metabci.brainviz.serial_worker import SerialReader
        try:
            self._srate = 250.0; self._n_channels = 8
            self._buffer = EEGBuffer(n_channels=self._n_channels, srate=self._srate)

            self._thread = SerialReader(
                port=port, baudrate=115200, buffer=self._buffer,
                n_channels=self._n_channels, srate=self._srate,
            )
            self._thread.rx_callback = self._on_serial_rx
            self._thread.start()

            self._start_worker(); self._sync_paradigm()
            self._set_connected(port, f'串口 {self._n_channels}通道')
        except Exception as e:
            QMessageBox.critical(self, '串口连接失败', str(e))

    def _on_serial_rx(self, text: str, is_hex: bool):
        pass  # 后续可显示到接收区

    def _start_worker(self):
        self._worker = LiveWorker(self._buffer)
        # [MetaBCI] 传递脑电通道索引 (排除 ECG)
        eeg_idx = self._get_eeg_channel_indices()
        self._worker.set_eeg_channels(eeg_idx)
        self._worker.waveform_ready.connect(self._on_waveform)
        self._worker.preproc_ready.connect(self._on_preproc)
        self._worker.spectrum_ready.connect(self._on_spectrum)
        self._worker.bands_ready.connect(self._on_bands)
        self._worker.focus_ready.connect(self._on_focus)
        self._worker.ssvep_ready.connect(self._on_ssvep)
        self._worker.p300_ready.connect(self._on_p300)
        self._worker.mi_ready.connect(self._on_mi)
        # [MetaBCI] 转发解码结果到 GameBridge → Godot 游戏
        self._worker.focus_ready.connect(self._forward_focus)
        self._worker.ssvep_ready.connect(self._forward_ssvep)
        self._worker.p300_ready.connect(self._forward_p300)
        self._worker.mi_ready.connect(self._forward_mi)
        # 缓存最近频带功率用于充实 focus 消息
        self._latest_bands = {}
        self._worker.bands_ready.connect(lambda pm: setattr(self, '_latest_bands', pm.copy()))
        # 恢复上次应用的预处理配置
        if hasattr(self, '_saved_preproc_config') and self._saved_preproc_config:
            self._worker.set_preproc(self._saved_preproc_config)
        self._worker.start()

    def _get_eeg_channel_indices(self) -> list[int]:
        """从帧格式读取通道名，返回非 ECG 的脑电通道索引"""
        names = self._get_frame_channel_names()
        if not names:
            return list(range(self._buffer.n_channels)) if self._buffer else [0, 1]
        eeg_idx = []
        for i, name in enumerate(names):
            if 'ECG' not in name.upper() and '心电' not in name:
                eeg_idx.append(i)
        return eeg_idx if eeg_idx else [0, 1]  # 全是 ECG 则 fallback

    def _set_connected(self, name, info):
        self._conn_btn.setText('断开')
        self._conn_btn.setStyleSheet(f'background:{RED};color:#fff;font-weight:bold;padding:6px 14px;border-radius:4px;border:none;')
        self._mw._device_status.setText(f'● {name} ({info})')
        self._mw._device_status.setStyleSheet(f'font-size:12px;color:{GREEN};padding:12px 8px;border-top:1px solid {BORDER};')

    def _disconnect(self):
        if self._worker: self._worker.stop(); self._worker.wait(1000); self._worker = None
        if self._thread:
            if hasattr(self._thread, 'stop'): self._thread.stop()
            elif hasattr(self._thread, 'r'): self._thread.r = False
            self._thread = None
        self._inlet = None
        # 保留 _buffer 不清空，重连后继续绘制
        self._conn_btn.setText('连接')
        self._conn_btn.setStyleSheet(f'background:{GREEN};color:#fff;font-weight:bold;padding:6px 14px;border-radius:4px;border:none;')
        self._mw._device_status.setText('○ 未连接')
        self._mw._device_status.setStyleSheet(f'font-size:12px;color:{TEXT2};padding:12px 8px;border-top:1px solid {BORDER};')

    def _open_serial(self):
        from metabci.brainviz.serial_dialog import SerialDialog
        if hasattr(self, '_serial_dlg') and self._serial_dlg and self._serial_dlg.isVisible():
            self._serial_dlg.raise_()
            return
        port = self._dev_combo.currentData()[1] if self._dev_combo.currentData() else ''
        dlg = SerialDialog(self, current_port=port)
        dlg.config_changed.connect(self._on_serial_config)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        dlg.show()  # 非模态，保持打开接收数据
        self._serial_dlg = dlg

    def _on_serial_data(self, text: str, is_hex: bool):
        """接收串口数据 → 转发到设置界面接收区(如果打开)"""
        if hasattr(self, '_serial_dlg') and self._serial_dlg and self._serial_dlg.isVisible():
            self._serial_dlg.append_rx(text, is_hex)

    def _on_serial_config(self, cfg: dict):
        """串口设置确认后同步主界面"""
        port = cfg['port']
        if port:
            idx = self._dev_combo.findData(('serial', port))
            if idx < 0:
                self._dev_combo.insertItem(0, f'{port} — 串口', ('serial', port))
                idx = 0
            self._dev_combo.setCurrentIndex(idx)
        # 立即更新通道名
        self._sync_paradigm()

    def _connect_serial(self, port: str):
        import json, os, logging
        from metabci.brainviz.serial_worker import SerialReader
        from metabci.brainviz.frame_field import FrameField
        _log = logging.getLogger("brainviz")
        config_path = os.path.expanduser('~/.metabci_serial_config.json')
        baud = 115200; frame_fields = []
        try:
            if os.path.exists(config_path):
                with open(config_path) as f:
                    cfg = json.load(f)
                baud = int(cfg.get('baudrate', 115200))
                for fd in cfg.get('frame_fields', []):
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
                    frame_fields.append(f)
                _log.info(f"加载帧格式: {len(frame_fields)} 字段")
        except Exception as e:
            _log.error(f"加载帧格式失败: {e}")

        try:
            self._srate = 250.0; self._n_channels = 8
            if self._buffer is None:
                self._buffer = EEGBuffer(n_channels=self._n_channels, srate=self._srate)
            else:
                self._buffer.srate = self._srate
            self._thread = SerialReader(port=port, baudrate=baud, buffer=self._buffer,
                                        n_channels=self._n_channels, srate=self._srate,
                                        frame_fields=frame_fields)
            self._thread.rx_callback = self._on_serial_data
            self._thread.start()
            self._start_worker(); self._sync_paradigm()
            self._set_connected(port, f'串口 {self._n_channels}ch, {baud}bps')
        except Exception as e:
            QMessageBox.critical(self, '串口连接失败', str(e))

    def _open_frame_parser(self):
        from metabci.brainviz.frame_parse_dialog import FrameParseDialog
        dlg = FrameParseDialog(self)
        dlg.exec()

    # ============================================================
    # 波形控制
    # ============================================================

    def _on_range_changed(self, _plot, _range):
        # 只在用户用鼠标操作时标记 (程序设XRange也会触发此信号)
        pass  # 不再锁定 — XRange 始终自动滑动

    _hr_last_t = 0
    def _update_hr(self, d):
        """从 ECG 数据估算心率"""
        ch_name = self._ch_combo.currentText()
        if 'ECG' not in ch_name.upper() and '心电' not in ch_name:
            self._hr_label.setText('')
            return
        import time as _time
        now = _time.time()
        if now - LiveLabPage._hr_last_t < 2.0: return  # 2秒算一次
        LiveLabPage._hr_last_t = now
        try:
            import numpy as np
            # 找R峰: 超过均值+2*std, 不应期0.25s(62样本@250Hz)
            threshold = np.mean(d) + 2.0 * np.std(d)
            refractory = int(250 * 0.25)  # 0.25s不应期
            peaks = []
            last_peak = -refractory
            for i in range(1, len(d)-1):
                if d[i] > threshold and d[i] > d[i-1] and d[i] > d[i+1] and i - last_peak >= refractory:
                    peaks.append(i)
                    last_peak = i
            if len(peaks) >= 2:
                # 平均RR间期 → BPM
                rr_mean = np.mean(np.diff(peaks)) / 250.0  # 250Hz采样
                bpm = 60.0 / rr_mean if rr_mean > 0 else 0
                self._hr_label.setText(f'♥ {bpm:.0f} BPM')
        except: pass

    def _on_channel_changed(self, idx: int):
        if self._worker and idx >= 0:
            self._worker.set_wave_channel(idx)
            self._y_set = False; self._y_set_pp = False
        if 'ECG' not in self._ch_combo.currentText().upper():
            self._hr_label.setText('')

    def _toggle_pause(self):
        self._wave_paused = not self._wave_paused
        self._pause_btn.setText('继续' if self._wave_paused else '暂停')

    def _toggle_preproc_view(self):
        self._show_preproc = not self._show_preproc
        self._preproc_btn.setText('处理后' if self._show_preproc else '原始')
        self._y_set_pp = False
        # 立即用已有的预处理数据刷新
        if self._show_preproc and hasattr(self, '_preproc_wave') and self._preproc_wave is not None:
            t, d = self._preproc_wave
            n = min(len(t), len(d))
            if n > 1:
                self._wave_curve.setData(t[:n], d[:n])
                self._wave_plot.setXRange(t[0], t[-1], padding=0)

    def _toggle_recording(self):
        import os, json, time as _time
        from datetime import datetime
        import numpy as np

        if self._recording:
            self._recording = False
            duration = _time.time() - self._record_start
            chunks = getattr(self, '_record_chunks', [])
            preproc_chunks = getattr(self, '_record_preproc_chunks', [])
            if chunks:
                tstamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                para = self._mw.current_paradigm
                pname = para.paradigm_id if para else 'unknown'
                dpath = os.path.join(os.path.expanduser('~/MetaBCI_Recordings'), f'{pname}_{tstamp}')
                os.makedirs(dpath, exist_ok=True)
                # 拼接所有录制的 chunk（持续追加模式）
                data = np.concatenate(chunks, axis=0)
                nch = data.shape[1]
                np.save(os.path.join(dpath, 'raw.npy'), data)
                # 预处理数据 — 对所有通道分别做预处理
                if self._worker and hasattr(self._worker, '_apply_preproc'):
                    srate = self._buffer.srate
                    pp_all = []
                    for ch in range(nch):
                        ch_data = data[:, ch].astype(np.float64)
                        pp_ch = self._worker._apply_preproc(ch_data, srate)
                        pp_all.append(pp_ch)
                    pp_data = np.column_stack(pp_all)
                    np.save(os.path.join(dpath, 'preprocessed.npy'), pp_data)
                elif preproc_chunks:
                    pp_data = np.concatenate(preproc_chunks, axis=0)
                    if len(pp_data) > data.shape[0]:
                        pp_data = pp_data[-data.shape[0]:]
                    np.save(os.path.join(dpath, 'preprocessed.npy'), pp_data)
                # 通道名称
                ch_names = self._get_frame_channel_names()
                if not ch_names:
                    ch_names = [f'Ch{i}' for i in range(nch)]
                meta = {'srate': self._buffer.srate, 'n_channels': nch,
                        'duration': duration, 'samples': data.shape[0],
                        'date': tstamp, 'paradigm': pname,
                        'channel_names': ch_names[:nch],
                        'preproc': True}
                with open(os.path.join(dpath, 'meta.json'), 'w') as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)
                actual_dur = data.shape[0] / self._buffer.srate
                self._rec_status.setText(f'已保存 ({actual_dur:.0f}s, {nch}ch)')
            else:
                self._rec_status.setText(f'无数据 ({duration:.0f}s)')
            self._rec_btn.setText('● 录制')
            self._record_chunks = []
            self._record_preproc_chunks = []
        else:
            if self._buffer is None or self._buffer.sample_count == 0:
                QMessageBox.warning(self, '提示', '请先连接设备')
                return
            self._recording = True
            self._record_start = _time.time()
            self._record_chunks = []
            self._record_preproc_chunks = []
            self._rec_btn.setText('■ 停止')
            self._rec_status.setText('录制中...')

    def _on_user_scroll(self):
        self._user_scrolling = True
        # 3秒不动后恢复自动滚动
        if hasattr(self, '_scroll_timer'):
            self._scroll_timer.stop()
        from PySide6.QtCore import QTimer
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(lambda: setattr(self, '_user_scrolling', False))
        self._scroll_timer.start(3000)

    def _reset_wave(self):
        self._user_scrolling = False
        self._y_range_set = False
        self._wave_curve.clear()
        self._y_range_set = False
        self._wave_plot.enableAutoRange(axis='x'); self._wave_plot.enableAutoRange(axis='y')

    def _clear_wave(self):
        self._wave_curve.clear()
        self._y_range_set = False
        self._wave_plot.disableAutoRange(axis='y')
        self._wave_plot.setYRange(-500, 500)

    # ── [MetaBCI] 基线校准 ──

    _baseline_ratios: list = []
    _baseline_timer: int = 0
    _baseline_active: bool = False

    def _start_baseline(self):
        """开始 10 秒基线采集 — 请保持放松闭眼"""
        if self._baseline_active:
            return
        if not self._worker:
            QMessageBox.warning(self, '提示', '请先连接设备')
            return
        self._baseline_ratios = []
        self._baseline_timer = 0
        self._baseline_active = True
        self._baseline_btn.setText('采集中...')
        self._baseline_btn.setStyleSheet('padding:2px 10px;font-size:11px;background:#f59e0b;color:#fff;border:none;border-radius:3px;')
        self._baseline_status.setText('请闭眼放松 (10s)')

        # 用 QTimer 每秒更新倒计时, 10s 后完成
        from PySide6.QtCore import QTimer
        self._bl_timer = QTimer(self)
        self._bl_timer.timeout.connect(self._baseline_tick)
        self._bl_timer.start(1000)

    def _baseline_tick(self):
        """基线采集倒计时"""
        self._baseline_timer += 1
        remaining = 10 - self._baseline_timer
        self._baseline_status.setText(f'请闭眼放松 ({remaining}s)')
        if self._baseline_timer >= 10:
            self._baseline_finish()

    def _baseline_finish(self):
        """基线采集完成, 计算平均 β/(θ+α)"""
        self._baseline_active = False
        self._bl_timer.stop()
        self._baseline_btn.setText('基线校准')
        self._baseline_btn.setStyleSheet('padding:2px 10px;font-size:11px;background:#4CAF50;color:#fff;border:none;border-radius:3px;')

        if not self._worker:
            self._baseline_status.setText('无数据')
            return

        ratios = getattr(self._worker, '_baseline_collect', [])
        if ratios and len(ratios) > 10:
            import numpy as np
            baseline = float(np.mean(ratios))
            self._save_baseline(baseline)
            # 更新 Worker 的基线
            self._worker._focus_baseline = baseline
            self._worker._baseline_collect = []
            self._baseline_status.setText(f'✅ 基线: {baseline:.2f}')
        else:
            self._baseline_status.setText(f'数据不足 ({len(ratios)}点)')

    def _save_baseline(self, ratio: float):
        """保存基线到文件"""
        import json as _json, os as _os
        path = _os.path.expanduser('~/MetaBCI_Calibration/focus_baseline.json')
        _os.makedirs(_os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            _json.dump({'baseline_ratio': float(ratio), 'formula': 'beta/(theta+alpha)'}, f)

    # ============================================================
    # 信号处理
    # ============================================================

    def _on_waveform(self, t, d):
        # [MetaBCI] 录制：每次取最新小块 (环形缓冲安全, 不限时长)
        if self._recording and self._buffer:
            import numpy as np
            buf = self._buffer
            n_ch = min(buf.n_channels, 8)
            n_new = max(1, int(buf.srate * 0.05))  # ~12 样本 @250Hz
            ch_data = []
            for ch in range(n_ch):
                cd = buf.get_channel(ch)
                if len(cd) >= n_new:
                    ch_data.append(cd[-n_new:].copy())
            if len(ch_data) >= 1:
                # 对齐所有通道到最短长度, 不足的填 0
                min_len = min(len(c) for c in ch_data)
                padded = []
                for c in ch_data:
                    padded.append(c[-min_len:])
                # 缺失通道填 0
                while len(padded) < n_ch:
                    padded.append(np.zeros(min_len))
                chunk = np.column_stack(padded)
                self._record_chunks.append(chunk)
            # 预处理片段
            if self._worker and hasattr(self._worker, '_preproc_cache') and len(self._worker._preproc_cache) >= n_new:
                self._record_preproc_chunks.append(
                    self._worker._preproc_cache[-n_new:].copy())

        if self._wave_paused: return
        if not self._show_preproc:
            n = min(len(t), len(d))
            if n > 1:
                self._wave_curve.setData(t[:n], d[:n])
                if not getattr(self, '_user_drag', False):
                    self._wave_plot.setXRange(t[0], t[-1], padding=0)
                if not hasattr(self, '_y_set') or not self._y_set:
                    import numpy as np
                    lo, hi = np.percentile(d[:n], 1), np.percentile(d[:n], 99)
                    self._wave_plot.setYRange(lo-(hi-lo)*0.15, hi+(hi-lo)*0.15 if hi>lo else lo+1000, padding=0)
                    self._y_set = True
                # ECG心率
                self._update_hr(d)
                if self.isVisible(): self._wave_plot.update()

    def _on_preproc(self, t, d):
        if self._wave_paused: return
        if self._show_preproc and len(t) > 1 and len(d) > 1:
            n = min(len(t), len(d))
            self._wave_curve.setData(t[:n], d[:n])
            self._wave_plot.setXRange(t[0], t[-1], padding=0)  # 预处理强制更新X轴
            if not hasattr(self, '_y_set_pp') or not self._y_set_pp:
                import numpy as np
                lo, hi = np.percentile(d[:n], 1), np.percentile(d[:n], 99)
                self._wave_plot.setYRange(lo-(hi-lo)*0.15, hi+(hi-lo)*0.15 if hi>lo else lo+1000, padding=0)
                self._y_set_pp = True
            if self.isVisible(): self._wave_plot.update()

    def _draw_wave(self):
        if self._wave_paused: return
        if self._show_preproc and hasattr(self, '_preproc_wave') and self._preproc_wave is not None:
            t, d = self._preproc_wave
            if len(t) == 0 or len(d) == 0:
                data = getattr(self, '_raw_wave', None)
                if data: t, d = data
                else: return
        else:
            data = getattr(self, '_raw_wave', None)
            if data is None: return
            t, d = data
        n = min(len(t), len(d))
        if n > 1:
            self._wave_curve.setData(t[:n], d[:n])
            # X轴: 显示绝对时间 (自动滑动)
            self._wave_plot.setXRange(t[0], t[-1], padding=0)
            # Y轴: 首次设定后不再调整
            if not hasattr(self, '_y_range_set') or not self._y_range_set:
                import numpy as np
                lo = np.percentile(d[:n], 1)
                hi = np.percentile(d[:n], 99)
                if hi > lo:
                    margin = (hi - lo) * 0.15
                    self._wave_plot.setYRange(lo - margin, hi + margin, padding=0)
                else:
                    # 常数值通道: 以数值为中心给个默认范围
                    self._wave_plot.setYRange(lo - 1000, lo + 1000, padding=0)
                self._y_range_set = True
            if self.isVisible():
                self._wave_plot.update()

    def _on_spectrum(self, f, p):
        self._spec_curve.setData(f, p)
        # Y 轴自适应
        if len(p) > 0:
            self._spec_plot.enableAutoRange(axis='y')

    def _on_bands(self, pm):
        mx = max(pm.values()) or 1.0
        for bn, bar in self._band_bars.items():
            p = pm.get(bn, 0.0); bar.setValue(min(100, int(p/mx*100)))
            self._band_vals[bn].setText(f'{p:.1f}')

    def _on_focus(self, pct, ratio):
        self._result_val.setText(str(pct)); self._result_bar.setValue(pct)
        self._result_detail.setText(f'β/(θ+α) = {ratio:.2f}')
        c = GREEN if pct>=65 else '#f59e0b' if pct>=35 else RED
        self._result_val.setStyleSheet(f'color:{c};font-size:48px;font-weight:bold;border:none;background:transparent;')

    def _on_ssvep(self, freq, direction):
        self._result_val.setText(f'{freq:.1f} Hz'); self._result_bar.setValue(int(freq/15*100))
        self._result_detail.setText(f'方向: {direction}')
        self._result_val.setStyleSheet(f'color:{ACCENT};font-size:40px;font-weight:bold;border:none;background:transparent;')

    def _on_p300(self, target):
        if target>=0: self._result_val.setText('目标出现'); self._result_bar.setValue(100); self._result_detail.setText(f'检测到目标 {target+1}')
        else: self._result_val.setText('检测中'); self._result_bar.setValue(0); self._result_detail.setText('等待 P300 响应...')

    def _on_mi(self, side, conf):
        self._result_val.setText(side); self._result_bar.setValue(int(conf*100))
        self._result_detail.setText(f'置信度: {conf:.0%}')
        self._result_val.setStyleSheet(f'color:{ACCENT};font-size:36px;font-weight:bold;border:none;background:transparent;')

    # ── [MetaBCI] GameBridge 转发 ──

    def _forward_focus(self, pct: int, ratio: float):
        """转发专注度到 Godot 游戏 (仅 focus 范式)"""
        if self._paradigm_id != 'focus':
            return
        bridge = self._mw.game_bridge
        if not bridge or not bridge.is_running:
            return
        bands = getattr(self, '_latest_bands', {})
        has_baseline = bool(
            self._worker and self._worker._focus_baseline is not None
        )
        bridge.broadcast({
            "type": "focus",
            "pct": pct,
            "ratio": round(ratio, 2),
            "theta": round(bands.get('θ theta', 0), 4),
            "alpha": round(bands.get('α alpha', 0), 4),
            "beta": round(bands.get('β beta', 0), 4),
            "has_baseline": has_baseline,
        })
        # 诊断日志 (每秒最多打印一次)
        now = __import__('time').time()
        if not hasattr(self, '_last_fwd_log') or now - self._last_fwd_log > 1.0:
            self._last_fwd_log = now
            print(f"[LiveLab] 转发专注度: pct={pct}, ratio={ratio:.2f}, "
                  f"has_baseline={has_baseline}, bridge_clients={bridge.client_count}")

    def _forward_ssvep(self, freq: float, direction: str):
        """转发 SSVEP 解码结果到 Godot 游戏"""
        # 始终记录解码日志 (必须在 bridge 检查之前)
        _ssvep_decode_log.append({
            'freq': round(freq, 1),
            'time': __import__('time').time(),
        })
        bridge = self._mw.game_bridge
        if not bridge or not bridge.is_running:
            return
        from metabci.brainviz.game_bridge import SSVEP_FREQ_MAP
        target_index = -1
        min_dist = float('inf')
        for f, idx in SSVEP_FREQ_MAP.items():
            dist = abs(f - freq)
            if dist < min_dist and dist < 1.5:
                min_dist = dist
                target_index = idx
        # 仅在 SSVEP 范式时转发到游戏
        if self._paradigm_id == 'ssvep':
            bridge.broadcast({
                "type": "ssvep_result",
                "frequency": round(freq, 1),
                "target_index": target_index,
                "direction": direction,
            })
        # 解码日志已在方法开头记录

    def _forward_p300(self, target: int):
        """转发 P300 检测结果到 Godot 游戏"""
        bridge = self._mw.game_bridge
        if not bridge or not bridge.is_running:
            return
        bridge.broadcast({
            "type": "p300_result",
            "target_index": target,
            "confidence": 0.85 if target >= 0 else 0.0,
        })

    def _forward_mi(self, side: str, conf: float):
        """转发 MI 分类结果到 Godot 游戏"""
        bridge = self._mw.game_bridge
        if not bridge or not bridge.is_running:
            return
        bridge.broadcast({
            "type": "mi_result",
            "direction": side,
            "confidence": round(conf, 2),
        })

    # ── [MetaBCI] P300 事件处理 ──

    def _on_bridge_game_event(self, event_name: str, data: dict):
        """接收来自 Godot 游戏的 P300 事件"""
        if event_name == "p300_flash":
            self._handle_p300_flash(data)
        elif event_name == "p300_scan_done":
            self._handle_p300_scan_done(data)

    def _handle_p300_flash(self, data: dict):
        """处理单次闪牌事件 — 截取 EEG 片段"""
        if not self._buffer or self._buffer.sample_count < 100:
            return

        card_index = data.get("card_index", -1)
        if card_index < 0:
            return

        # 初始化 P300 解码器
        if self._p300_decoder is None:
            from metabci.brainviz.p300_decoder import P300Decoder
            n_ch = min(self._buffer.n_channels, 8)
            self._p300_decoder = P300Decoder(
                srate=self._buffer.srate, n_channels=n_ch
            )

        decoder = self._p300_decoder
        srate = self._buffer.srate
        seg_len = decoder.segment_len

        # 从缓冲区截取 [当前-N, 当前] 的 EEG 段
        # 包含刺激前 pre_samples 和刺激后 post_samples
        # 由于闪牌事件是实时到达的，我们取最近 seg_len 个样本
        eeg_segments = []
        eeg_idx = self._get_eeg_channel_indices()
        for ch in eeg_idx[:2]:  # 最多2个脑电通道
            ch_data = self._buffer.get_channel(ch)
            if len(ch_data) < seg_len:
                continue
            # 对通道做预处理
            if self._worker and hasattr(self._worker, '_apply_preproc'):
                pp = self._worker._apply_preproc(ch_data[-seg_len:], srate)
            else:
                pp = ch_data[-seg_len:]
            eeg_segments.append(pp)

        if eeg_segments:
            eeg = np.array(eeg_segments)
            decoder.add_flash(card_index, eeg)

    def _handle_p300_scan_done(self, data: dict):
        """扫描完成 — 分类并发送结果"""
        if not self._p300_decoder or not self._p300_decoder.ready:
            return

        target_idx, confidence = self._p300_decoder.classify()

        # 发送结果到 Godot
        bridge = self._mw.game_bridge
        if bridge and bridge.is_running:
            bridge.broadcast({
                "type": "p300_result",
                "target_index": target_idx,
                "confidence": round(confidence, 2),
                "flash_stats": self._p300_decoder.get_flash_stats(),
            })

        # 更新 UI
        if target_idx >= 0:
            self._result_val.setText(f'牌{target_idx+1}')
            self._result_bar.setValue(int(confidence * 100))
            self._result_detail.setText(f'P300 检测 置信度:{confidence:.0%}')
        else:
            self._result_val.setText('?')
            self._result_detail.setText('P300 数据不足')

        # 重置准备下一轮
        self._p300_decoder.reset()
