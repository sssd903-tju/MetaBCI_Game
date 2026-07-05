# -*- coding: utf-8 -*-
"""LiveWorker — 实时脑电处理 (MetaBCI ProcessWorker 模式)"""

import logging, os, traceback; import numpy as np
from PySide6.QtCore import QThread, Signal
from metabci.brainviz.config import BANDS

logger = logging.getLogger("brainviz.worker")
# [MetaBCI] SSVEP 目标频率 — 默认贪吃蛇 2频(8/15Hz), 打地鼠7频
SSVEP_FREQS = [8.0, 10.0, 12.0, 15.0]
MOLE_FREQS = [8.0, 10.0, 12.0, 15.0]  # 打地鼠 4频


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
        self._preproc_config = {'带通滤波': True, '陷波滤波': True, '基线校正': False}
        self._filter_params = {'lowcut': 0.5, 'highcut': 45.0, 'notch': 50.0}
        self._preproc_cache = np.array([]); self._preproc_last_idx = 0
        # [MetaBCI] 脑电通道名列表 (从帧格式读取, 不含 ECG)
        self._eeg_channels: list[int] = []
        # [MetaBCI] 专注度基线
        self._focus_baseline = self._load_focus_baseline()
        self._baseline_collect = []  # 基线采集期间的比值缓存
        # [MetaBCI] ItCCA SSVEP 个人化模板 (训练中心校准后自动加载)
        self._ssvep_freqs: list[float] = []
        self._ssvep_templates = self._load_ssvep_templates()

    def set_eeg_channels(self, indices: list[int]):
        """设置用于解码的脑电通道索引 (不含 ECG)"""
        self._eeg_channels = indices

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
                nyq = srate / 2; nf = self._filter_params['notch']
                # 50Hz 主陷波: Q=8 更宽更有效
                b, a = sig.iirnotch(nf / nyq, 8.0)
                result = sig.filtfilt(b, a, result)
                # 100Hz 谐波陷波
                if nf * 2 < nyq:
                    b2, a2 = sig.iirnotch(nf * 2 / nyq, 8.0)
                    result = sig.filtfilt(b2, a2, result)
            except Exception:
                pass
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

                # 预处理缓存: 每0.25秒重建 (快速启动)
                if len(ch_data) > 0 and int(global_samples) >= self._preproc_last_idx + int(srate * 0.25):
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

                # 频谱 + 解码 — 每 0.5s 更新, 用所有脑电通道
                spec_t += 0.05
                if spec_t >= 0.5:
                    spec_t = 0.0
                    decode_data = self._get_multi_ch_data(buf, srate)
                    if decode_data is not None:
                        self._compute_all(decode_data, srate)
                    elif len(self._preproc_cache) > 0:
                        self._compute_all(self._preproc_cache, srate)
                    else:
                        # fallback: 直接用原始单通道数据
                        if len(ch_data) >= int(srate * 1.0):
                            pp = self._apply_preproc(ch_data[-int(srate * 1.0):], srate)
                            self._compute_all(pp, srate)

            except Exception as e:
                logger.error(f"Worker: {e}\n{traceback.format_exc()}")
            self.msleep(50)
        logger.info("Worker stopped")

    def _get_multi_ch_data(self, buf, srate) -> np.ndarray | None:
        """获取所有脑电通道的预处理数据 (排除 ECG)"""
        if not self._eeg_channels:
            self._eeg_channels = list(range(buf.n_channels))
        eeg_idx = [i for i in self._eeg_channels if i < buf.n_channels]
        if not eeg_idx:
            return None
        seg_len = int(srate * 1.0)  # 1秒数据即可解码
        ch_segments = []
        for i in eeg_idx:
            cd = buf.get_channel(i)
            if len(cd) < seg_len:
                continue
            pp = self._apply_preproc(cd[-seg_len:], srate)
            ch_segments.append(pp)
        if not ch_segments:
            return None
        min_len = min(len(c) for c in ch_segments)
        return np.array([c[-min_len:] for c in ch_segments])

    def stop(self): self._running = False

    # —— 频谱 ——
    def _compute_all(self, data, srate):
        """多通道频谱计算 — data shape (n_channels, n_samples)"""
        if data.ndim == 1:
            data = data[np.newaxis, :]  # 兼容单通道
        n_ch = data.shape[0]
        seg_len = int(srate * 1.0)

        # 对每个通道计算 PSD
        all_psds = []
        for ch in range(n_ch):
            ch_data = data[ch]
            recent = ch_data[-int(srate * 3.0):]
            if len(recent) < seg_len:
                continue
            overlap = seg_len // 2; step = seg_len - overlap
            n_segs = max(1, (len(recent) - seg_len) // step + 1)
            psd_avg = None; actual_len = 0
            for i in range(n_segs):
                seg = recent[i*step:i*step+seg_len]
                if len(seg) < seg_len: continue
                actual_len = len(seg)
                seg = seg - np.mean(seg); seg = seg * np.hanning(len(seg))
                psd = np.abs(np.fft.rfft(seg))**2 / (seg_len * srate)
                psd_avg = psd if psd_avg is None else psd_avg + psd
            if psd_avg is None or actual_len == 0: continue
            psd_avg /= n_segs
            all_psds.append(psd_avg)

        if not all_psds:
            return
        # 多通道平均 PSD
        psd_avg = np.mean(all_psds, axis=0)
        actual_len = len(psd_avg) * 2 - 2  # rfft 逆推
        freqs = np.fft.rfftfreq(actual_len, 1.0 / srate)
        mask = freqs <= 100
        self.spectrum_ready.emit(freqs[mask], psd_avg[mask])

        # 多通道平均频带能量
        power_map = {}
        for bn, (lo, hi) in BANDS.items():
            idx = np.where((freqs >= lo) & (freqs <= hi))[0]
            power_map[bn] = float(np.trapz(psd_avg[idx], freqs[idx])) if len(idx) > 0 else 0.0
        self.bands_ready.emit(power_map)

        # 诊断
        now = __import__('time').time()
        if not hasattr(self, '_last_ca_log') or now - self._last_ca_log > 2.0:
            self._last_ca_log = now
            print(f"[_compute_all] paradigm={self._paradigm} data_shape={data.shape}")
        if self._paradigm == 'focus':
            self._decode_focus(power_map)
        elif self._paradigm == 'ssvep':
            self._decode_ssvep(data, srate)

    def _load_focus_baseline(self) -> float | None:
        """加载已保存的专注度基线"""
        import json as _json
        path = os.path.expanduser('~/MetaBCI_Calibration/focus_baseline.json')
        try:
            if os.path.exists(path):
                with open(path) as f:
                    data = _json.load(f)
                return float(data.get('baseline_ratio', 0))
        except Exception:
            pass
        return None

    def _load_ssvep_templates(self) -> dict | None:
        """[MetaBCI] 加载 ItCCA SSVEP 个人化频率模板

        优先从训练中心输出目录加载，其次从校准目录加载。
        模板格式: {freq_str: {'template_mean': ndarray (n_samples, n_channels), ...}, ...}

        Returns:
            dict | None: 模板字典，无模板时返回 None (回退 SCCA)
        """
        import json as _json
        search_paths = [
            os.path.expanduser('~/MetaBCI_Training_Data'),
            os.path.expanduser('~/MetaBCI_Calibration'),
        ]
        for base in search_paths:
            # 方式1: 直接读 ssvep_templates.npz (训练中心最新输出)
            direct = os.path.join(base, 'ssvep_templates.npz')
            if os.path.exists(direct):
                try:
                    data = np.load(direct, allow_pickle=True)
                    t_dict = data['templates'].item()
                    # 提取频率列表
                    self._ssvep_freqs = sorted([float(k) for k in t_dict.keys()])
                    logger.info(f"ItCCA 模板已加载: {self._ssvep_freqs} Hz (from {direct})")
                    return t_dict
                except Exception as e:
                    logger.warning(f"ItCCA 模板加载失败 ({direct}): {e}")

            # 方式2: 搜索训练数据子目录
            if os.path.isdir(base):
                for d in sorted(os.listdir(base), reverse=True):
                    sub = os.path.join(base, d, 'ssvep_templates.npz')
                    if os.path.exists(sub):
                        try:
                            data = np.load(sub, allow_pickle=True)
                            t_dict = data['templates'].item()
                            self._ssvep_freqs = sorted([float(k) for k in t_dict.keys()])
                            logger.info(f"ItCCA 模板已加载: {self._ssvep_freqs} Hz (from {sub})")
                            return t_dict
                        except Exception:
                            continue

        logger.info("ItCCA 模板未找到，将使用 SCCA 在线解码")
        return None

    def _decode_focus(self, pm):
        """[MetaBCI] 专注度 = β / (θ+α)

        生理依据:
          β波 (13-30Hz) — 活跃思考、注意力集中 → 专注时增强
          α波 (8-13Hz)  — 放松闭眼 → 专注时被抑制（α阻断）
          θ波 (4-8Hz)   — 冥想/困倦 → 专注时降低

        闭眼放松 → α↑ → 比值↓ → 专注度低
        睁眼专注 → α↓ β↑ → 比值↑ → 专注度高

        百分位计算:
          无基线: pct = ratio * 50  (ratio≈1.0 时 pct≈50)
          有基线: pct = (ratio / baseline) * 50  (个人化)
        """
        t = pm.get('θ theta', 0)
        a = pm.get('α alpha', 0)
        b = max(pm.get('β beta', 0), 1e-10)
        r = b / (t + a + 1e-10)

        # 基线采集期间累积比值
        if len(self._baseline_collect) < 50:  # ~5s 的数据
            self._baseline_collect.append(r)

        if self._focus_baseline and self._focus_baseline > 0.01:
            pct = max(0, min(100, int(r / self._focus_baseline * 50)))
        else:
            pct = max(0, min(100, int(r * 50)))
        self.focus_ready.emit(pct, r)

    def _decode_ssvep(self, data, srate):
        """[MetaBCI] SSVEP 在线解码

        优先使用 ItCCA 个人化模板匹配 (离线准确率 94%)；
        无模板时回退 SCCA + 差分预加重 + 去偏 (通用方案)。
        """
        try:
            if self._ssvep_templates is not None:
                best_f, conf = self._decode_ssvep_itcca(data)
                method = 'ItCCA'
            else:
                best_f, conf = self._decode_ssvep_scca(data, srate)
                method = 'SCCA'

            d = {8.0: '↑', 10.0: '→', 12.0: '↓', 15.0: '←'}
            direction = d.get(best_f, f'{best_f:.0f}Hz')
            print(f"[SSVEP:{method}] {best_f:.0f}Hz conf={conf:.2f} {direction}")
            self.ssvep_ready.emit(best_f, direction)
        except Exception as e:
            print(f"[SSVEP] err: {e}")
            self.ssvep_ready.emit(8.0, '?')

    def _decode_ssvep_itcca(self, data):
        """ItCCA 个体模板匹配 — 离线准确率 94%, 极低计算开销

        Args:
            data: (n_channels, n_samples) 预处理后 EEG

        Returns:
            (best_freq_hz, confidence_0_to_1)
        """
        t_dict = self._ssvep_templates
        n_samp = min(data.shape[1], 375)  # 最多取 1.5s
        seg = data[:, -n_samp:]  # 取最新数据

        corrs = {}
        for freq_key, tmpl_data in t_dict.items():
            tmpl = np.array(tmpl_data['template_mean'])  # (n_tmpl, n_ch)
            min_len = min(seg.shape[1], tmpl.shape[0])
            seg_trim = seg[:, :min_len]
            tmpl_trim = tmpl[:min_len, :].T  # → (n_ch, n_tmpl) 匹配 data 形状

            # 多通道平均 Pearson 相关
            ch_corrs = []
            n_ch = min(seg_trim.shape[0], tmpl_trim.shape[0])
            for ch in range(n_ch):
                if seg_trim[ch].std() > 1e-10 and tmpl_trim[ch].std() > 1e-10:
                    c = np.corrcoef(seg_trim[ch], tmpl_trim[ch])[0, 1]
                    ch_corrs.append(abs(c))
            corrs[float(freq_key)] = float(np.mean(ch_corrs)) if ch_corrs else 0.0

        if not corrs:
            return 8.0, 0.0

        best_freq = max(corrs, key=corrs.get)
        # 归一化置信度：max_corr / (sum of all corrs)
        total = sum(corrs.values()) + 1e-10
        conf = corrs[best_freq] / total
        return best_freq, conf

    def _decode_ssvep_scca(self, data, srate):
        """SCCA + 差分预加重 + 去偏 (回退方案，无需校准)"""
        data = np.diff(data, axis=-1, prepend=data[..., :1])
        from metabci.brainviz.calibration import get_decoder
        decoder = get_decoder(SSVEP_FREQS, srate)
        best_f, _, conf = decoder.decode(data)
        return best_f, conf

    def _decode_p300(self, data, srate): self.p300_ready.emit(-1)
    def _decode_mi(self): self.mi_ready.emit('--', 0.0)
