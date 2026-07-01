# -*- coding: utf-8 -*-
"""
MI 运动想象范式
"""

from metabci.brainviz.paradigm.base import BaseParadigm, Electrode, TEN_TWENTY_ELECTRODES


class MIParadigm(BaseParadigm):
    def __init__(self):
        super().__init__(
            paradigm_id="mi",
            name="运动想象",
            icon="💪",
            description="不动手、光想！想象左手右手，电脑能「猜」到你想哪边",
            color="#29B6F6",
            result_label='运动想象',
            explain_summary=(
                'C3 和 C4 贴在头顶两侧——这里是大脑的「运动指挥部」！'
                '你想象左手动，大脑右侧就忙起来；想象右手动，左侧就活跃。'
                '虽然手没真的动，但脑电信号已经暴露了你的想法！'
            ),
            explain_principle=(
                '这是唯一不需要看屏幕、不需要听声音的范式——'
                '纯靠"想象"就能控制！想象左手 → 向左，想象右手 → 向右。'
                '多多练习，电脑猜对的概率能超过 65%。'
                '就像学会了「意念超能力」！'
            ),
            ws_port=8769,
            active_electrodes=[
                e for e in TEN_TWENTY_ELECTRODES
                if e.name in ("C3", "C4")
            ],
            all_electrodes=TEN_TWENTY_ELECTRODES,
            pipeline_steps=[
                "C3/C4 采集感觉运动皮层 EEG",
                "带通滤波 8-30Hz (μ+β 节律)",
                "CSP 共空间模式 → 最优区分左右手",
                "分类器 (LDA/SVM) → 识别想象侧",
                "WebSocket → Godot 跳跃方向控制",
            ],
            science={
                "signal": """
                <h3>💪 感觉运动皮层 — MI 的信号来源</h3>
                <p>运动想象使用 <b>C3 和 C4</b> 电极，位于大脑中央两侧的感觉运动皮层。</p>
                <p><b>C3</b> 对应右侧肢体控制（左手想象），<b>C4</b> 对应左侧肢体控制（右手想象）。</p>
                <h4>ERD/ERS 现象</h4>
                <p>想象运动时，对侧感觉运动皮层的 μ 节律 (8-12Hz) 和 β 节律 (13-30Hz) 能量<b>下降</b>——称为<b>事件相关去同步 (ERD)</b>。</p>
                """,
                "process": """
                <h3>🔧 CSP 共空间模式</h3>
                <p>CSP 是一种空间滤波算法，找到<b>最优区分两类运动想象</b>的电极权重组合。</p>
                <p>它最大化一类信号的方差同时最小化另一类的方差，使 C3 和 C4 的差异最大化。</p>
                <p>MetaBCI brainda 提供: CSP, FBCSP, multiCSP, DSP 等多种变体。</p>
                """,
                "decode": """
                <h3>🧮 左右手二分类</h3>
                <p>CSP 提取特征后，用 <b>LDA 或 SVM</b> 分类器判断用户在想左手还是右手。</p>
                <p>C3 能量下降 → 右手想象；C4 能量下降 → 左手想象。</p>
                <p style="font-size:16px;text-align:center;"><b>二分类正确率 ≥ 65%，需要 2-3 秒数据</b></p>
                """,
                "control": """
                <h3>🎮 MI → 方向控制</h3>
                <ul>
                <li><b>跳跃方向选择</b>：想象左手→左跳，想象右手→右跳</li>
                </ul>
                <p>解码结果通过 <b>WebSocket (端口 8769)</b> 发送给 Godot。</p>
                """,
            },
        )
