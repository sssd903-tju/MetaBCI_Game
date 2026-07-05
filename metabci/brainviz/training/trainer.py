#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[MetaBCI] 训练脚本 — 基于 brainstim 的标准范式训练与基线校准

作为子进程运行，通过 stdout JSON 行与主进程通信。
PsychoPy 独占全屏窗口，因此必须在独立进程中运行。

用法:
  python trainer.py --mode focus_baseline --duration 30
  python trainer.py --mode ssvep --trials 20 --freqs 8,10,12,15
  python trainer.py --mode p300 --trials 12
  python trainer.py --mode mi --trials 20

协议 (stdout, 每行一条 JSON):
  → 主进程: {"status": "progress", "phase": "prepare", "message": "..."}
  → 主进程: {"status": "progress", "phase": "trial", "trial": 3, "total": 20}
  → 主进程: {"status": "complete", "results": {...}}
  → 主进程: {"status": "error", "message": "..."}
"""

import json
import sys
import os
import time
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("trainer")


def _emit(data: dict):
    """发送 JSON 行到 stdout"""
    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _patch_linebreak():
    """Monkey-patch: 修复 PsychoPy 2022 + Python 3.10 的 linebreak_class 字节码溢出

    linebreak_class.py 有 33 万行 dict 定义，Python 3.10 编译器无法处理。
    直接读取文件内容作为数据解析，绕过编译步骤。
    """
    import re
    try:
        import psychopy.tools as _ptools
        lb_path = os.path.join(os.path.dirname(_ptools.__file__),
                               "linebreak_class.py")
        if os.path.exists(lb_path):
            with open(lb_path) as f:
                raw = f.read()
            # 解析 linebreak_class = { ... } 中的键值对
            entries = {}
            for match in re.finditer(r"(0x[0-9A-Fa-f]+)\s*:\s*'([^']*)'", raw):
                entries[int(match.group(1), 16)] = match.group(2)
            # 注入预编译的模块
            import types
            mod = types.ModuleType("psychopy.tools.linebreak_class")
            mod.linebreak_class = entries
            sys.modules["psychopy.tools.linebreak_class"] = mod
            return True
    except Exception:
        pass
    return False


def _check_deps():
    """检查 PsychoPy 和 brainstim 依赖"""
    # Monkey-patch 修复 linebreak_class 字节码溢出
    _patch_linebreak()

    try:
        import psychopy  # noqa: F401
    except ImportError:
        _emit({"status": "error", "message": "PsychoPy 未安装。请运行: pip install psychopy"})
        sys.exit(1)

    # 将 MetaBCI 加入路径
    metabci_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    if metabci_path not in sys.path:
        sys.path.insert(0, metabci_path)


# ═══════════════════════════════════════════════════════════
# 专注度基线训练
# ═══════════════════════════════════════════════════════════

def run_focus_baseline(duration: int = 30):
    """
    专注度基线校准：
    - 前 10 秒：闭眼放松 (theta/alpha 基线)
    - 中间 10 秒：睁眼专注 (beta 基线)
    - 最后 10 秒：自由状态
    """
    _check_deps()
    from psychopy import visual, core, event

    _emit({"status": "progress", "phase": "prepare", "message": "准备专注度基线训练..."})

    win = visual.Window(
        size=(1280, 720), fullscr=False, color=[0.94, 0.91, 0.85],
        units="height", allowGUI=True,
    )

    relax_text = visual.TextStim(win, text="请闭眼放松\n\n保持自然呼吸",
                                 height=0.06, color="#3F6850", bold=True)
    focus_text = visual.TextStim(win, text="请睁眼保持专注\n\n盯着屏幕中央的圆点",
                                 height=0.06, color="#5A8A6A", bold=True)
    free_text = visual.TextStim(win, text="自由状态\n\n保持正常状态即可",
                                height=0.06, color="#8BA89A", bold=True)
    dot = visual.Circle(win, radius=0.015, fillColor="#5A8A6A", lineColor=None)
    countdown = visual.TextStim(win, text="", height=0.04, color="#8BA89A")
    countdown.pos = (0, -0.2)

    clock = core.Clock()
    phases = [
        ("relax", relax_text, 10, False),
        ("focus", focus_text, 10, True),
        ("free", free_text, max(0, duration - 20), False),
    ]

    results = {"phases": {}, "total_duration": duration}

    for phase_name, text_stim, secs, show_dot in phases:
        if secs <= 0:
            continue

        _emit({"status": "progress", "phase": phase_name,
               "message": f"{'放松' if phase_name == 'relax' else '专注' if phase_name == 'focus' else '自由'}阶段 ({secs}秒)",
               "duration": secs})

        clock.reset()
        start_time = time.time()
        while clock.getTime() < secs:
            remaining = secs - clock.getTime()
            countdown.text = f"{int(remaining) + 1}"

            text_stim.draw()
            countdown.draw()
            if show_dot:
                dot.draw()

            win.flip()

            # 检查退出
            keys = event.getKeys(["escape", "q"])
            if keys:
                win.close()
                _emit({"status": "cancelled", "message": "用户取消"})
                return

        elapsed = time.time() - start_time
        results["phases"][phase_name] = {"duration": elapsed}
        _emit({"status": "progress", "phase": phase_name, "done": True,
               "duration": elapsed})

    win.close()
    _emit({"status": "complete", "results": results})


# ═══════════════════════════════════════════════════════════
# SSVEP 校准训练 — 与 Godot 游戏频率对齐
# ═══════════════════════════════════════════════════════════

# 思维贪吃蛇: ↑8Hz →10Hz ↓12Hz ←15Hz
SNAKE_FREQS = {
    "up": 8.0, "right": 10.0, "down": 12.0, "left": 15.0,
}
SNAKE_LABELS = {
    "up": "▲ 上 (8Hz)", "right": "→ 右 (10Hz)",
    "down": "↓ 下 (12Hz)", "left": "← 左 (15Hz)",
}

# 打地鼠: 7 个频率池 (2×2 ~ 4×4 网格)
MOLE_FREQ_POOL = [8.0, 9.2, 10.4, 11.6, 13.0, 14.4, 15.6]


def _try_lsl_outlet():
    """尝试创建 LSL 标记出口 (如果 pylsl 可用)"""
    try:
        from pylsl import StreamInfo, StreamOutlet
        info = StreamInfo(
            "MetaBCI-Training-Markers", "Markers", 1, 0,
            "string", "metabci_training_001"
        )
        return StreamOutlet(info)
    except Exception:
        return None


def run_ssvep_calibration(trials: int = 20, freqs: list = None, layout: str = "snake"):
    """
    SSVEP 校准训练 — 标准闪烁块，每轮提示目标频率。

    频率与 Godot 游戏严格对齐:
      - layout=snake: 4 方向箭头 (↑8Hz →10Hz ↓12Hz ←15Hz) — 思维贪吃蛇
      - layout=mole:  频率池 — 打地鼠

    通过 LSL 发送事件标记 (如果 pylsl 可用):
      "ssvep_cue,<freq>" — 提示阶段开始
      "ssvep_stim,<freq>" — 闪烁阶段开始
      "ssvep_rest" — 休息阶段
    """
    _check_deps()
    from psychopy import visual, core, event
    import numpy as np

    # 确定频率列表
    if freqs is None:
        if layout == "mole":
            freqs = MOLE_FREQ_POOL
        else:
            freqs = list(SNAKE_FREQS.values())

    # LSL 标记出口
    lsl_outlet = _try_lsl_outlet()

    n_elements = len(freqs)
    _emit({"status": "progress", "phase": "prepare",
           "message": f"准备 SSVEP 训练 ({layout}, {n_elements} 频率, {trials} 试次)...",
           "freqs": freqs, "trials": trials, "layout": layout,
           "lsl_markers": lsl_outlet is not None})

    win = visual.Window(
        size=(1280, 720), fullscr=False, color=[-1, -1, -1],
        units="pix", allowGUI=True,
    )

    fps = int(win.getActualFrameRate(nIdentical=10, nWarmUpFrames=10) or 60)
    win_size = win.size

    # 自适应布局 — 根据元素数量动态计算行列和块大小
    if n_elements <= 4:
        cols = 2 if n_elements <= 2 else 2
    elif n_elements <= 6:
        cols = 3
    else:
        cols = 4
    rows = (n_elements + cols - 1) // cols

    # 可用区域 (留边距和标签空间)
    avail_w = win_size[0] - 120
    avail_h = win_size[1] - 200
    cell_w = avail_w // cols
    cell_h = avail_h // rows
    block_w = block_h = min(cell_w, cell_h, 140) - 20
    label_offset = block_h // 2 + 20

    margin_x = (win_size[0] - cols * (block_w + 20)) // 2
    margin_y = (win_size[1] - rows * (block_h + label_offset + 10)) // 2 + 20

    positions = []
    for i in range(n_elements):
        r, c = divmod(i, cols)
        # 最后一行居中
        items_in_last_row = n_elements - (rows - 1) * cols
        if r == rows - 1 and items_in_last_row < cols:
            offset_x = (cols - items_in_last_row) * (block_w + 20) // 2
        else:
            offset_x = 0
        x = margin_x + c * (block_w + 20) + block_w // 2 - win_size[0] // 2 + offset_x
        y = win_size[1] // 2 - (margin_y + r * (block_h + label_offset + 10) + block_h // 2)
        positions.append((x, y))

    stim_time = 2.0

    # 频率标签
    if layout == "snake":
        dir_names = list(SNAKE_LABELS.values())
    else:
        dir_names = [f"{f:.1f} Hz" for f in freqs]

    freq_labels = []
    for i, label in enumerate(dir_names):
        lbl = visual.TextStim(win, text=label,
                              pos=(positions[i][0], positions[i][1] + label_offset),
                              height=18 if layout == "mole" else 20, color="#aaaaaa")
        freq_labels.append(lbl)

    # 退出提示
    exit_hint = visual.TextStim(win, text="按 Q 或 Esc 退出",
                                pos=(0, -win_size[1] // 2 + 30),
                                height=16, color="#666666")

    # 提示箭头
    cue = visual.TextStim(win, text="▼", height=30, color="#ff6600", bold=True)

    results = {"freqs": freqs, "layout": layout, "trials": []}

    import random
    trial_order = list(range(n_elements)) * (trials // n_elements)
    while len(trial_order) < trials:
        trial_order.append(random.randint(0, n_elements - 1))
    random.shuffle(trial_order)

    def _check_quit():
        """检查退出按键，返回 True 表示用户请求退出"""
        keys = event.getKeys(["escape", "q"])
        return bool(keys)

    for trial_idx, target in enumerate(trial_order):
        if _check_quit():
            break

        target_freq = freqs[target]
        target_label = dir_names[target] if target < len(dir_names) else f"{target_freq:.1f}Hz"

        _emit({"status": "progress", "phase": "trial",
               "trial": trial_idx + 1, "total": trials,
               "target_index": target, "target_freq": target_freq,
               "target_label": target_label,
               "trial_time": time.time()})

        # 提示阶段 (1s)
        if lsl_outlet:
            lsl_outlet.push_sample([f"ssvep_cue,{target_freq}"])
        cue.pos = (positions[target][0], positions[target][1] - label_offset)
        clock = core.Clock()
        while clock.getTime() < 1.0:
            if _check_quit(): break
            for i in range(n_elements):
                rect = visual.Rect(win, width=block_w, height=block_h,
                                   pos=positions[i], fillColor=[0.3, 0.3, 0.3],
                                   lineColor=[0.5, 0.5, 0.5])
                rect.draw()
                freq_labels[i].draw()
            cue.draw()
            exit_hint.draw()
            win.flip()
        if _check_quit(): break

        # 闪烁阶段 — 实时钟驱动，保证精确频率
        if lsl_outlet:
            lsl_outlet.push_sample([f"ssvep_stim,{target_freq}"])
        clock.reset()
        flip_times = []
        while clock.getTime() < stim_time:
            if _check_quit(): break
            elapsed = clock.getTime()
            flip_times.append(elapsed)
            for i in range(n_elements):
                # 基于实际时间计算亮度 → 频率精确，不受丢帧影响
                brightness = (np.sin(2 * np.pi * freqs[i] * elapsed) + 1) / 2
                c = [brightness * 2 - 1] * 3
                rect = visual.Rect(win, width=block_w, height=block_h,
                                   pos=positions[i],
                                   fillColor=c,
                                   lineColor=[0.5, 0.5, 0.5])
                rect.draw()
            exit_hint.draw()
            win.flip()
        # 验证帧率
        trial_fps = 0.0
        if len(flip_times) > 1:
            intervals = np.diff(flip_times)
            trial_fps = float(1.0 / np.mean(intervals)) if np.mean(intervals) > 0 else 0.0
            _emit({"status": "progress", "phase": "trial",
                   "trial": trial_idx + 1, "total": trials,
                   "target_index": target, "target_freq": target_freq,
                   "target_label": target_label,
                   "actual_fps": round(trial_fps, 1),
                   "frames": len(flip_times)})
        if _check_quit(): break

        # 短暂休息
        if lsl_outlet:
            lsl_outlet.push_sample(["ssvep_rest"])
        rest_frames = int(0.5 * fps)
        for _ in range(rest_frames):
            if _check_quit(): break
            for i in range(n_elements):
                rect = visual.Rect(win, width=block_w, height=block_h,
                                   pos=positions[i], fillColor=[0.2, 0.2, 0.2],
                                   lineColor=[0.3, 0.3, 0.3])
                rect.draw()
                freq_labels[i].draw()
            exit_hint.draw()
            win.flip()
        if _check_quit(): break

        results["trials"].append({
            "trial": trial_idx + 1, "target_index": target,
            "freq": target_freq, "label": target_label,
            "actual_fps": round(trial_fps, 1),
        })

    # 保存校准文件
    calib = _save_ssvep_calibration(results)
    if calib:
        results["calibration_file"] = calib

    win.close()
    _emit({"status": "complete", "results": results})


def _save_ssvep_calibration(results: dict) -> str | None:
    """保存 SSVEP 试次元数据为校准文件，供后续解码器使用"""
    try:
        calib_dir = os.path.expanduser("~/MetaBCI_Calibration")
        os.makedirs(calib_dir, exist_ok=True)
        calib_path = os.path.join(calib_dir, "ssvep_trials.json")

        calib_data = {
            "freqs": results["freqs"],
            "layout": results.get("layout", "snake"),
            "trials": results["trials"],
            "total_trials": len(results["trials"]),
            "freq_counts": {},
        }
        for t in results["trials"]:
            f = t["freq"]
            calib_data["freq_counts"][str(f)] = calib_data["freq_counts"].get(str(f), 0) + 1

        with open(calib_path, "w", encoding="utf-8") as f:
            json.dump(calib_data, f, ensure_ascii=False, indent=2)

        _emit({"status": "progress", "phase": "calibration",
               "message": f"校准文件已保存: {calib_path}",
               "freq_counts": calib_data["freq_counts"]})
        return calib_path
    except Exception as e:
        logger.warning(f"保存校准文件失败: {e}")
        return None


# ═══════════════════════════════════════════════════════════
# P300 校准训练
# ═══════════════════════════════════════════════════════════

def run_p300_calibration(trials: int = 12):
    """P300 校准训练 — 标准行列闪烁 oddball"""
    _check_deps()
    from psychopy import visual, core, event
    import numpy as np

    _emit({"status": "progress", "phase": "prepare",
           "message": f"准备 P300 训练 ({trials} 试次)...", "trials": trials})

    win = visual.Window(
        size=(1280, 720), fullscr=False, color=[-1, -1, -1],
        units="pix", allowGUI=True,
    )

    fps = int(win.getActualFrameRate(nIdentical=10, nWarmUpFrames=10) or 60)
    win_size = win.size

    # 3x2 网格
    rows, cols = 2, 3
    n_elements = rows * cols
    symbols = ["A", "B", "C", "D", "E", "F"]

    block_w, block_h = 140, 140
    grid_w = cols * block_w + (cols - 1) * 20
    grid_h = rows * block_h + (rows - 1) * 20
    start_x = -grid_w // 2 + block_w // 2
    start_y = -grid_h // 2 + block_h // 2

    positions = []
    for r in range(rows):
        for c in range(cols):
            x = start_x + c * (block_w + 20)
            y = start_y + r * (block_h + 20)
            positions.append((x, y))

    # 文字标签
    text_stims = []
    for i, sym in enumerate(symbols):
        ts = visual.TextStim(win, text=sym, pos=positions[i],
                             height=50, color="#ffffff", bold=True)
        text_stims.append(ts)

    stim_duration = 0.1
    stim_ISI = 0.025
    stim_frames_per = int(stim_duration * fps)
    isi_frames = int(stim_ISI * fps)

    # 退出提示
    exit_hint = visual.TextStim(win, text="按 Q 或 Esc 退出",
                                pos=(0, -win_size[1] // 2 + 30),
                                height=16, color="#666666")

    def _p3_check_quit():
        return bool(event.getKeys(["escape", "q"]))

    results = {"rows": rows, "cols": cols, "symbols": symbols, "trials": []}

    for trial_idx in range(trials):
        if _p3_check_quit():
            break

        target = trial_idx % n_elements

        _emit({"status": "progress", "phase": "trial",
               "trial": trial_idx + 1, "total": trials,
               "target_symbol": symbols[target]})

        # 提示目标 (1.5s)
        cue = visual.TextStim(win, text=f"请默想: {symbols[target]}",
                              height=40, color="#ff6600", bold=True)
        clock = core.Clock()
        while clock.getTime() < 1.5:
            if _p3_check_quit(): break
            for i in range(n_elements):
                rect = visual.Rect(win, width=block_w, height=block_h,
                                   pos=positions[i],
                                   fillColor=[0.2, 0.2, 0.2],
                                   lineColor=[0.4, 0.4, 0.4])
                rect.draw()
                text_stims[i].draw()
            cue.draw()
            exit_hint.draw()
            win.flip()
        if _p3_check_quit(): break

        # 闪烁阶段: 行列交替
        row_order = list(range(rows))
        col_order = list(range(cols))
        np.random.shuffle(row_order)
        np.random.shuffle(col_order)
        order_row_col = row_order + [r + rows for r in col_order]  # 行标签 1..rows, 列标签 rows+1..rows+cols

        for flash_idx in order_row_col:
            if _p3_check_quit(): break
            is_row = flash_idx < rows
            idx = flash_idx if is_row else flash_idx - rows

            # 高亮帧
            for _ in range(stim_frames_per):
                for i in range(n_elements):
                    r, c = divmod(i, cols)
                    highlight = (is_row and r == idx) or (not is_row and c == idx)
                    fill = [1, 1, 1] if highlight else [0.2, 0.2, 0.2]
                    rect = visual.Rect(win, width=block_w, height=block_h,
                                       pos=positions[i],
                                       fillColor=fill, lineColor=[0.4, 0.4, 0.4])
                    rect.draw()
                    text_stims[i].draw()
                exit_hint.draw()
                win.flip()

            # ISI 帧
            for _ in range(isi_frames):
                for i in range(n_elements):
                    rect = visual.Rect(win, width=block_w, height=block_h,
                                       pos=positions[i],
                                       fillColor=[0.2, 0.2, 0.2],
                                       lineColor=[0.4, 0.4, 0.4])
                    rect.draw()
                    text_stims[i].draw()
                exit_hint.draw()
                win.flip()
        if _p3_check_quit(): break

        results["trials"].append({"trial": trial_idx + 1, "target": target,
                                   "symbol": symbols[target]})

    win.close()
    _emit({"status": "complete", "results": results})


# ═══════════════════════════════════════════════════════════
# MI 校准训练
# ═══════════════════════════════════════════════════════════

def run_mi_calibration(trials: int = 20):
    """MI 运动想象校准训练 — 左右手想象提示"""
    _check_deps()
    from psychopy import visual, core, event

    _check_deps()

    _emit({"status": "progress", "phase": "prepare",
           "message": f"准备 MI 训练 ({trials} 试次)...", "trials": trials})

    win = visual.Window(
        size=(1280, 720), fullscr=False, color=[0.94, 0.91, 0.85],
        units="height", allowGUI=True,
    )

    # 左右提示
    left_arrow = visual.TextStim(win, text="←\n左手", height=0.08,
                                  color="#3F6850", bold=True)
    right_arrow = visual.TextStim(win, text="→\n右手", height=0.08,
                                   color="#5A8A6A", bold=True)
    rest_cross = visual.TextStim(win, text="+", height=0.08,
                                  color="#8BA89A", bold=True)
    status_text = visual.TextStim(win, text="", height=0.04,
                                   color="#B8936B", pos=(0, -0.3))

    fps = int(win.getActualFrameRate(nIdentical=10, nWarmUpFrames=10) or 60)
    results = {"trials": []}

    import random
    sides = ["left"] * (trials // 2) + ["right"] * (trials // 2)
    while len(sides) < trials:
        sides.append("left")
    random.shuffle(sides)

    # 退出提示
    exit_hint = visual.TextStim(win, text="按 Q 或 Esc 退出",
                                height=16, color="#888888", pos=(0, -0.4))

    def _mi_check_quit():
        return bool(event.getKeys(["escape", "q"]))

    for trial_idx, side in enumerate(sides):
        if _mi_check_quit():
            break

        _emit({"status": "progress", "phase": "trial",
               "trial": trial_idx + 1, "total": trials, "side": side})

        arrow = left_arrow if side == "left" else right_arrow

        # 休息 (2s)
        clock = core.Clock()
        while clock.getTime() < 2.0:
            if _mi_check_quit(): break
            rest_cross.draw()
            status_text.text = f"休息 ({int(2.0 - clock.getTime()) + 1}s)"
            status_text.draw()
            exit_hint.draw()
            win.flip()

        # 准备提示 (1s)
        clock.reset()
        while clock.getTime() < 1.0:
            if _mi_check_quit(): break
            arrow.draw()
            status_text.text = "准备..."
            status_text.draw()
            exit_hint.draw()
            win.flip()

        # 运动想象 (4s)
        clock.reset()
        while clock.getTime() < 4.0:
            if _mi_check_quit(): break
            arrow.draw()
            status_text.text = f"想象{'左手' if side == 'left' else '右手'}运动！"
            status_text.draw()
            exit_hint.draw()
            win.flip()

        results["trials"].append({"trial": trial_idx + 1, "side": side})

    win.close()
    _emit({"status": "complete", "results": results})


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

MODES = {
    "focus_baseline": run_focus_baseline,
    "ssvep": run_ssvep_calibration,
    "p300": run_p300_calibration,
    "mi": run_mi_calibration,
}


def main():
    parser = argparse.ArgumentParser(description="MetaBCI brainstim 训练脚本")
    parser.add_argument("--mode", choices=MODES.keys(), required=True,
                        help="训练模式")
    parser.add_argument("--duration", type=int, default=30,
                        help="专注度基线时长 (秒)")
    parser.add_argument("--trials", type=int, default=20,
                        help="训练试次数")
    parser.add_argument("--freqs", type=str, default=None,
                        help="SSVEP 频率列表 (逗号分隔, 默认根据 layout 自动选择)")
    parser.add_argument("--layout", type=str, default="snake",
                        choices=["snake", "mole"],
                        help="SSVEP 布局: snake=方向箭头(4频) mole=网格(7频)")
    args = parser.parse_args()

    mode_func = MODES[args.mode]

    try:
        if args.mode == "focus_baseline":
            mode_func(duration=args.duration)
        elif args.mode == "ssvep":
            freqs = None
            if args.freqs:
                freqs = [float(f) for f in args.freqs.split(",")]
            mode_func(trials=args.trials, freqs=freqs, layout=args.layout)
        elif args.mode in ("p300", "mi"):
            mode_func(trials=args.trials)
    except SystemExit:
        pass  # _check_deps 或其他正常退出
    except Exception as e:
        import traceback
        _emit({"status": "error", "message": f"{type(e).__name__}: {e}",
               "traceback": traceback.format_exc()[-500:]})


if __name__ == "__main__":
    main()
