#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
8Hz SSVEP 闪烁测试 — 独立运行，验证硬件能否采集到 SSVEP 信号

用法:
  python test_8hz.py

屏幕中央显示 8Hz 闪烁方块（黑→白正弦波）。
同时打开在线实验室看频谱图，8Hz 处应有明显峰值。
按 Q 或 Esc 退出。
"""

import time, re, os, sys
import numpy as np

# Monkey-patch: 修复 PsychoPy linebreak_class 字节码溢出
try:
    import psychopy.tools as _ptools
    _lb_path = os.path.join(os.path.dirname(_ptools.__file__), "linebreak_class.py")
    if os.path.exists(_lb_path):
        with open(_lb_path) as _f:
            _raw = _f.read()
        _entries = {}
        for _m in re.finditer(r"(0x[0-9A-Fa-f]+)\s*:\s*'([^']*)'", _raw):
            _entries[int(_m.group(1), 16)] = _m.group(2)
        import types
        _mod = types.ModuleType("psychopy.tools.linebreak_class")
        _mod.linebreak_class = _entries
        sys.modules["psychopy.tools.linebreak_class"] = _mod
except Exception:
    pass

try:
    from psychopy import visual, core, event
except ImportError:
    print("需要 PsychoPy: pip install psychopy")
    print("或 conda: conda install -c conda-forge psychopy")
    exit(1)

TARGET_FREQ = 15.0  # 改成15Hz，远离常见噪声频率
DURATION = 30  # 闪烁 30 秒
BLOCK_SIZE = 300  # 方块大小

win = visual.Window(
    size=(1280, 720), fullscr=False, color=[-1, -1, -1],
    units="pix", allowGUI=True,
)

fps = win.getActualFrameRate(nIdentical=10, nWarmUpFrames=10)
fps = int(fps) if fps else 60
print(f"屏幕刷新率: {fps} Hz")
print(f"闪烁频率: {TARGET_FREQ} Hz")
print(f"方块大小: {BLOCK_SIZE}x{BLOCK_SIZE}")
print(f"持续时间: {DURATION} 秒")
print(f"\n请盯着屏幕中央闪烁方块")
print(f"同时在在线实验室看频谱图 — 8Hz 处应有峰值")
print(f"按 Q 或 Esc 退出\n")

# 中央方块
rect = visual.Rect(win, width=BLOCK_SIZE, height=BLOCK_SIZE,
                   fillColor=[1, 1, 1], lineColor=[0.5, 0.5, 0.5])

# 提示文字
hint = visual.TextStim(win, text=f"盯住方块 · {TARGET_FREQ}Hz 闪烁测试 · 按Q退出",
                       pos=(0, -300), height=20, color="#888888")
freq_label = visual.TextStim(win, text=f"{TARGET_FREQ} Hz",
                             pos=(0, -BLOCK_SIZE//2 - 40), height=24, color="#aaaaaa")

clock = core.Clock()
flip_times = []

while clock.getTime() < DURATION:
    keys = event.getKeys(["escape", "q"])
    if keys:
        print("用户退出")
        break

    elapsed = clock.getTime()
    flip_times.append(elapsed)

    # 实时钟驱动正弦: brightness = (sin(2π·freq·t) + 1) / 2
    brightness = (np.sin(2 * np.pi * TARGET_FREQ * elapsed) + 1) / 2
    c = brightness * 2 - 1  # [0,1] → [-1,1]
    rect.fillColor = [c, c, c]

    rect.draw()
    freq_label.draw()
    hint.draw()
    win.flip()

win.close()

# 统计
if len(flip_times) > 1:
    intervals = np.diff(flip_times)
    actual_fps = 1.0 / np.mean(intervals)
    fps_std = np.std(intervals)
    print(f"\n实际帧率: {actual_fps:.1f} ± {fps_std*1000:.1f}ms")
    print(f"闪烁周期: {1.0/TARGET_FREQ*1000:.0f}ms (应为 {1000/TARGET_FREQ:.0f}ms)")
    print(f"每周期帧数: {actual_fps/TARGET_FREQ:.1f} (应为 {actual_fps/TARGET_FREQ:.1f})")

print("\n如果在线实验室频谱图 8Hz 处有明显峰值 → SSVEP 信号正常")
print("如果 8Hz 处是平的 → 检查电极连接, 或自制硬件 SNR 不够")
