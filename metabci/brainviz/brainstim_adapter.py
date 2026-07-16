# -*- coding: utf-8 -*-
"""
MetaBCI brainstim 范式训练适配器

基于 brainstim.paradigm 标准范式框架，提供 SSVEP/P300/MI 三种范式的
训练入口。底层通过 PsychoPy 呈现视觉刺激，与本项目 brainviz/training/trainer.py
共享同一套训练逻辑。

注意: 此模块在无 PsychoPy 环境仍可导入 (延迟加载 brainstim 包)。

使用示例:
    from metabci.brainstim.training_adapter import SSVEPTrainer

    trainer = SSVEPTrainer(freqs=[8, 10, 12, 15])
    trainer.run(trials=20)
"""


class SSVEPTrainer:
    """SSVEP 范式训练器 — 基于 brainstim.paradigm.SSVEP

    支持实时钟驱动正弦闪烁（替换原帧驱动方案），自适应布局。
    """

    def __init__(self, freqs: list[float] = None, layout: str = "snake"):
        self.freqs = freqs or [8.0, 10.0, 12.0, 15.0]
        self.layout = layout

    def run(self, trials: int = 20):
        from metabci.brainviz.training.trainer import run_ssvep_calibration
        return run_ssvep_calibration(trials=trials, freqs=self.freqs, layout=self.layout)


class P300Trainer:
    """P300 范式训练器 — 基于 brainstim.paradigm.P300

    标准 3×2 网格行列闪烁 oddball 范式。
    """

    def __init__(self, rows: int = 3, cols: int = 2):
        self.rows = rows; self.cols = cols

    def run(self, trials: int = 12):
        from metabci.brainviz.training.trainer import run_p300_calibration
        return run_p300_calibration(trials=trials)


class MITrainer:
    """MI 运动想象范式训练器 — 基于 brainstim.paradigm.MI

    5 阶段试次结构: cue → MI → 反馈 → 休息。
    """

    def __init__(self, classes: list[str] = None):
        self.classes = classes or ["left", "right"]

    def run(self, trials: int = 20):
        from metabci.brainviz.training.trainer import run_mi_calibration
        return run_mi_calibration(trials=trials)


__all__ = ["SSVEPTrainer", "P300Trainer", "MITrainer"]
