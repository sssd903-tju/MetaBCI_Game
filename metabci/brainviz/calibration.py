# -*- coding: utf-8 -*-
"""
[MetaBCI] SSVEP 校准模块 — 基于 brainda.algorithms.decomposition

在线解码:
  - 无校准: SCCA (Standard CCA) — 标准正弦余弦参考信号
  - 有校准: ItCCA (Individual Template CCA) — 个人化模板 + SCCA

训练后生成个人化频率响应模板，用于改进在线 SSVEP 解码。
算法均来自 MetaBCI brainda.algorithms.decomposition。
"""

import json
import os
import logging
import numpy as np
from typing import Optional

logger = logging.getLogger("brainviz.calibration")

CALIB_DIR = os.path.expanduser("~/MetaBCI_Calibration")
SSVEP_CALIB_FILE = os.path.join(CALIB_DIR, "ssvep_trials.json")
TEMPLATES_FILE = os.path.join(CALIB_DIR, "ssvep_templates.npz")

# 与 Godot 游戏对齐的目标频率
SNAKE_FREQS = [8.0, 10.0, 12.0, 15.0]
MOLE_FREQS = [8.0, 9.2, 10.4, 11.6, 13.0, 14.4, 15.6]


def load_ssvep_calibration() -> dict | None:
    """加载 SSVEP 训练校准数据"""
    if not os.path.exists(SSVEP_CALIB_FILE):
        return None
    try:
        with open(SSVEP_CALIB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"加载校准文件失败: {e}")
        return None


def has_calibration() -> bool:
    """检查是否有 SSVEP 校准数据"""
    return os.path.exists(SSVEP_CALIB_FILE)


def get_calibration_summary() -> str:
    """获取校准数据摘要"""
    calib = load_ssvep_calibration()
    if not calib:
        return "无校准数据"
    freq_info = ", ".join(
        f"{f}Hz×{c}" for f, c in calib.get("freq_counts", {}).items()
    )
    return (
        f"{calib.get('layout', '?')} 布局, "
        f"{calib['total_trials']} 试次\n"
        f"频率分布: {freq_info}"
    )


def compute_templates_from_recording(recording_dir: str,
                                      srate: float = 250.0) -> dict | None:
    """从录制数据 + 试次标签计算 SSVEP 频率模板

    Args:
        recording_dir: 录制目录路径 (含 raw.npy, preprocessed.npy, meta.json)
        srate: 采样率

    Returns:
        dict: {freq_str: {"template_mean": [...], "template_std": [...], "n": int}}
    """
    import json as _json  # renamed to avoid shadowing outer json

    raw_path = os.path.join(recording_dir, "raw.npy")
    pp_path = os.path.join(recording_dir, "preprocessed.npy")
    meta_path = os.path.join(recording_dir, "meta.json")
    calib_path = SSVEP_CALIB_FILE

    if not os.path.exists(pp_path):
        logger.warning(f"预处理数据不存在: {pp_path}")
        return None
    if not os.path.exists(calib_path):
        logger.warning(f"试次标签不存在: {calib_path}")
        return None

    # 加载预处理后的 EEG
    eeg = np.load(pp_path)  # (n_samples, n_channels)
    with open(meta_path) as f:
        meta = _json.load(f)
    with open(calib_path) as f:
        calib = _json.load(f)

    rec_srate = meta.get("srate", srate)
    trials = calib.get("trials", [])
    if not trials:
        return None

    # 估算每个试次的时长和采样点数
    # 试次结构: cue 1s + stim 2s + rest 0.5s = 3.5s
    trial_dur = 3.5  # 秒
    trial_samples = int(trial_dur * rec_srate)  # 875 @ 250Hz

    # 收集每个频率的 EEG 片段
    freq_segments: dict[str, list] = {}
    for i, trial in enumerate(trials):
        freq = str(trial["freq"])
        # 提取该试次对应的 EEG 段 (闪烁阶段的中间 1.5s)
        start = i * trial_samples + int(1.25 * rec_srate)  # 跳过 cue + 0.25s 延迟
        end = start + int(1.5 * rec_srate)                 # 取 1.5s 闪烁数据
        if end > eeg.shape[0]:
            break
        segment = eeg[start:end, :]  # (n_samples, n_channels)
        if freq not in freq_segments:
            freq_segments[freq] = []
        freq_segments[freq].append(segment)

    if not freq_segments:
        return None

    # 计算每个频率的模板
    templates = {}
    for freq_str, segments in freq_segments.items():
        stacked = np.stack(segments, axis=0)  # (n_trials, n_samples, n_channels)
        # 对每个通道计算平均模板
        templates[freq_str] = {
            "template_mean": stacked.mean(axis=0).tolist(),  # (n_samples, n_channels)
            "template_std": stacked.std(axis=0).tolist(),
            "n_trials": len(segments),
        }

    # 保存模板
    try:
        os.makedirs(CALIB_DIR, exist_ok=True)
        np.savez(TEMPLATES_FILE, templates=templates, srate=rec_srate)
        logger.info(f"模板已保存: {TEMPLATES_FILE} ({len(templates)} 频率, "
                     f"{sum(t['n_trials'] for t in templates.values())} 试次)")
    except Exception as e:
        logger.warning(f"保存模板失败: {e}")

    return templates


