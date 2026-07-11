# -*- coding: utf-8 -*-
"""
P300 事件相关电位范式
"""

from metabci.brainviz.paradigm.base import BaseParadigm, Electrode, TEN_TWENTY_ELECTRODES


class P300Paradigm(BaseParadigm):
    def __init__(self):
        super().__init__(
            paradigm_id="p300",
            name="P300",
            icon="⚡",
            description="心里默想目标，大脑「举报」你在想哪个！",
            color="#E91E63",
            result_label='目标检测',
            explain_summary=(
                'Pz 和 Cz 贴在头顶——这里是大脑的「惊讶中心」！'
                '当你在心里默想某个目标时，每次它一闪，'
                '大脑就会在大约 0.3 秒后冒出一个叫 P300 的电信号。'
            ),
            explain_principle=(
                '屏幕上好几张卡牌轮流闪，你心里只数你想选的那张。'
                '虽然每次 P300 信号很小，但多闪几次叠加起来就明显了。'
                '电脑找到 P300 最强的那个，就知道你心里想的是哪张牌！'
                '正确率超过 70%，像「读心术」一样神奇。'
            ),
            ws_port=8769,
            active_electrodes=[
                e for e in TEN_TWENTY_ELECTRODES
                if e.name in ("Pz", "Cz")
            ],
            all_electrodes=TEN_TWENTY_ELECTRODES,
            pipeline_steps=[
                "Pz/Cz 采集中线 EEG",
                "带通滤波 0.5-15Hz (P300 频段)",
                "刺激锁定分段 → 多试次叠加平均",
                "检测刺激后 ~300ms 正向峰值 → 识别目标",
                "WebSocket → Godot 卡牌/采矿目标选中",
            ],
            science={
                "signal": """
                <h3>⚡ 顶叶中线 — P300 的来源</h3>
                <p>P300 使用 <b>Pz、Cz</b> 电极，位于大脑顶叶中线。</p>
                <p>P300 是<b>认知电位</b>，反映大脑对意外/目标刺激的注意加工，在刺激出现后约 <b>300ms</b> 达到峰值。</p>
                <h4>为什么是中线？</h4>
                <p>P300 源于顶叶-额叶网络的同步活动，中线电极能最好地捕捉这一广泛分布的电位。</p>
                """,
                "process": """
                <h3>🔧 叠加平均去噪</h3>
                <p>单次 P300 淹没在背景 EEG 噪声中。通过<b>多次重复刺激并对齐叠加</b>，随机噪声相互抵消，P300 波形浮现。</p>
                <p>典型的 <b>Oddball 范式</b>：目标刺激（小概率）和标准刺激（大概率）随机交替出现。</p>
                <p>MetaBCI brainda 提供 LDA、Bayesian 动态停止等解码算法。</p>
                """,
                "decode": """
                <h3>🧮 P300 峰值检测</h3>
                <p>在刺激后 250-500ms 时间窗内搜索正向峰值。</p>
                <p>目标刺激的 ERP 波形在该时间窗内显著高于标准刺激。</p>
                <p style="font-size:16px;text-align:center;"><b>正确率 ≥ 70%，需要 5-10 次重复叠加</b></p>
                """,
                "control": """
                <h3>🎮 P300 → 目标选择</h3>
                <ul>
                <li><b>卡牌读心</b>：6 张卡牌随机闪烁，检测 P300 识别用户关注的卡牌</li>
                <li><b>太空采矿</b>：6 颗小行星随机闪烁，选中目标矿物</li>
                </ul>
                <p>解码结果通过 <b>WebSocket (端口 8769)</b> 发送给 Godot。</p>
                """,
            },
        )
