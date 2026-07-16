# -*- coding: utf-8 -*-
"""
在线实验室 v2 — 实时脑电监测 (LSL / 串口 / BLE 三模式)
完全采用 xwm_viewer 格式: 左侧控制面板 + 右侧多通道波形 + 状态栏
"""

import os, json, time as _time, numpy as np
from datetime import datetime
from threading import Thread

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QMessageBox, QListWidget, QListWidgetItem,
    QGroupBox, QStackedWidget, QSplitter, QStatusBar, QMenu,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QTimer

from metabci.brainviz.widgets.xwm_waveform import WaveformWidget, THEMES
from metabci.brainviz.xwm_buffer import RingBuffer
from metabci.brainviz.ble_source import BleManager
from metabci.brainviz.frame_parser import FrameParser, BBSample, CCSample, MOTION_LABELS
from metabci.brainviz.data_buffer import EEGBuffer
from metabci.brainviz.live_worker import LiveWorker

THEME_DARK  = 'dark'
THEME_LIGHT = 'light'
WAVE_TW     = 5.0
PANEL_W     = 220
BB_RATE     = 250  # EEG 采样率
CC_RATE     = 25   # 传感器采样率


class LiveLabPageV2(QWidget):
    """在线实验室 v2 — xwm_viewer 格式 (BB/CC 双帧协议)"""

    def __init__(self, main_window):
        super().__init__()
        self._mw = main_window
        self._buffer: EEGBuffer | None = None
        self._worker: LiveWorker | None = None
        self._inlet = None; self._thread: Thread | None = None
        self._srate = 250.0; self._n_channels = 8
        self._paradigm_id = 'focus'
        self._recording = False; self._record_start = 0.0
        self._record_chunks: list = []

        self._mode = 'serial'; self._connected = False

        # 帧解析器
        self._parser = FrameParser()

        # BLE
        self._ble = BleManager(); self._ble_thread = None
        self._ble_poll = QTimer(self); self._ble_poll.timeout.connect(self._poll_ble)
        self._ble_sample_count = 0; self._last_bb_cnt = 0; self._last_cc_cnt = 0
        self._last_stats_t = _time.time()
        self._latest_hr = 0; self._latest_spo2 = 0; self._latest_motion = 0

        # RingBuffer: BB (3ch EEG) + CC (2ch 传感器)
        self._bb_buf = RingBuffer(3000, n_channels=3, sample_rate=BB_RATE)
        self._cc_buf = RingBuffer(750, n_channels=2, sample_rate=CC_RATE)

        self._theme_dark = True

        self._build_ui()
        self._connect_signals()
        QTimer.singleShot(100, self._scan_devices)

    # ═══════════════════════════════════════════════
    # UI 构建 (xwm_viewer 格式)
    # ═══════════════════════════════════════════════

    def _build_ui(self):
        ml = QHBoxLayout(self); ml.setContentsMargins(4, 4, 4, 4)

        # ── 左侧面板 ──
        left = QWidget(); left.setFixedWidth(PANEL_W)
        lp = QVBoxLayout(left); lp.setContentsMargins(2, 2, 2, 2); lp.setSpacing(3)

        # 模式切换
        mode_row = QHBoxLayout()
        self._btn_serial = QPushButton('串口'); self._btn_serial.setCheckable(True)
        self._btn_lsl    = QPushButton('LSL');  self._btn_lsl.setCheckable(True)
        self._btn_ble    = QPushButton('BLE');   self._btn_ble.setCheckable(True)
        self._btn_serial.setChecked(True)
        for b in (self._btn_serial, self._btn_lsl, self._btn_ble):
            b.setFixedHeight(26); mode_row.addWidget(b)
        lp.addLayout(mode_row)

        # 串口面板
        self._serial_panel = QWidget()
        sl = QVBoxLayout(self._serial_panel); sl.setContentsMargins(0,0,0,0); sl.setSpacing(2)
        pr = QHBoxLayout()
        self._combo_serial = QComboBox(); self._btn_refresh = QPushButton('↻'); self._btn_refresh.setFixedWidth(30)
        pr.addWidget(self._combo_serial); pr.addWidget(self._btn_refresh)
        self._btn_serial_conn = QPushButton('连接串口'); self._btn_serial_dis = QPushButton('断开串口')
        self._btn_serial_dis.setEnabled(False)
        sl.addLayout(pr); sl.addWidget(self._btn_serial_conn); sl.addWidget(self._btn_serial_dis)

        # LSL 面板
        self._lsl_panel = QWidget()
        ll = QVBoxLayout(self._lsl_panel); ll.setContentsMargins(0,0,0,0); ll.setSpacing(2)
        self._combo_lsl = QComboBox()
        self._btn_lsl_scan = QPushButton('扫描 LSL')
        self._btn_lsl_conn = QPushButton('连接 LSL'); self._btn_lsl_dis = QPushButton('断开 LSL')
        self._btn_lsl_dis.setEnabled(False)
        ll.addWidget(self._combo_lsl); ll.addWidget(self._btn_lsl_scan)
        ll.addWidget(self._btn_lsl_conn); ll.addWidget(self._btn_lsl_dis)

        # BLE 面板
        self._ble_panel = QWidget()
        bl = QVBoxLayout(self._ble_panel); bl.setContentsMargins(0,0,0,0); bl.setSpacing(2)
        self._btn_ble_scan = QPushButton('扫描设备')
        self._ble_list = QListWidget()
        self._btn_ble_conn = QPushButton('连接 BLE'); self._btn_ble_conn.setEnabled(False)
        self._btn_ble_dis = QPushButton('断开 BLE'); self._btn_ble_dis.setEnabled(False)
        bl.addWidget(self._btn_ble_scan); bl.addWidget(self._ble_list)
        bl.addWidget(self._btn_ble_conn); bl.addWidget(self._btn_ble_dis)

        self._mode_stack = QStackedWidget()
        self._mode_stack.addWidget(self._serial_panel)
        self._mode_stack.addWidget(self._lsl_panel)
        self._mode_stack.addWidget(self._ble_panel)
        self._mode_stack.setCurrentIndex(0)
        lp.addWidget(self._mode_stack)

        # 生命体征
        gb_vital = QGroupBox('生命体征')
        gv = QVBoxLayout(gb_vital)
        self._lbl_hr = QLabel('HR: -- BPM')
        self._lbl_spo2 = QLabel('SpO₂: --%')
        self._lbl_motion = QLabel('运动: --')
        for lbl in (self._lbl_hr, self._lbl_spo2, self._lbl_motion):
            lbl.setStyleSheet('font-size:13pt;font-weight:bold;padding:2px;')
        gv.addWidget(self._lbl_hr); gv.addWidget(self._lbl_spo2); gv.addWidget(self._lbl_motion)
        lp.addWidget(gb_vital)

        # 滤波
        gb_filt = QGroupBox('滤波')
        gf = QVBoxLayout(gb_filt)
        self._btn_bpf = QPushButton('轻量带通: 关')
        self._btn_bpf.setCheckable(True); self._btn_bpf.setFixedHeight(28)
        gf.addWidget(self._btn_bpf); lp.addWidget(gb_filt)

        # 通道显隐 (BB: CH1/CH2/ECG, CC: IR/RED)
        gb_ch = QGroupBox('通道')
        gch = QVBoxLayout(gb_ch)
        self._bb_cbs = []
        for i, label in enumerate(('CH1 (脑电)', 'CH2 (脑电)', 'ECG (心电)')):
            cb = QPushButton(label); cb.setCheckable(True); cb.setChecked(True)
            cb.setFixedHeight(24); cb.toggled.connect(self._make_bb_toggle(i))
            gch.addWidget(cb); self._bb_cbs.append(cb)
        self._cc_cbs = []
        for i, label in enumerate(('IR (PPG)', 'RED (PPG)')):
            cb = QPushButton(label); cb.setCheckable(True); cb.setChecked(True)
            cb.setFixedHeight(24); cb.toggled.connect(self._make_cc_toggle(i))
            gch.addWidget(cb); self._cc_cbs.append(cb)
        lp.addWidget(gb_ch)

        # 操作按钮
        self._btn_theme = QPushButton('☀ 浅色主题')
        self._btn_theme.clicked.connect(self._toggle_theme); lp.addWidget(self._btn_theme)
        self._btn_pause = QPushButton('暂停波形'); self._btn_pause.setCheckable(True); lp.addWidget(self._btn_pause)
        self._btn_zoom_reset = QPushButton('重置缩放'); lp.addWidget(self._btn_zoom_reset)
        self._btn_clear = QPushButton('清除波形'); lp.addWidget(self._btn_clear)
        lb = QLabel('Y缩放: 鼠标滚轮 | 时间: [ ] | 通道: 1-8')
        lb.setStyleSheet('color:#666;font-size:9px;'); lp.addWidget(lb)
        lp.addSpacing(2)
        self._btn_record = QPushButton('开始录制'); self._btn_record.setEnabled(False); lp.addWidget(self._btn_record)
        lp.addStretch()
        ml.addWidget(left)

        # ── 波形 (BB + CC 分屏) ──
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._bb_wave = WaveformWidget(
            self._bb_buf, labels=['CH1 (脑电)', 'CH2 (脑电)', 'ECG (心电)'],
            sample_rate=BB_RATE, time_window=WAVE_TW, theme='dark')
        self._bb_wave.set_bpf_params(ma_n=8, passes=2)
        self._splitter.addWidget(self._bb_wave)
        self._cc_wave = WaveformWidget(
            self._cc_buf, labels=['IR (PPG)', 'RED (PPG)'],
            sample_rate=CC_RATE, time_window=WAVE_TW, theme='dark')
        self._cc_wave.set_bpf_params(ma_n=8, passes=1)
        self._splitter.addWidget(self._cc_wave)
        self._splitter.setStretchFactor(0, 3); self._splitter.setStretchFactor(1, 1)

        # 右键菜单 (共用)
        self._wave_menu = QMenu(self)
        self._wave_menu.addAction('暂停/恢复 (Space)', self._toggle_pause)
        self._wave_menu.addAction('录制 (R)', self._toggle_recording)
        self._wave_menu.addAction('清除波形 (C)', self._on_clear)
        self._wave_menu.addAction('切换滤波 (F)', self._toggle_bpf)
        self._wave_menu.addAction('切换主题 (T)', self._toggle_theme)
        self._bb_wave.set_context_menu(self._wave_menu)
        self._cc_wave.set_context_menu(self._wave_menu)
        ml.addWidget(self._splitter, 1)

        # ── 状态栏 ──
        self._sb = QStatusBar()
        self._lbl_status = QLabel('就绪')
        self._lbl_rate = QLabel('速率: -- Hz')
        self._lbl_count = QLabel('采样: 0')
        for lbl in (self._lbl_status, self._lbl_rate, self._lbl_count):
            lbl.setContentsMargins(6, 0, 6, 0)
        self._sb.addWidget(self._lbl_status, 1)
        self._sb.addWidget(self._lbl_rate); self._sb.addWidget(self._lbl_count)

    # ═══════════════════════════════════════════════
    # 信号连接
    # ═══════════════════════════════════════════════

    def _connect_signals(self):
        # 模式切换
        self._btn_serial.toggled.connect(lambda c: c and self._switch_mode('serial'))
        self._btn_lsl.toggled.connect(lambda c: c and self._switch_mode('lsl'))
        self._btn_ble.toggled.connect(lambda c: c and self._switch_mode('ble'))
        # 串口
        self._btn_refresh.clicked.connect(self._scan_devices)
        self._btn_serial_conn.clicked.connect(self._connect_serial)
        self._btn_serial_dis.clicked.connect(self._disconnect)
        # LSL
        self._btn_lsl_scan.clicked.connect(self._scan_devices)
        self._btn_lsl_conn.clicked.connect(self._connect_lsl)
        self._btn_lsl_dis.clicked.connect(self._disconnect)
        # BLE
        self._btn_ble_scan.clicked.connect(self._ble_scan)
        self._btn_ble_conn.clicked.connect(self._connect_ble)
        self._btn_ble_dis.clicked.connect(self._disconnect)
        self._ble_list.itemClicked.connect(lambda it: (
            setattr(self, '_sel_ble_addr', it.data(Qt.ItemDataRole.UserRole)),
            self._btn_ble_conn.setEnabled(True)))
        # 操作
        self._btn_pause.toggled.connect(self._on_pause)
        self._btn_zoom_reset.clicked.connect(self._on_zoom_reset)
        self._btn_clear.clicked.connect(self._on_clear)
        self._btn_record.clicked.connect(self._toggle_recording)
        self._btn_bpf.toggled.connect(self._on_bpf)

    # ═══════════════════════════════════════════════
    # 模式切换
    # ═══════════════════════════════════════════════

    def _switch_mode(self, mode: str):
        if self._connected: self._disconnect()
        self._mode = mode
        idx = {'serial': 0, 'lsl': 1, 'ble': 2}[mode]
        self._mode_stack.setCurrentIndex(idx)
        for m, btn in [('serial', self._btn_serial), ('lsl', self._btn_lsl), ('ble', self._btn_ble)]:
            btn.setChecked(m == mode)
        self._scan_devices()

    # ═══════════════════════════════════════════════
    # 设备扫描
    # ═══════════════════════════════════════════════

    def _scan_devices(self):
        if self._mode == 'ble': self._ble_scan()
        elif self._mode == 'lsl': self._scan_lsl()
        else: self._scan_serial()

    def _scan_serial(self):
        self._combo_serial.clear()
        try:
            import serial.tools.list_ports
            for p in serial.tools.list_ports.comports():
                self._combo_serial.addItem(p.device)
            if not self._combo_serial.count():
                self._combo_serial.addItem('(无串口)')
        except Exception: self._combo_serial.addItem('(pyserial未安装)')

    def _scan_lsl(self):
        self._combo_lsl.clear()
        self._combo_lsl.addItem('扫描中...')
        class _S(Thread):
            def __init__(s, cb): super().__init__(daemon=True); s.cb = cb
            def run(s):
                try:
                    from pylsl import resolve_byprop
                    r = [f'{x.name()}@{x.hostname()}' for x in resolve_byprop('type','EEG',timeout=2.0)]
                    s.cb(r if r else ['(未发现LSL流)'])
                except: s.cb(['(pylsl未安装)'])
        def _cb(r):
            self._combo_lsl.clear()
            for x in r: self._combo_lsl.addItem(x)
        _S(_cb).start()

    def _ble_scan(self):
        self._ble_list.clear()
        self._ble_list.addItem('正在扫描...')
        self._ble.scan(self._on_ble_devices, self._set_status)

    def _on_ble_devices(self, devs):
        self._ble_list.clear()
        for name, addr in devs:
            it = QListWidgetItem(f'{name}\n{addr}')
            it.setData(Qt.ItemDataRole.UserRole, addr); self._ble_list.addItem(it)
        if not self._ble_list.count(): self._ble_list.addItem('(未发现BLE设备)')

    # ═══════════════════════════════════════════════
    # 连接 / 断开
    # ═══════════════════════════════════════════════

    def _connect_serial(self):
        port = self._combo_serial.currentText()
        if not port or '无' in port: return QMessageBox.warning(self,'提示','请选择串口')
        try:
            from metabci.brainviz.serial_worker import SerialReader
            self._buffer = EEGBuffer(n_channels=8, srate=self._srate)
            self._bb_buf.reset(sample_rate=self._srate)
            self._reader = SerialReader(port=port, buffer=self._buffer, n_channels=8)
            self._reader.start()
            self._start_worker()
            self._set_connected(f'串口 {port}', f'{self._srate:.0f}Hz x 8ch')
        except Exception as e: QMessageBox.critical(self,'连接失败',str(e))

    def _connect_lsl(self):
        name = self._combo_lsl.currentText()
        if not name or '未发现' in name or '扫描' in name:
            return QMessageBox.warning(self,'提示','请先扫描并选择LSL设备')
        try:
            from pylsl import resolve_byprop, StreamInlet
            sn = name.split('@')[0]
            streams = resolve_byprop('name', sn, timeout=3.0)
            if not streams: return QMessageBox.warning(self,'错误',f'未找到: {sn}')
            info = streams[0]; self._inlet = StreamInlet(info)
            self._srate = float(info.nominal_srate() or 250)
            self._n_channels = info.channel_count()
            self._buffer = EEGBuffer(n_channels=self._n_channels, srate=self._srate)
            self._bb_buf.reset(sample_rate=self._srate)
            class _P(Thread):
                def __init__(s,i,b): super().__init__(daemon=True); s.i=i; s.b=b; s.r=True
                def run(s):
                    while s.r:
                        try:
                            c,t=s.i.pull_chunk(timeout=0.1,max_samples=64)
                            if c: s.b.push(c,t)
                        except: pass
            self._thread = _P(self._inlet, self._buffer); self._thread.start()
            self._start_worker()
            self._set_connected(name, f'{self._srate:.0f}Hz x {self._n_channels}ch')
        except Exception as e: QMessageBox.critical(self,'连接失败',str(e))

    def _connect_ble(self):
        addr = getattr(self, '_sel_ble_addr', None)
        if not addr: return QMessageBox.warning(self,'提示','请先扫描并选择BLE设备')
        self._bb_buf.reset(sample_rate=250)
        self._bb_wave.reset_view()
        self._ble_thread = self._ble.connect(addr, self._set_status, self._on_ble_connected)
        self._ble_poll.start(8)
        self._set_connected(f'BLE {addr}', '250Hz x 3ch')

    def _on_ble_connected(self):
        self._parser.reset_stats()
        self._ble_sample_count = self._last_bb_cnt = self._last_cc_cnt = 0
        self._bb_buf.reset(sample_rate=BB_RATE); self._cc_buf.reset(sample_rate=CC_RATE)
        self._bb_wave.reset_view(); self._cc_wave.reset_view()
        self._lbl_hr.setText('HR: -- BPM'); self._lbl_spo2.setText('SpO₂: --%'); self._lbl_motion.setText('运动: --')
        self._btn_ble_conn.setEnabled(False); self._btn_ble_dis.setEnabled(True)
        self._set_status('BLE 已连接 — 250Hz')

    def _start_worker(self):
        self._worker = LiveWorker(self._buffer)
        self._worker.set_lightweight(True)
        self._worker.waveform_ready.connect(self._on_waveform)
        self._worker.start()

    def _set_connected(self, name, info):
        self._connected = True
        self._btn_serial_conn.setEnabled(False); self._btn_serial_dis.setEnabled(True)
        self._btn_lsl_conn.setEnabled(False); self._btn_lsl_dis.setEnabled(True)
        self._btn_ble_conn.setEnabled(False); self._btn_ble_dis.setEnabled(True)
        self._btn_record.setEnabled(True)
        self._set_status(f'● 已连接: {name} ({info})')

    def _disconnect(self):
        self._connected = False
        if self._thread: self._thread.r = False; self._thread = None
        self._inlet = None
        if self._worker: self._worker.stop(); self._worker.wait(2000); self._worker = None
        if hasattr(self,'_reader'): self._reader.stop()
        self._buffer = None
        self._ble.disconnect(); self._ble_thread = None; self._ble_poll.stop()
        self._btn_serial_conn.setEnabled(True); self._btn_serial_dis.setEnabled(False)
        self._btn_lsl_conn.setEnabled(True); self._btn_lsl_dis.setEnabled(False)
        self._btn_ble_conn.setEnabled(True); self._btn_ble_dis.setEnabled(False)
        self._btn_record.setEnabled(False)
        if self._btn_pause.isChecked(): self._btn_pause.setChecked(False)
        self._set_status('就绪 — 请选择模式并连接设备')

    # ═══════════════════════════════════════════════
    # BLE 数据轮询
    # ═══════════════════════════════════════════════

    def _poll_ble(self):
        if not self._ble_thread or not self._ble_thread.isRunning(): return
        try:
            q = self._ble_thread.data_queue
            for _ in range(20):
                try: data = q.get_nowait()
                except: break
                dlen = len(data); bb_len = (dlen // 20) * 20
                if bb_len > 0:
                    for s in self._parser.feed_ble_eeg(data[:bb_len]):
                        self._bb_buf.push([s.ch1, s.ch2, s.ecg])
                        self._ble_sample_count += 1
                if dlen - bb_len >= 8:
                    for s in self._parser.feed_ble_ecg(data[bb_len:bb_len+8]):
                        self._cc_buf.push([s.ir, s.red])
                        self._latest_hr = s.hr; self._latest_spo2 = s.spo2; self._latest_motion = s.motion
                        self._lbl_hr.setText(f'HR: {s.hr if s.hr else "--"} BPM')
                        self._lbl_spo2.setText(f'SpO₂: {s.spo2/100:.2f}%')
                        self._lbl_motion.setText(f'运动: {MOTION_LABELS.get(s.motion, str(s.motion))}')
        except Exception: pass
        # 更新状态栏
        now = _time.time(); dt = now - self._last_stats_t
        if dt > 1.0:
            self._last_stats_t = now
            bb_cnt = self._parser.bb_count; cc_cnt = self._parser.cc_count
            if bb_cnt > 0: self._lbl_rate.setText(f'BB: {(bb_cnt-self._last_bb_cnt)/dt:.0f} Hz')
            if cc_cnt > 0: self._lbl_rate.setText(f'CC: {(cc_cnt-self._last_cc_cnt)/dt:.0f} Hz')
            self._last_bb_cnt = bb_cnt; self._last_cc_cnt = cc_cnt
            self._lbl_count.setText(f'采样: {self._ble_sample_count}')

    # ═══════════════════════════════════════════════
    # LSL/串口 波形 → RingBuffer
    # ═══════════════════════════════════════════════

    def _on_waveform(self, t, d):
        if self._recording and self._buffer:
            buf = self._buffer; n_ch = min(buf.n_channels, 8)
            n_new = max(1, int(buf.srate * 0.05))
            ch_data = [buf.get_channel(ch)[-n_new:].copy()
                       for ch in range(n_ch) if len(buf.get_channel(ch)) >= n_new]
            if ch_data:
                min_len = min(len(c) for c in ch_data)
                padded = [c[-min_len:] for c in ch_data]
                while len(padded) < n_ch: padded.append(np.zeros(min_len))
                self._record_chunks.append(np.column_stack(padded))
        if self._buffer:
            n_ch = min(self._buffer.n_channels, 8)
            ch_data = [self._buffer.get_channel(ch) for ch in range(n_ch)]
            min_len = min((len(c) for c in ch_data if len(c) > 0), default=0)
            if min_len > 0:
                n_push = min(3, len(ch_data))
                self._bb_buf.push([ch_data[ch][-1] if len(ch_data[ch]) > 0 else 0.0 for ch in range(n_push)])

    # ═══════════════════════════════════════════════
    # 录制
    # ═══════════════════════════════════════════════

    def _toggle_recording(self):
        if self._recording:
            self._recording = False
            if self._record_chunks:
                tstamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                dpath = os.path.join(os.path.expanduser('~/MetaBCI_Recordings'), f'live_{tstamp}')
                os.makedirs(dpath, exist_ok=True)
                data = np.concatenate(self._record_chunks, axis=0)
                np.save(os.path.join(dpath, 'raw.npy'), data)
                meta = {'srate': self._srate, 'n_channels': data.shape[1], 'samples': data.shape[0], 'date': tstamp}
                with open(os.path.join(dpath, 'meta.json'), 'w') as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)
                self._set_status(f'已保存 ({data.shape[0]/self._srate:.0f}s)')
            self._btn_record.setText('开始录制'); self._record_chunks = []
        else:
            self._recording = True; self._record_start = _time.time()
            self._record_chunks = []; self._btn_record.setText('停止录制'); self._set_status('录制中...')

    # ═══════════════════════════════════════════════
    # 显示控制
    # ═══════════════════════════════════════════════

    def _toggle_theme(self):
        self._theme_dark = not self._theme_dark
        t = 'dark' if self._theme_dark else 'light'
        self._bb_wave.set_theme(t)
        self._btn_theme.setText('☀ 浅色主题' if self._theme_dark else '☾ 暗色主题')

    def _on_bpf(self, checked: bool):
        self._bb_wave.toggle_bpf(checked); self._cc_wave.toggle_bpf(checked)
        self._btn_bpf.setText('轻量带通: 开' if checked else '轻量带通: 关')

    def _on_pause(self, checked: bool):
        if checked: self._bb_wave.pause(); self._cc_wave.pause(); self._btn_pause.setText('▶ 恢复波形')
        else: self._bb_wave.resume(); self._cc_wave.resume(); self._btn_pause.setText('暂停波形')

    def _on_zoom_reset(self): self._bb_wave.reset_zoom(); self._cc_wave.reset_zoom()
    def _toggle_pause(self): self._btn_pause.toggle()
    def _toggle_bpf(self): self._btn_bpf.toggle()

    def _on_clear(self):
        self._bb_buf.reset(sample_rate=BB_RATE); self._cc_buf.reset(sample_rate=CC_RATE)
        self._bb_wave.reset_view(); self._cc_wave.reset_view()
        self._parser.reset_stats()
        self._ble_sample_count = self._last_bb_cnt = self._last_cc_cnt = 0
        self._lbl_hr.setText('HR: -- BPM'); self._lbl_spo2.setText('SpO₂: --%'); self._lbl_motion.setText('运动: --')
        if self._btn_pause.isChecked(): self._btn_pause.setChecked(False)

    def _make_bb_toggle(self, n: int):
        def _toggle(checked):
            if not checked and self._bb_wave.visible_count() <= 1:
                self._bb_cbs[n].blockSignals(True); self._bb_cbs[n].setChecked(True); self._bb_cbs[n].blockSignals(False); return
            self._bb_wave.set_visible(n, checked)
        return _toggle

    def _make_cc_toggle(self, n: int):
        def _toggle(checked):
            if not checked and self._cc_wave.visible_count() <= 1:
                self._cc_cbs[n].blockSignals(True); self._cc_cbs[n].setChecked(True); self._cc_cbs[n].blockSignals(False); return
            self._cc_wave.set_visible(n, checked)
        return _toggle

    def _set_status(self, msg: str): self._lbl_status.setText(msg)

    # ═══════════════════════════════════════════════
    # 键盘快捷键 (xwm_viewer 同款)
    # ═══════════════════════════════════════════════

    def keyPressEvent(self, ev):
        k = ev.key()
        if k == Qt.Key.Key_Space: self._toggle_pause()
        elif k == Qt.Key.Key_R: self._toggle_recording()
        elif k == Qt.Key.Key_C: self._on_clear()
        elif k == Qt.Key.Key_F: self._toggle_bpf()
        elif k == Qt.Key.Key_T: self._toggle_theme()
        elif k == Qt.Key.Key_BracketLeft: self._bb_wave.zoom_time_in(); self._cc_wave.zoom_time_in()
        elif k == Qt.Key.Key_BracketRight: self._bb_wave.zoom_time_out(); self._cc_wave.zoom_time_out()
        elif k == Qt.Key.Key_Minus:
            if ev.modifiers() & Qt.KeyboardModifier.ShiftModifier: self._bb_wave.zoom_y_all_out(); self._cc_wave.zoom_y_all_out()
            else: self._bb_wave.zoom_y_out(); self._cc_wave.zoom_y_out()
        elif k == Qt.Key.Key_Equal:
            if ev.modifiers() & Qt.KeyboardModifier.ShiftModifier: self._bb_wave.zoom_y_all_in(); self._cc_wave.zoom_y_all_in()
            else: self._bb_wave.zoom_y_in(); self._cc_wave.zoom_y_in()
        elif k in (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4,
                   Qt.Key.Key_5, Qt.Key.Key_6, Qt.Key.Key_7, Qt.Key.Key_8):
            if ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self._ch_btns[k - Qt.Key.Key_1].toggle()
            else:
                self._bb_wave.set_active_channel(k - Qt.Key.Key_1)
        else: super().keyPressEvent(ev)