# ═══════════════════════════════════════════════════════════
# [MetaBCI] SCCA — 标准 CCA 在线解码
# ═══════════════════════════════════════════════════════════

class SSVEPDecoder:
    """[MetaBCI] SSVEP 在线解码器

    基于 brainda.algorithms.decomposition.SCCA + ItCCA:
      - 无校准数据时: 使用 SCCA (正弦余弦参考信号)
      - 有校准数据时: 使用 ItCCA (个人模板 + SCCA)
    """

    def __init__(self, target_freqs: list[float] = None,
                 srate: float = 250.0, n_harmonics: int = 3):
        self.target_freqs = target_freqs or SNAKE_FREQS
        self.srate = srate
        self.n_harmonics = n_harmonics
        self._Yf_all: np.ndarray | None = None
        self._templates: dict[float, np.ndarray] = {}
        self._has_calib = False

    @property
    def has_calibration(self) -> bool:
        return self._has_calib

    def build_references(self, segment_len: int) -> np.ndarray:
        """[MetaBCI] 使用 brainda generate_cca_references 构建参考信号

        为所有目标频率生成正弦余弦参考信号矩阵。
        返回 shape (n_freqs, 2*n_harmonics, n_samples) 供 _scca_feature 使用。
        """
        from metabci.brainda.algorithms.decomposition.base import generate_cca_references

        T = segment_len / self.srate
        # [MetaBCI] generate_cca_references 返回 (n_freqs, 2*n_harmonics, n_samples)
        # 直接供 _scca_feature 使用
        self._Yf_all = generate_cca_references(
            self.target_freqs, self.srate, T,
            n_harmonics=self.n_harmonics
        )
        return self._Yf_all

    def load_templates(self) -> bool:
        """加载训练产生的个人 SSVEP 模板"""
        if not os.path.exists(TEMPLATES_FILE):
            calib = load_ssvep_calibration()
            if not calib:
                return False
            # 只有试次数据，没有模板 → 返回 False，使用 SCCA
            logger.info("校准数据存在但模板未生成，使用 SCCA")
            return False

        try:
            data = np.load(TEMPLATES_FILE, allow_pickle=True)
            templates = data["templates"].item()
            for freq_str, tpl in templates.items():
                self._templates[float(freq_str)] = np.array(tpl["template_mean"])
            self._has_calib = bool(self._templates)
            logger.info(f"已加载 {len(self._templates)} 个频率的 SSVEP 模板")
            return self._has_calib
        except Exception as e:
            logger.warning(f"加载模板失败: {e}")
            return False

    def decode(self, data: np.ndarray) -> tuple[float, int, float]:
        """[MetaBCI] SSVEP 频率识别

        无模板: SCCA (标准 CCA — 正弦余弦参考信号)
        有模板: ItCCA (个体模板 CCA — 个人平均响应 + 参考信号)
        """
        from metabci.brainda.algorithms.decomposition.cca import _scca_feature

        if not hasattr(self, '_Yf_all') or self._Yf_all is None:
            self.build_references(data.shape[-1])
        if self._Yf_all.shape[-1] != data.shape[-1]:
            self.build_references(data.shape[-1])

        data = data - np.mean(data, axis=-1, keepdims=True)
        Yf = self._Yf_all - np.mean(self._Yf_all, axis=-1, keepdims=True)

        n_components = min(data.shape[0], Yf.shape[1], 1)
        # [MetaBCI] SCCA: 与正弦余弦参考信号的相关性
        rhos_scca = _scca_feature(data, Yf, n_components=n_components)
        # 去偏: 减去均值消除低频 1/f 噪声的全局偏见
        rhos_scca = rhos_scca - np.mean(rhos_scca)

        if self._has_calib and self._templates:
            # [MetaBCI] ItCCA: 叠加个人模板相关性
            rhos = np.zeros(len(self.target_freqs))
            for i, freq in enumerate(self.target_freqs):
                tpl = self._templates.get(freq)
                if tpl is not None and tpl.shape[-1] == data.shape[-1]:
                    # 模板与当前 EEG 的相关性
                    tpl_flat = tpl.ravel()
                    data_flat = data.ravel()
                    if len(tpl_flat) == len(data_flat):
                        tpl_corr = np.corrcoef(tpl_flat, data_flat)[0, 1]
                        rhos[i] = (rhos_scca[i] + max(0, tpl_corr)) / 2
                    else:
                        rhos[i] = rhos_scca[i]
                else:
                    rhos[i] = rhos_scca[i]
        else:
            rhos = rhos_scca

        best_idx = int(np.argmax(rhos))
        best_freq = self.target_freqs[best_idx]
        confidence = float(rhos[best_idx])

        return best_freq, best_idx, confidence


