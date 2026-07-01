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


class LiveLabPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self._mw = main_window
        self._buffer = None; self._inlet = None
        self._thread = None; self._worker = None
        self._srate = 250.0; self._n_channels = 8
        self._paradigm_id = 'focus'; self._wave_paused = False
        self._mode_lsl = True
        self._band_bars = {}; self._band_vals = {}
        self._setup(); self._scan_devices()

    def showEvent(self, event):
        super().showEvent(event); self._sync_paradigm()
        self._wave_plot.update()
        if self._worker:
            self._worker.resume()

    def hideEvent(self, event):
        super().hideEvent(event)
        if self._worker:
            self._worker.pause()

    def _sync_paradigm(self):
        para = self._mw.current_paradigm
        if para is None:
            para = type('obj', (object,), {'paradigm_id': 'focus', 'name': '专注度检测',
                'result_label': '检测结果', 'active_electrodes': [], 'science': {}})()
        self._ch_combo.clear()
        ch_names = self._get_frame_channel_names()
        if ch_names:
            for name in ch_names:
                self._ch_combo.addItem(name)
        elif hasattr(para, 'active_electrodes'):
            for name in [e.name for e in para.active_electrodes]:
                self._ch_combo.addItem(name)
        if hasattr(para, 'result_label'):
            self._result_title.setText(para.result_label)
        if self._worker and hasattr(para, 'paradigm_id'):
            self._worker.set_paradigm(para.paradigm_id)
            self._paradigm_id = para.paradigm_id
        self._ch_combo.clear()
        # 优先从帧格式读取通道名，否则用范式电极名
        ch_names = self._get_frame_channel_names()
        if ch_names:
            for name in ch_names:
                self._ch_combo.addItem(name)
        else:
            for name in [e.name for e in para.active_electrodes]:
                self._ch_combo.addItem(name)
        label = getattr(para, 'result_label', '检测结果')
        self._result_title.setText(label)
        if self._worker: self._worker.set_paradigm(para.paradigm_id)
        self._paradigm_id = para.paradigm_id
        self._science.set_content(f'{para.name} · 实时监测', para.science.get('signal', ''))

    def _get_frame_channel_names(self):
        """从已保存的帧格式配置中读取通道名称"""
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
                return names or None
        except Exception:
            pass
        return None

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

        self._mode_lsl = True
        self._mode_btn = QPushButton('串口')  # 当前LSL模式, 按钮显示"切换到串口"
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
        self._pause_btn = QPushButton('暂停'); self._pause_btn.setStyleSheet(btn_s)
        self._pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pause_btn.clicked.connect(self._toggle_pause); tr.addWidget(self._pause_btn)
        reset_btn = QPushButton('重置'); reset_btn.setStyleSheet(btn_s)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self._reset_wave); tr.addWidget(reset_btn)
        wl.replaceWidget(wave_title, QWidget()); wl.insertLayout(0, tr)
        wl.setContentsMargins(8, 4, 8, 8)

        self._wave_plot = pg.PlotWidget()
        self._wave_plot.setBackground('w')
        for ax in ['left', 'bottom']: self._wave_plot.getAxis(ax).setPen('#aaa')
        self._wave_plot.showGrid(x=True, y=True, alpha=0.15)
        self._wave_plot.enableAutoRange(axis='y')
        self._wave_plot.setXRange(0, WAVEFORM_SECONDS)
        self._wave_curve = self._wave_plot.plot(pen=pg.mkPen(color=ACCENT, width=1.2))
        wl.addWidget(self._wave_plot)
        self._ch_combo = QComboBox(); self._ch_combo.setFixedWidth(100); wl.addWidget(self._ch_combo)
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
        # 按钮显示"按下后切换到的模式" (与连接/断开逻辑一致)
        if self._mode_lsl:
            self._mode_btn.setText('串口')
            self._mode_btn.setStyleSheet(f'background:#f59e0b;color:#fff;font-weight:bold;padding:6px 12px;border-radius:4px;border:none;')
        else:
            self._mode_btn.setText('LSL')
            self._mode_btn.setStyleSheet(f'background:{ACCENT};color:#fff;font-weight:bold;padding:6px 12px;border-radius:4px;border:none;')
        self._ser_cfg.setVisible(not self._mode_lsl)
        if self._inlet: self._disconnect()
        self._scan_devices()
        # 首次加载通道名
        self._sync_paradigm()

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
        self._worker.waveform_ready.connect(self._on_waveform)
        self._worker.spectrum_ready.connect(self._on_spectrum)
        self._worker.bands_ready.connect(self._on_bands)
        self._worker.focus_ready.connect(self._on_focus)
        self._worker.ssvep_ready.connect(self._on_ssvep)
        self._worker.p300_ready.connect(self._on_p300)
        self._worker.mi_ready.connect(self._on_mi)
        self._worker.start()

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
        import json, os
        from metabci.brainviz.serial_worker import SerialReader
        from metabci.brainviz.frame_field import FrameField
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
        except Exception: pass

        try:
            self._srate = 250.0; self._n_channels = 8
            if self._buffer is None:
                self._buffer = EEGBuffer(n_channels=self._n_channels, srate=self._srate)
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

    def _toggle_pause(self):
        self._wave_paused = not self._wave_paused
        self._pause_btn.setText('继续' if self._wave_paused else '暂停')

    def _reset_wave(self):
        self._wave_curve.clear()
        self._wave_plot.enableAutoRange(axis='x'); self._wave_plot.enableAutoRange(axis='y')

    # ============================================================
    # 信号处理
    # ============================================================

    def _on_waveform(self, t, d):
        if self._wave_paused: return
        if len(t)>1 and len(d)>1:
            self._wave_curve.setData(t, d)
            self._wave_plot.setXRange(t[-1]-WAVEFORM_SECONDS, t[-1], padding=0)
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
        self._result_detail.setText(f'(θ+α)/β = {ratio:.2f}')
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
