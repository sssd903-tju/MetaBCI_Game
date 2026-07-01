# -*- coding: utf-8 -*-
"""
BrainVizGUI — 主窗口

整合 metabci.brainflow (数据采集) + metabci.brainda (算法) + PySide6 GUI
"""

import logging
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QLabel,
    QPushButton, QToolBar, QComboBox, QMessageBox, QWidget, QHBoxLayout, QVBoxLayout,
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction

from metabci.brainviz.config import (
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT,
    PLOT_REFRESH_MS, COLORS, BANDS, WAVEFORM_SECONDS,
)
from metabci.brainviz.data_buffer import EEGBuffer
from metabci.brainviz.panels.waveform import WaveformPanel
from metabci.brainviz.panels.spectrum import SpectrumPanel
from metabci.brainviz.panels.classification import ClassificationPanel
from metabci.brainviz.panels.science import SciencePanel
from metabci.brainviz.panels.recording import RecordingPanel

logger = logging.getLogger("brainviz")


class BrainVizGUI(QMainWindow):
    """MetaBCI 可视化平台主窗口"""

    def __init__(self, simulate: bool = False):
        super().__init__()
        self._simulate = simulate
        self._buffer: EEGBuffer | None = None
        self._inlet = None
        self._pull_thread = None
        self._elapsed = 0.0
        self._srate = 250.0
        self._n_channels = 8

        self.setWindowTitle(WINDOW_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(f"background-color: {COLORS['bg_dark']};")

        self._setup_toolbar()
        self._setup_tabs()
        self._setup_statusbar()

        # 刷新定时器
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(PLOT_REFRESH_MS)

        # 自动扫描 LSL
        self._scan_streams()

        # 模拟模式自动启动
        if simulate:
            self._start_simulate()

    # ============================================================
    # 工具栏
    # ============================================================

    def _setup_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setStyleSheet(f"""
            QToolBar {{
                background: {COLORS['bg_panel']};
                border-bottom: 1px solid {COLORS['grid']};
                padding: 4px; spacing: 8px;
            }}
        """)

        self._connect_btn = QPushButton("🔌 连接 LSL")
        self._connect_btn.setStyleSheet(self._btn_style())
        self._connect_btn.clicked.connect(self._toggle_lsl)
        tb.addWidget(self._connect_btn)

        self._stream_combo = QComboBox()
        self._stream_combo.setFixedWidth(220)
        self._stream_combo.setStyleSheet(f"""
            QComboBox {{
                background: {COLORS['bg_dark']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['grid']}; padding: 4px 8px; border-radius: 4px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background: {COLORS['bg_dark']}; color: {COLORS['text_primary']};
                selection-background-color: {COLORS['accent_green']};
            }}
        """)
        tb.addWidget(self._stream_combo)

        refresh_btn = QPushButton("🔄 扫描")
        refresh_btn.setStyleSheet(self._btn_style())
        refresh_btn.clicked.connect(self._scan_streams)
        tb.addWidget(refresh_btn)

        tb.addSeparator()

        self._mode_label = QLabel("⚪ 未连接")
        self._mode_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; padding: 4px;"
        )
        tb.addWidget(self._mode_label)

        self.addToolBar(tb)

    # ============================================================
    # 标签页
    # ============================================================

    def _setup_tabs(self):
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: {COLORS['bg_dark']}; }}
            QTabBar::tab {{
                background: {COLORS['bg_panel']}; color: {COLORS['text_secondary']};
                padding: 8px 20px; margin-right: 2px;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
            }}
            QTabBar::tab:selected {{
                background: {COLORS['bg_dark']}; color: {COLORS['accent_green']};
                font-weight: bold;
            }}
            QTabBar::tab:hover {{ color: {COLORS['text_primary']}; }}
        """)

        # 页签 1: 实时仪表板
        viz = QWidget()
        viz_layout = QHBoxLayout(viz)
        viz_layout.setContentsMargins(4, 4, 4, 4)
        viz_layout.setSpacing(4)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(4)

        self._waveform = WaveformPanel()
        self._spectrum = SpectrumPanel()
        ll.addWidget(self._waveform, 3)
        ll.addWidget(self._spectrum, 2)

        self._classification = ClassificationPanel()
        self._classification.setFixedWidth(320)

        viz_layout.addWidget(left, 4)
        viz_layout.addWidget(self._classification, 1)

        self._tabs.addTab(viz, "📊 实时仪表板")

        # 页签 2: 科普讲解
        self._science = SciencePanel()
        self._tabs.addTab(self._science, "📖 科普讲解")

        # 页签 3: 数据记录
        self._recording = RecordingPanel()
        self._tabs.addTab(self._recording, "💾 数据管理")

        self.setCentralWidget(self._tabs)

    # ============================================================
    # 状态栏
    # ============================================================

    def _setup_statusbar(self):
        self._status = QStatusBar()
        self._status.setStyleSheet(f"""
            QStatusBar {{
                background: {COLORS['bg_panel']}; color: {COLORS['text_secondary']};
                border-top: 1px solid {COLORS['grid']}; font-size: 11px;
            }}
        """)

        self._srate_lbl = QLabel("采样率: -- Hz")
        self._ch_lbl = QLabel("通道: --")
        self._dur_lbl = QLabel("数据: 0.0s")
        self._fps_lbl = QLabel("FPS: --")

        for lbl in [self._srate_lbl, self._ch_lbl, self._dur_lbl, self._fps_lbl]:
            lbl.setStyleSheet("padding: 0 12px;")
            self._status.addWidget(lbl)

        self.setStatusBar(self._status)

    # ============================================================
    # LSL 操作 (基于 metabci.brainflow 模式)
    # ============================================================

    def _scan_streams(self):
        self._stream_combo.clear()
        try:
            from pylsl import resolve_byprop
            streams = resolve_byprop("type", "EEG", timeout=3.0)
            for s in streams:
                label = f"{s.name()} ({s.channel_count()}ch, {int(s.nominal_srate())}Hz)"
                self._stream_combo.addItem(label, {
                    "name": s.name(), "uid": s.uid(),
                    "channels": s.channel_count(), "srate": s.nominal_srate(),
                })
            if not streams:
                self._stream_combo.addItem("(未发现 LSL 流)")
        except Exception as e:
            self._stream_combo.addItem(f"(错误: {e})")
            logger.error(f"LSL 扫描失败: {e}")

    def _toggle_lsl(self):
        if self._inlet is not None:
            self._disconnect_lsl()
        elif self._simulate:
            self._disconnect_lsl()
        else:
            self._connect_lsl()

    def _connect_lsl(self):
        data = self._stream_combo.currentData()
        if data is None:
            QMessageBox.warning(self, "错误", "请先选择 LSL 流")
            return

        try:
            from pylsl import resolve_byprop, StreamInlet

            streams = resolve_byprop("name", data["name"], timeout=3.0)
            if not streams:
                QMessageBox.warning(self, "错误", f"未找到流: {data['name']}")
                return

            self._inlet = StreamInlet(streams[0])
            info = self._inlet.info()
            self._srate = info.nominal_srate()
            self._n_channels = info.channel_count()
            self._elapsed = 0.0

            # 创建缓冲区
            self._buffer = EEGBuffer(
                n_channels=self._n_channels, srate=self._srate
            )

            # 启动拉取线程
            self._start_pull_thread()

            # 关联面板
            self._waveform.set_buffer(self._buffer)
            self._spectrum.set_buffer(self._buffer)
            self._recording.set_buffer(self._buffer)

            # UI
            self._connect_btn.setText("🔌 断开")
            self._connect_btn.setStyleSheet(self._btn_style(active=True))
            self._mode_label.setText(f"🟢 {data['name']}")
            self._mode_label.setStyleSheet(
                f"color: {COLORS['accent_green']}; padding: 4px; font-weight: bold;"
            )
            self._srate_lbl.setText(f"采样率: {int(self._srate)} Hz")
            self._ch_lbl.setText(f"通道: {self._n_channels}")

            logger.info(f"已连接 LSL: {data['name']} ({self._n_channels}ch, {int(self._srate)}Hz)")

        except Exception as e:
            QMessageBox.critical(self, "连接失败", str(e))
            logger.error(f"LSL 连接失败: {e}")

    def _start_pull_thread(self):
        """后台拉取线程 (参照 brainflow.workers 模式)"""
        from threading import Thread

        class PullThread(Thread):
            def __init__(self, inlet, buffer, srate):
                super().__init__(daemon=True)
                self.inlet = inlet
                self.buffer = buffer
                self.srate = srate
                self.running = True

            def run(self):
                while self.running:
                    try:
                        chunk, ts = self.inlet.pull_chunk(timeout=0.1, max_samples=128)
                        if chunk and len(chunk) > 0:
                            self.buffer.push(chunk, ts)
                    except Exception:
                        pass

        self._pull_thread = PullThread(self._inlet, self._buffer, self._srate)
        self._pull_thread.start()

    def _disconnect_lsl(self):
        if self._pull_thread:
            self._pull_thread.running = False
            self._pull_thread = None
        self._inlet = None
        self._buffer = None

        self._connect_btn.setText("🔌 连接 LSL")
        self._connect_btn.setStyleSheet(self._btn_style())
        self._mode_label.setText("⚪ 未连接")
        self._mode_label.setStyleSheet(f"color: {COLORS['text_secondary']}; padding: 4px;")
        self._srate_lbl.setText("采样率: -- Hz")
        self._ch_lbl.setText("通道: --")

    def _start_simulate(self):
        """模拟模式 — 生成合成 EEG 数据"""
        from threading import Thread
        import time

        self._srate = 250.0
        self._n_channels = 8
        self._elapsed = 0.0
        self._buffer = EEGBuffer(n_channels=self._n_channels, srate=self._srate)

        class SimThread(Thread):
            def __init__(self, buffer, srate):
                super().__init__(daemon=True)
                self.buffer = buffer
                self.srate = srate
                self.running = True
                self._t = 0.0

            def run(self):
                while self.running:
                    n = int(0.1 * self.srate)
                    t = np.linspace(self._t, self._t + 0.1, n, endpoint=False)
                    self._t += 0.1
                    # 合成 EEG: 噪声 + alpha(10Hz) + beta(20Hz)
                    noise = np.random.randn(n) * 10.0
                    alpha = 15.0 * np.sin(2 * np.pi * 10.0 * t)
                    beta = 10.0 * np.sin(2 * np.pi * 20.0 * t)
                    eeg = noise + alpha + beta
                    # 扩展到多通道（加微小差异）
                    chunk = []
                    for ch in range(self.buffer.n_channels):
                        ch_data = eeg + np.random.randn(n) * 2.0
                        chunk.append(ch_data.tolist())
                    # 转置: [[ch1, ch2,...], ...]
                    samples = [[chunk[c][i] for c in range(self.buffer.n_channels)] for i in range(n)]
                    self.buffer.push(samples, None)
                    time.sleep(0.09)

        self._sim_thread = SimThread(self._buffer, self._srate)
        self._sim_thread.start()

        self._waveform.set_buffer(self._buffer)
        self._spectrum.set_buffer(self._buffer)
        self._recording.set_buffer(self._buffer)

        self._mode_label.setText("🟡 模拟模式")
        self._mode_label.setStyleSheet(
            f"color: {COLORS['warning']}; padding: 4px; font-weight: bold;"
        )
        self._srate_lbl.setText(f"采样率: {int(self._srate)} Hz")
        self._ch_lbl.setText(f"通道: {self._n_channels}")

    # ============================================================
    # 主循环
    # ============================================================

    def _tick(self):
        self._elapsed += PLOT_REFRESH_MS / 1000.0

        if self._buffer is None or self._buffer.sample_count == 0:
            self._fps_lbl.setText("FPS: --")
            return

        self._waveform.refresh()
        self._spectrum.refresh(self._elapsed)
        self._update_classification()

        self._dur_lbl.setText(f"数据: {self._buffer.duration:.1f}s")

    def _update_classification(self):
        """使用 brainda 算法计算频带能量和专注度"""
        buf = self._buffer
        if buf is None or buf.sample_count < int(buf.srate * 1.0):
            return

        ch0 = buf.get_channel(0)[-int(buf.srate * 2.0):]
        if len(ch0) < int(buf.srate * 0.5):
            return

        from scipy import signal as scipy_signal
        nperseg = min(len(ch0), int(buf.srate))
        freqs, psd = scipy_signal.welch(
            ch0 - np.mean(ch0), fs=buf.srate,
            nperseg=nperseg, noverlap=nperseg // 2
        )

        power_map = {}
        for band_name, (lo, hi) in BANDS.items():
            idx = np.where((freqs >= lo) & (freqs <= hi))[0]
            power = float(np.trapezoid(psd[idx], freqs[idx])) if len(idx) > 0 else 0.0
            power_map[band_name] = power

        theta = power_map.get("θ theta", 0.0)
        alpha_ = power_map.get("α alpha", 0.0)
        beta = power_map.get("β beta", 1e-10)
        ratio = (theta + alpha_) / max(beta, 1e-10)
        focus_pct = max(0, min(100, int(ratio / 2.0 * 50)))

        self._classification.update_focus(focus_pct)

        max_p = max(power_map.values()) if power_map else 1.0
        self._classification.update_bands(power_map, max_p)

        self._classification.set_status(
            f"θ+α/β = {ratio:.2f}  →  专注度: {focus_pct}%\n"
            f"δ:{power_map.get('δ delta',0):.1f}  θ:{theta:.1f}  "
            f"α:{alpha_:.1f}  β:{beta:.1f}  γ:{power_map.get('γ gamma',0):.1f}"
        )

    # ============================================================
    # 样式
    # ============================================================

    @staticmethod
    def _btn_style(active: bool = False) -> str:
        bg = COLORS["accent_green"] if active else COLORS["bg_dark"]
        return f"""
            QPushButton {{
                background: {bg}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['grid']};
                padding: 6px 14px; border-radius: 4px; font-size: 13px;
            }}
            QPushButton:hover {{ background: {COLORS['accent_green']}; }}
        """

    def closeEvent(self, event):
        self._disconnect_lsl()
        event.accept()