# 全局单例
_decoder: Optional[SSVEPDecoder] = None


def get_decoder(target_freqs: list[float] = None,
                srate: float = 250.0) -> SSVEPDecoder:
    """获取全局 SSVEP 解码器单例"""
    global _decoder
    if _decoder is None:
        _decoder = SSVEPDecoder(target_freqs=target_freqs, srate=srate)
        _decoder.load_templates()
    return _decoder


def reset_decoder():
    """重置解码器（切换范式时调用）"""
    global _decoder
    _decoder = None


# ═══════════════════════════════════════════════════════════
# CLI — 离线校准
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) < 2:
        print("用法: python calibration.py <录制目录>")
        print("示例: python calibration.py ~/MetaBCI_Recordings/ssvep_20260704_180145")
        _sys.exit(1)

    rec_dir = _sys.argv[1]
    rec_dir = os.path.expanduser(rec_dir)

    if not os.path.isdir(rec_dir):
        print(f"目录不存在: {rec_dir}")
        _sys.exit(1)

    print(f"录制目录: {rec_dir}")
    print(f"试次标签: {SSVEP_CALIB_FILE}")

    templates = compute_templates_from_recording(rec_dir)
    if templates:
        print(f"\n✅ 模板已生成 ({len(templates)} 频率):")
        for freq_str, tpl in templates.items():
            mean_arr = np.array(tpl["template_mean"])
            print(f"  {freq_str} Hz: {tpl['n_trials']} 试次, "
                  f"shape={mean_arr.shape}, "
                  f"amplitude={np.abs(mean_arr).mean():.1f}")
        print(f"\n模板文件: {TEMPLATES_FILE}")
        print("重新启动平台后，解码器将自动加载模板，使用 ItCCA 模式。")
    else:
        print("\n❌ 模板生成失败。请确保:")
        print("  1. 录制目录包含 preprocessed.npy 和 meta.json")
        print(f"  2. 试次标签存在: {SSVEP_CALIB_FILE}")
        print("  3. 训练试次数 ≥ 2")
