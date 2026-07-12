#!/usr/bin/env python3
"""ItCCA SSVEP 分类验证 — 会话内模板匹配

训练中心校准阶段使用 ItCCA 个人化频率模板进行验证，
本脚本复现相同的会话内模板匹配流程。

用法:
  cd 验证程序 && python 03_itcca_validate.py

依赖: numpy
"""

import json, sys; from pathlib import Path; import numpy as np

SRATE = 250.0; FREQS = [8.0, 15.0]; DATA_DIR = Path("../验证数据")


def extract_trials(data_dir):
    pp = data_dir / "preprocessed.npy"; tj = data_dir / "trials.json"
    if not pp.exists() or not tj.exists(): return [], []
    eeg = np.load(pp); trials = json.load(open(tj))["trials"]
    ts = int(3.5 * SRATE)
    X, y = [], []
    for i, t in enumerate(trials):
        s = i * ts + int(1.25 * SRATE); e = s + int(1.5 * SRATE)
        if e > eeg.shape[0]: break
        X.append(eeg[s:e, :]); y.append(t["freq"])
    return X, y


def build_templates(X_list, y_list):
    tmpl = {}
    for f in FREQS:
        fs = str(float(f)); segs = [x for x, y in zip(X_list, y_list) if abs(y - f) < 1.5]
        if segs: tmpl[fs] = {"mu": np.stack(segs).mean(0), "n": len(segs)}
    return tmpl


def itcca_decode(segment, templates):
    corrs = {}
    for f in FREQS:
        fs = str(float(f))
        if fs not in templates: continue
        mu = templates[fs]["mu"]; ml = min(len(segment), len(mu))
        st, tt = segment[:ml, :2], mu[:ml, :2]
        cc = [abs(np.corrcoef(st[:, c], tt[:, c])[0, 1]) for c in range(2)
              if st[:, c].std() > 1e-10 and tt[:, c].std() > 1e-10]
        corrs[f] = np.mean(cc) if cc else 0.0
    return float(max(corrs, key=corrs.get))


def main():
    sessions = sorted([d for d in DATA_DIR.iterdir()
                       if d.is_dir() and d.name.startswith("ssvep")])
    if not sessions:
        print("未找到 SSVEP 数据"); sys.exit(1)

    print("=" * 64)
    print("ItCCA SSVEP 会话内验证 (复刻训练中心方法)")
    print("=" * 64)
    print(f"算法: Individual Template CCA (个人化频率模板, Pearson相关)")
    print(f"频率: {FREQS}  采样率: {SRATE} Hz")
    print(f"硬件: 自制脑电采集电路板, 串口通信")
    print(f"验证方式: 会话内全部试次训练模板 -> 同会话测试")
    print()

    total_correct, total_n = 0, 0

    for s in sessions:
        X, y = extract_trials(s)
        if len(X) < 2: continue
        tmpl = build_templates(X, y)
        t8 = tmpl.get("8.0", {}).get("n", 0)
        t15 = tmpl.get("15.0", {}).get("n", 0)

        correct = 0; per_trial = []
        for i, (seg, target) in enumerate(zip(X, y)):
            pred = itcca_decode(seg, tmpl)
            hit = abs(pred - target) < 1.5
            if hit: correct += 1
            per_trial.append((i + 1, target, pred, hit))

        acc = correct / len(X) * 100
        total_correct += correct; total_n += len(X)

        print(f"-- {s.name} --")
        print(f"  模板: 8Hz x {t8}, 15Hz x {t15}  试次: {len(X)}  "
              f"正确: {correct}  准确率: {acc:.0f}%")
        for idx, target, pred, hit in per_trial:
            mark = "OK" if hit else "XX"
            print(f"    试次{idx:2d}: 目标{target:.0f}Hz -> 解码{pred:.1f}Hz {mark}")
        print()

    avg = total_correct / total_n * 100 if total_n else 0
    print("=" * 64)
    print(f"汇总: {total_correct}/{total_n} = {avg:.1f}%")
    print(f"基线 (2分类随机): 50.0%")
    if avg > 50: print(f"提升: +{avg - 50:.1f}%")


if __name__ == "__main__":
    main()
