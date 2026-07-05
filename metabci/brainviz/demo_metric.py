#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[MetaBCI] 指标验证脚本 — SSVEP 离线训练准确率验证

用法:
  python demo_metric.py ~/MetaBCI_Training_Data/ssvep_20260705_224212

输出: SSVEP 2频分类准确率及详细试次结果
"""

import sys, os, json, numpy as np
from scipy import signal
from collections import Counter

def compute_accuracy_from_data(data_dir: str) -> dict:
    """从训练数据目录计算 SSVEP 准确率"""
    pp_path = os.path.join(data_dir, "preprocessed.npy")
    meta_path = os.path.join(data_dir, "meta.json")
    trials_path = os.path.join(data_dir, "trials.json")

    for p, name in [(pp_path, "preprocessed.npy"), (meta_path, "meta.json"),
                     (trials_path, "trials.json")]:
        if not os.path.exists(p):
            print(f"❌ 缺失: {name}")
            return {}

    eeg = np.load(pp_path)
    with open(meta_path) as f:
        meta = json.load(f)
    with open(trials_path) as f:
        trial_info = json.load(f)

    srate = meta.get("srate", 250.0)
    trials = trial_info.get("trials", [])
    freqs = [float(f) for f in trial_info.get("freqs", "8,15").split(",")]

    if not trials:
        print("❌ 无试次数据")
        return {}

    # 估算每试次约 3.5s (cue 1s + stim 2s + rest 0.5s)
    trial_samples = int(3.5 * srate)

    correct = 0
    per_trial = []

    for i, trial in enumerate(trials):
        target_freq = trial["freq"]
        # 提取试次对应 EEG 段 (闪烁阶段)
        start = i * trial_samples + int(1.25 * srate)
        end = start + int(1.5 * srate)
        if end > eeg.shape[0]:
            break

        segment = eeg[start:end, :]
        # PSD SNR 解码
        best_freq, best_snr = _psd_decode(segment, freqs, srate)
        hit = abs(best_freq - target_freq) < 1.5
        if hit:
            correct += 1
        per_trial.append({
            "trial": i + 1,
            "target": target_freq,
            "decoded": round(best_freq, 1),
            "snr": round(best_snr, 2),
            "correct": hit,
        })

    n = len(per_trial)
    acc = correct / n * 100 if n > 0 else 0

    return {
        "total_trials": n,
        "correct": correct,
        "accuracy": round(acc, 1),
        "frequencies": freqs,
        "srate": srate,
        "n_channels": eeg.shape[1],
        "per_trial": per_trial,
    }


def _psd_decode(eeg, freqs, srate):
    """[MetaBCI] SCCA+去偏 — 与在线解码一致"""
    # 仅取有效通道 (std > 0)
    valid_ch = [ch for ch in range(eeg.shape[1]) if eeg[:, ch].std() > 1.0]
    if not valid_ch:
        valid_ch = list(range(eeg.shape[1]))
    eeg = eeg[:, valid_ch].T  # (n_channels, n_samples)
    # 预加重 + SCCA
    eeg = np.diff(eeg, axis=-1, prepend=eeg[..., :1])
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from metabci.brainviz.calibration import SSVEPDecoder
    decoder = SSVEPDecoder(target_freqs=freqs, srate=srate)
    best_f, best_idx, conf = decoder.decode(eeg)
    return best_f, conf


def main():
    if len(sys.argv) < 2:
        print("用法: python demo_metric.py <训练数据目录>")
        print("示例: python demo_metric.py ~/MetaBCI_Training_Data/ssvep_20260705_224212")
        sys.exit(1)

    data_dir = os.path.expanduser(sys.argv[1])
    print(f"数据目录: {data_dir}")
    print(f"算法: [MetaBCI] SCCA + PSD SNR 自适应窗口")
    print(f"硬件: 自制脑电采集电路板, 串口 250Hz")

    result = compute_accuracy_from_data(data_dir)
    if not result:
        sys.exit(1)

    print(f"\n=== SSVEP 离线分类结果 ===")
    print(f"频率: {result['frequencies']}")
    print(f"采样率: {result['srate']} Hz")
    print(f"通道数: {result['n_channels']}")
    print(f"试次数: {result['total_trials']}")
    print(f"正确数: {result['correct']}")
    print(f"准确率: {result['accuracy']}%")

    print(f"\n=== 逐试次结果 ===")
    for t in result['per_trial']:
        mark = "✓" if t['correct'] else "✗"
        print(f"  试次{t['trial']:2d}: 目标{t['target']:.0f}Hz → "
              f"解码{t['decoded']:.1f}Hz SNR={t['snr']:.2f} {mark}")

    print(f"\n=== 指标汇总 ===")
    print(f"项目类型: SSVEP 稳态视觉诱发电位")
    print(f"类别数: {len(result['frequencies'])}")
    print(f"导联数: {result['n_channels']}")
    print(f"分类正确率: {result['accuracy']}%")


if __name__ == "__main__":
    main()
