# -*- coding: utf-8 -*-
"""
LiveWorker — 实时脑电处理, 遵循 MetaBCI brainflow.ProcessWorker 模式

pre() → consume() → post() 生命周期
按范式切换处理逻辑: 专注度→百分制 / SSVEP→频率识别 / P300→检测 / MI→分类
"""

import logging, traceback
import numpy as np
from PySide6.QtCore import QThread, Signal

from metabci.brainviz.config import BANDS

logger = logging.getLogger("brainviz.worker")

# SSVEP 目标频率
SSVEP_FREQS = [8.0, 10.0, 12.0, 15.0]


class LiveWorker(QThread):
    """在线脑电处理 worker (MetaBCI ProcessWorker 模式)"""

    waveform_ready = Signal(object, object)   # (np.ndarray, np.ndarray)
    spectrum_ready = Signal(object, object)   # (np.ndarray, np.ndarray)
    bands_ready = Signal(object)             # dict
    focus_ready = Signal(int, float)
    ssvep_ready = Signal(float, str)
    p300_ready = Signal(int)
    mi_ready = Signal(str, float)

    def __init__(self, buffer, parent=None):
        super().__init__(parent)
        self._buffer = buffer
        self._running = False
        self._spec_timer = 0.0
        self._spec_interval = 5.0  # 频谱计算间隔 (降低CPU占用)
        self._paused = False
        self._wave_timer = 0.0
        self._wave_interval = 0.1  # 波形 10Hz (降低信号频率)
        self._paradigm = 'focus'

    def set_paradigm(self, paradigm_id: str):
        """切换处理范式 — focus / ssvep / p300 / mi"""
        self._paradigm = paradigm_id
        logger.info(f"LiveWorker paradigm → {paradigm_id}")

    # —— MetaBCI ProcessWorker 生命周期 ——

    def pre(self):
        self._spec_timer = 0.0; self._wave_timer = 0.0

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def consume(self):
        if self._paused:
            return
        if self._buffer is None or self._buffer.sample_count < int(self._buffer.srate * 0.5):
            return

        buf = self._buffer
        ch0 = buf.get_channel(0)
        time = buf.get_time()
        srate = buf.srate

        # 波形发送 (节流 10Hz)
        self._wave_timer += 0.05
        if self._wave_timer >= self._wave_interval:
            self._wave_timer = 0.0
            n_wave = int(5.0 * srate)
            self.waveform_ready.emit(time[-n_wave:].copy(), ch0[-n_wave:].copy())

        # 频谱 (节流)
        self._spec_timer += 0.05
        if self._spec_timer >= self._spec_interval:
            self._spec_timer = 0.0
            self._compute_all(ch0, srate)

    def post(self):
        logger.info("LiveWorker stopped")

    # —— 统一计算 ——

    def _compute_all(self, data: np.ndarray, srate: float):
        recent = data[-int(srate * 3.0):]
        if len(recent) < int(srate * 0.5):
            return

        # 分段平均 PSD (类 Welch, 纯 numpy, 轻量)
        seg_len = int(srate * 1.0)  # 1秒一段
        overlap = seg_len // 2
        step = seg_len - overlap
        n_segs = max(1, (len(recent) - seg_len) // step + 1)

        psd_avg = None
        for i in range(n_segs):
            start = i * step
            seg = recent[start:start + seg_len]
            seg = seg - np.mean(seg)
            seg = seg * np.hanning(len(seg))  # 加窗
            fft_vals = np.fft.rfft(seg)
            psd = np.abs(fft_vals) ** 2 / (seg_len * srate)
            if psd_avg is None:
                psd_avg = psd
            else:
                psd_avg += psd

        if psd_avg is None:
            return
        psd_avg /= n_segs
        freqs = np.fft.rfftfreq(seg_len, 1.0 / srate)

        mask = freqs <= 100
        self.spectrum_ready.emit(freqs[mask], psd_avg[mask])

        # Band power
        power_map = {}
        for band_name, (lo, hi) in BANDS.items():
            idx = np.where((freqs >= lo) & (freqs <= hi))[0]
            p = float(np.trapz(psd_avg[idx], freqs[idx])) if len(idx) > 0 else 0.0
            power_map[band_name] = p
        self.bands_ready.emit(power_map)

        # 范式感知解码
        if self._paradigm == 'ssvep':
            self._decode_ssvep(freqs, psd)
        elif self._paradigm == 'p300':
            self._decode_p300(data, srate)
        elif self._paradigm == 'mi':
            self._decode_mi()
        else:
            self._decode_focus(power_map)

    # —— 专注度: (θ+α)/β → 百分制 ——

    def _decode_focus(self, power_map: dict[str, float]):
        theta = power_map.get('θ theta', 0.0)
        alpha_ = power_map.get('α alpha', 0.0)
        beta = power_map.get('β beta', 1e-10)
        ratio = (theta + alpha_) / max(beta, 1e-10)
        pct = max(0, min(100, int(ratio / 2.0 * 50)))
        self.focus_ready.emit(pct, ratio)

    # —— SSVEP: 识别目标频率 → 方向 ——

    def _decode_ssvep(self, freqs: np.ndarray, psd: np.ndarray):
        best_freq = 8.0
        best_power = 0.0
        for target in SSVEP_FREQS:
            # 取目标频率 ±1Hz 范围内的峰值功率
            idx = np.where((freqs >= target - 1.0) & (freqs <= target + 1.0))[0]
            if len(idx) > 0:
                peak = float(np.max(psd[idx]))
                if peak > best_power:
                    best_power = peak
                    best_freq = target

        # 频率 → 方向
        direction_map = {8.0: '↑ 上', 10.0: '→ 右', 12.0: '↓ 下', 15.0: '← 左'}
        direction = direction_map.get(best_freq, f'{best_freq:.0f}Hz')
        self.ssvep_ready.emit(best_freq, direction)

    # —— P300: 占位 ——
    def _decode_p300(self, data: np.ndarray, srate: float):
        self.p300_ready.emit(-1)

    # —— MI: 占位 ——
    def _decode_mi(self):
        self.mi_ready.emit('--', 0.0)

    # —— QThread ——
    def run(self):
        import traceback
        self._running = True
        self.pre()
        while self._running:
            try:
                self.consume()
            except Exception as e:
                logger.error(f"LiveWorker error: {e}\n{traceback.format_exc()}")
            self.msleep(50)
        self.post()

    def stop(self):
        self._running = False
