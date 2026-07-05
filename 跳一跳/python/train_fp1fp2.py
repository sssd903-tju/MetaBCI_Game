#!/usr/bin/env python3
"""
离线训练: BDF + JSONL → Temporal FAA(8d) 特征 → SVM-RBF 模型

Usage:
    python train_fp1fp2.py \\
        --bdf /path/to/data.bdf \\
        --sessions /path/to/sessions/ \\
        --output models/fp1fp2_model/

输出:
    models/fp1fp2_model/
        mi_model.json        — 元数据
        mi_model_svm.pkl     — SVM 模型 (最佳)
        mi_model_rf.pkl      — RF 模型
        mi_model_lda.json    — LDA 权重 (兼容旧格式)
        mi_model_scaler.pkl  — StandardScaler
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import timedelta

import numpy as np
import mne
from scipy import signal as sig

sys.path.insert(0, str(Path(__file__).parent))
from fp1fp2_classifier import (
    extract_features, band_power,
    FP1FP2Classifier, train_and_compare,
    FEATURE_NAMES, N_FEATURES, FS as DEFAULT_FS,
)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

FP1_IDX, FP2_IDX = 4, 5
BASELINE_S = 2.0
TASK_S = 2.0


def parse_args():
    p = argparse.ArgumentParser(description="FP1/FP2 MI 分类器离线训练")
    p.add_argument("--bdf", required=True, help="BDF 文件路径")
    p.add_argument("--sessions", required=True, help="包含 session JSONL 的目录")
    p.add_argument("--output", default="models/fp1fp2_model",
                   help="模型输出目录 (default: models/fp1fp2_model)")
    p.add_argument("--fp1-idx", type=int, default=4, help="Fp1 通道索引")
    p.add_argument("--fp2-idx", type=int, default=5, help="Fp2 通道索引")
    p.add_argument("--baseline", type=float, default=2.0,
                   help="baseline 窗口长度 (s)")
    p.add_argument("--task", type=float, default=2.0,
                   help="task 窗口长度 (s)")
    p.add_argument("--fs", type=float, default=250.0, help="采样率")
    return p.parse_args()


def butter_bandpass(x, lo, hi, fs, order=4):
    nyq = 0.5 * fs
    b, a = sig.butter(order, [lo/nyq, hi/nyq], btype="band")
    return sig.filtfilt(b, a, x)


def notch_filt(x, fs, freq=50, q=30):
    b, a = sig.iirnotch(freq, q, fs)
    return sig.filtfilt(b, a, x)


def main():
    args = parse_args()
    fp1_idx, fp2_idx = args.fp1_idx, args.fp2_idx
    fs = args.fs
    bl_n = int(args.baseline * fs)
    tk_n = int(args.task * fs)

    # ── Load BDF ──
    logger.info("Loading BDF: %s", args.bdf)
    raw = mne.io.read_raw_bdf(args.bdf, preload=True, verbose=False)
    data_raw = raw.get_data()
    ch_names = raw.ch_names
    meas = raw.info.get("meas_date")

    # BDF meas_date: device records CST, MNE marks it as UTC
    if hasattr(meas, "timestamp"):
        bdf_start_ms = int((meas.timestamp() - 8 * 3600) * 1000)
    else:
        bdf_start_ms = int(meas * 1000) if meas else 0

    logger.info("Channels: %s, shape=%s, fs=%.0fHz", ch_names, data_raw.shape, fs)
    logger.info("Fp1=idx%d(%s), Fp2=idx%d(%s)",
                fp1_idx, ch_names[fp1_idx], fp2_idx, ch_names[fp2_idx])

    # ── Clean Fp1/Fp2 ──
    fp1_raw = data_raw[fp1_idx].astype(np.float64)
    fp2_raw = data_raw[fp2_idx].astype(np.float64)
    fp1 = notch_filt(butter_bandpass(fp1_raw, 0.5, 45, fs), fs)
    fp2 = notch_filt(butter_bandpass(fp2_raw, 0.5, 45, fs), fs)

    # ── Load trials ──
    session_dir = Path(args.sessions)
    session_files = sorted(session_dir.glob("*.jsonl"))
    if not session_files:
        logger.error("No JSONL files found in %s", session_dir)
        sys.exit(1)
    logger.info("Found %d session files", len(session_files))

    all_trials = []
    for sf in session_files:
        with open(sf) as f:
            for line in f:
                d = json.loads(line.strip())
                if d.get("type") == "trial":
                    all_trials.append(d)

    logger.info("Total trials: %d", len(all_trials))

    # ── Slice windows & extract features ──
    X_list, y_list = [], []
    skipped = 0

    for t in all_trials:
        gt = t["ground_truth"]
        ts_ms = t["timestamp_trial_start_ms"]
        offset_s = (ts_ms - bdf_start_ms) / 1000.0
        bl_s = int(offset_s * fs)
        bl_e = int((offset_s + args.baseline) * fs)
        tk_e = int((offset_s + args.baseline + args.task) * fs)

        if bl_s < 0 or tk_e > len(fp1):
            skipped += 1
            continue

        fp1_bl = fp1[bl_s:bl_e][:bl_n]
        fp1_tk = fp1[bl_e:tk_e][:tk_n]
        fp2_bl = fp2[bl_s:bl_e][:bl_n]
        fp2_tk = fp2[bl_e:tk_e][:tk_n]

        if len(fp1_bl) < bl_n * 0.8 or len(fp1_tk) < tk_n * 0.8:
            skipped += 1
            continue

        try:
            feat = extract_features(fp1_bl, fp1_tk, fp2_bl, fp2_tk, fs)
            X_list.append(feat)
            y_list.append(1 if gt == "left" else 2)
        except Exception as e:
            skipped += 1
            continue

    X = np.array(X_list)
    y = np.array(y_list)
    logger.info("Extracted features: X=%s, y=%s (skipped=%d)",
                X.shape, dict(zip(*np.unique(y, return_counts=True))), skipped)

    if len(X) < 10:
        logger.error("Too few valid trials (%d). Check time alignment.", len(X))
        sys.exit(1)

    # ── Train all classifiers & save best ──
    output_dir = Path(args.output)
    results = train_and_compare(X, y, save_dir=output_dir)

    # ── Print summary ──
    print("\n" + "=" * 55)
    print("训练完成")
    print("=" * 55)
    print(f"  试次: {len(X)} (left={np.sum(y==1)}, right={np.sum(y==2)})")
    print(f"  特征: {N_FEATURES} 维 (6频带FAA + 绝对功率 + ERD)")
    print(f"  输出: {output_dir.absolute()}")
    print()
    print(f"  {'分类器':<15s} {'LOO准确率':>12s}")
    print(f"  {'-'*27}")
    best_type = max(results, key=lambda k: results[k]["accuracy"])
    for ctype, info in results.items():
        marker = " ← best" if ctype == best_type else ""
        print(f"  {ctype.upper():<15s} {info['accuracy']:>10.1%}  ({info['loo_n']} folds){marker}")
    print(f"\n  最佳模型: {best_type.upper()} ({results[best_type]['accuracy']:.1%}) → mi_model_{best_type}.pkl")


if __name__ == "__main__":
    main()
