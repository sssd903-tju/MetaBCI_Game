# -*- coding: utf-8 -*-
"""LiveWorker — 实时脑电处理 (MetaBCI ProcessWorker 模式)"""

import logging, traceback; import numpy as np
from PySide6.QtCore import QThread, Signal
from metabci.brainviz.config import BANDS

logger = logging.getLogger("brainviz.worker")
SSVEP_FREQS = [8.0, 10.0, 12.0, 15.0]


class LiveWorker(QThread):
    waveform_ready = Signal(object, object)   # 原始波形 20Hz
    preproc_ready = Signal(object, object)    # 预处理波形 2Hz
    spectrum_ready = Signal(object, object)
    bands_ready = Signal(object)
    focus_ready = Signal(int, float)
    ssvep_ready = Signal(float, str)
    p300_ready = Signal(int)
    mi_ready = Signal(str, float)

    def __init__(self, buffer, parent=None):
        super().__init__(parent)
        self._buffer = buffer; self._running = False; self._paused = False
        self._wave_ch = 0; self._paradigm = 'focus'
        self._preproc_config = {'带通滤波': True, '陷波滤波': False, '基线校正': False}
        self._filter_params = {'lowcut': 0.5, 'highcut': 45.0, 'notch': 50.0}
        self._preproc_cache = np.array([]); self._preproc_last_idx = 0

    def set_paradigm(self, pid): self._paradigm = pid
    def set_preproc(self, cfg):
        self._preproc_config = cfg.get('filters', cfg)
        self._filter_params = cfg.get('params', self._filter_params)
        self._preproc_cache = np.array([]); self._preproc_last_idx = 0
    def set_wave_channel(self, ch):
        if ch != self._wave_ch:
            self._wave_ch = max(0, ch)
            self._preproc_cache = np.array([]); self._preproc_last_idx = 0
    def pause(self): self._paused = True
    def resume(self): self._paused = False

    # —— 预处理链 ——
    def _apply_preproc(self, data, srate):
        import scipy.signal as sig
        result = data.copy()
        if self._preproc_config.get('基线校正'): result = result - np.mean(result)
        if self._preproc_config.get('带通滤波'):
            try:
                nyq = srate/2; lo, hi = self._filter_params['lowcut'], self._filter_params['highcut']
                b, a = sig.butter(4, [lo/nyq, hi/nyq], btype='band'); result = sig.filtfilt(b, a, result)
            except: pass
        if self._preproc_config.get('陷波滤波'):
            try:
                nyq = srate/2; nf = self._filter_params['notch']
                b, a = sig.iirnotch(nf/nyq, 30.0); result = sig.filtfilt(b, a, result)
            except: pass
        return result

    # —— 主循环 ——
    def run(self):
        self._running = True
        wave_t = 0.0; preproc_t = 0.0; spec_t = 0.0
        global_samples = 0  # 全局样本计数 (不受缓冲区上限影响)
        while self._running:
            try:
                if self._paused: self.msleep(50); continue
                if self._buffer is None or self._buffer.sample_count < 25: self.msleep(50); continue

                buf = self._buffer; srate = buf.srate
                ch_idx = min(self._wave_ch, buf.n_channels-1) if buf.n_channels > 0 else 0
                ch_data = buf.get_channel(ch_idx)

                # 原始波形 20Hz
                wave_t += 0.05; global_samples += srate * 0.05
                if wave_t >= 0.05:
                    wave_t = 0.0
                    nw = int(5.0 * srate)
                    d = ch_data[-nw:].copy()
                    t_end = global_samples / srate
                    t = np.linspace(t_end - len(d)/srate, t_end, len(d))
                    self.waveform_ready.emit(t, d)

                # 预处理缓存: 每0.5秒重建
                if len(ch_data) > 0 and int(global_samples) > self._preproc_last_idx + int(srate * 0.5):
                    try:
                        self._preproc_cache = self._apply_preproc(ch_data, srate)
                        self._preproc_last_idx = int(global_samples)
                    except: pass

                # 预处理波形 20Hz — 从缓存读取，零开销
                preproc_t += 0.05
                if preproc_t >= 0.05 and len(self._preproc_cache) > 0:
                    preproc_t = 0.0
                    nw = int(5.0 * srate)
                    pp = self._preproc_cache[-nw:] if len(self._preproc_cache) >= nw else self._preproc_cache
                    t_end = global_samples / srate
                    tp = np.linspace(t_end - len(pp)/srate, t_end, len(pp))
                    self.preproc_ready.emit(tp, pp)

                # 频谱 5s
                spec_t += 0.05
                if spec_t >= 5.0:
                    spec_t = 0.0
                    self._compute_all(self._preproc_cache if len(self._preproc_cache) > 0 else ch_data, srate)

            except Exception as e:
                logger.error(f"Worker: {e}\n{traceback.format_exc()}")
            self.msleep(50)
        logger.info("Worker stopped")

    def stop(self): self._running = False

    # —— 频谱 ——
    def _compute_all(self, data, srate):
        seg_len = int(srate * 1.0)
        recent = data[-int(srate * 3.0):]
        if len(recent) < seg_len: return
        overlap = seg_len//2; step = seg_len - overlap
        n_segs = max(1, (len(recent)-seg_len)//step + 1)
        psd_avg = None; actual_len = 0
        for i in range(n_segs):
            seg = recent[i*step:i*step+seg_len]
            if len(seg) < seg_len: continue
            actual_len = len(seg)
            seg = seg - np.mean(seg); seg = seg * np.hanning(len(seg))
            psd = np.abs(np.fft.rfft(seg))**2 / (seg_len*srate)
            psd_avg = psd if psd_avg is None else psd_avg + psd
        if psd_avg is None or actual_len == 0: return
        psd_avg /= n_segs
        freqs = np.fft.rfftfreq(actual_len, 1.0/srate)
        mask = freqs <= 100
        self.spectrum_ready.emit(freqs[mask], psd_avg[mask])
        power_map = {}
        for bn, (lo, hi) in BANDS.items():
            idx = np.where((freqs>=lo)&(freqs<=hi))[0]
            power_map[bn] = float(np.trapz(psd_avg[idx], freqs[idx])) if len(idx)>0 else 0.0
        self.bands_ready.emit(power_map)
        if self._paradigm == 'focus': self._decode_focus(power_map)
        elif self._paradigm == 'ssvep': self._decode_ssvep(freqs, psd_avg)

    def _decode_focus(self, pm):
        t=pm.get('θ theta',0); a=pm.get('α alpha',0); b=max(pm.get('β beta',0), 1e-10)
        r=(t+a)/b; self.focus_ready.emit(max(0,min(100,int(r/2.0*50))), r)

    def _decode_ssvep(self, freqs, psd):
        best_f, best_p = 8.0, 0.0
        for f in SSVEP_FREQS:
            idx = np.where((freqs>=f-1)&(freqs<=f+1))[0]
            if len(idx)>0:
                p = float(np.max(psd[idx]))
                if p>best_p: best_p=p; best_f=f
        d = {8.0:'↑',10.0:'→',12.0:'↓',15.0:'←'}
        self.ssvep_ready.emit(best_f, d.get(best_f, f'{best_f:.0f}Hz'))

    def _decode_p300(self, data, srate): self.p300_ready.emit(-1)
    def _decode_mi(self): self.mi_ready.emit('--', 0.0)
