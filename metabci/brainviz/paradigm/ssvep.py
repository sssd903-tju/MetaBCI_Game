# -*- coding: utf-8 -*-
"""
SSVEP 稳态视觉诱发电位范式
"""

from metabci.brainviz.paradigm.base import BaseParadigm, Electrode, TEN_TWENTY_ELECTRODES


class SSVEPParadigm(BaseParadigm):
    def __init__(self):
        super().__init__(
            paradigm_id="ssvep",
            name="SSVEP",
            icon="👁",
            description="用眼睛「选择」方向！盯着闪烁的光看，大脑自动跟上节奏",
            color="#FF6F00",
            result_label='方向识别',
            explain_summary=(
                'O1 和 O2 两个电极放在后脑勺——这里是大脑的「视觉中心」！'
                '眼睛看到闪烁的光，后脑勺的脑细胞就会跟着一起"打节拍"。'
            ),
            explain_principle=(
                '上下左右四个方向的光，各以不同的速度闪烁（比如 8 次/秒、10 次/秒……）。'
                '你盯着哪个方向看，后脑勺的脑电波就会跟哪个频率对上。'
                '电脑一秒就能「猜」出你在看哪里，准确率超过 70%！'
            ),
            ws_port=8769,
            active_electrodes=[
                e for e in TEN_TWENTY_ELECTRODES
                if e.name in ("O1", "O2")
            ],
            all_electrodes=TEN_TWENTY_ELECTRODES,
            pipeline_steps=[
                "O1/O2 采集视觉皮层 EEG",
                "带通滤波 (目标频率附近)",
                "CCA 典型相关分析 → 与各频率模板匹配",
                "最大相关系数对应的频率 → 识别目标方向",
                "WebSocket → Godot 蛇移动/打地鼠",
            ],
            science={
                "signal": """
                <h3>👁 视觉皮层 — SSVEP 的信号来源</h3>
                <p>SSVEP 使用 <b>O1、O2、Oz、POz</b> 电极，位于大脑枕叶（视觉皮层）。</p>
                <p>当眼睛注视闪烁光源时，视觉皮层的神经元<b>以相同频率同步放电</b>，产生稳态视觉诱发电位。</p>
                <h4>为什么是枕叶？</h4>
                <p>枕叶是大脑的<b>视觉处理中枢</b>。视网膜信号经丘脑传递到初级视觉皮层 (V1)，这里对闪烁刺激最为敏感。</p>
                """,
                "process": """
                <h3>🔧 CCA 典型相关分析</h3>
                <p>CCA 寻找两组变量之间的最大相关性。在 SSVEP 中：</p>
                <ul>
                <li><b>一组</b>：多通道 EEG 信号</li>
                <li><b>另一组</b>：参考频率的正弦/余弦模板</li>
                </ul>
                <p>每个频率都有一组模板。CCA 计算 EEG 与每个模板的相关系数，<b>最大者即为识别频率</b>。</p>
                <p>MetaBCI brainda 提供: FBMsCCA, FBeCCA, TRCA, TDCA 等多种算法。</p>
                """,
                "decode": """
                <h3>🧮 频率 → 方向映射</h3>
                <p>4 个闪烁目标，每个以不同频率闪烁（如 8Hz、10Hz、12Hz、15Hz），对应上下左右四个方向。</p>
                <p>系统实时计算 EEG 与各频率的相关系数，<b>系数最高的频率</b>即为用户注视的目标。</p>
                <p style="font-size:16px;text-align:center;"><b>正确率 ≥ 70%，识别时间 1-2 秒</b></p>
                """,
                "control": """
                <h3>🎮 SSVEP → 方向控制</h3>
                <ul>
                <li><b>思维贪吃蛇</b>：注视不同频率目标控制蛇的移动方向</li>
                <li><b>打地鼠</b>：注视闪烁的地鼠洞来控制锤子落点</li>
                </ul>
                <p>解码结果通过 <b>WebSocket (端口 8769)</b> 发送给 Godot。</p>
                """,
            },
        )
