# -*- coding: utf-8 -*-
"""
专注度检测范式
"""

from metabci.brainviz.paradigm.base import BaseParadigm, Electrode, TEN_TWENTY_ELECTRODES


class FocusParadigm(BaseParadigm):
    def __init__(self):
        super().__init__(
            paradigm_id="focus",
            name="专注度检测",
            icon="🧠",
            description="测测你的注意力有多集中！额头贴片「听」脑电波",
            color="#4CAF50",
            result_label='专注度',
            explain_summary=(
                '你知道吗？大脑的前额叶就像「指挥官」，帮我们集中注意力。'
                'Fp1 和 Fp2 两个电极贴在额头，就能「听到」大脑的专注信号！'
            ),
            explain_principle=(
                '大脑里有不同的"脑电波"：放松时 α 波变强，紧张时 β 波变多。'
                '我们用一个简单公式：专注度 = (α + θ) / β，'
                '分数越高 = 你越专注！游戏开始前先花 10 秒测一下你的「平静状态」，'
                '之后就能看到自己有没有比平时更集中精神啦。'
            ),
            ws_port=8768,
            active_electrodes=[
                e for e in TEN_TWENTY_ELECTRODES
                if e.name in ("Fp1", "Fp2")
            ],
            all_electrodes=TEN_TWENTY_ELECTRODES,
            pipeline_steps=[
                "Fp1/Fp2 采集原始 EEG",
                "带通滤波 0.5-45Hz + 陷波 50Hz",
                "Welch PSD → θ(4-8) α(8-13) β(13-30) 频带能量",
                "专注度 = (θ+α)/β → 百分制 (基线=50)",
                "WebSocket → Godot 准星/光圈控制",
            ],
            science={
                "signal": """
                <h3>🧠 前额叶 — 专注度的大脑来源</h3>
                <p>专注度检测使用 <b>Fp1 和 Fp2</b> 电极，位于前额叶（额极）。</p>
                <p>前额叶是大脑的<b>"执行控制中心"</b>，负责注意力调节、决策和情绪管理。</p>
                <h4>为什么是前额叶？</h4>
                <ul>
                <li>θ 波 (4-8Hz) 在放松冥想时增强</li>
                <li>α 波 (8-13Hz) 在闭眼平静时增强</li>
                <li>β 波 (13-30Hz) 在紧张焦虑时增强</li>
                </ul>
                <p><b>比值越高 = 越放松而专注；比值越低 = 越紧张或分心。</b></p>
                """,
                "process": """
                <h3>🔧 频带能量提取</h3>
                <p>原始 EEG 包含从 0.5Hz 到 100Hz 的各种频率成分。我们用 <b>Welch 方法</b>计算功率谱密度 (PSD)，然后提取三个关键频带。</p>
                <p>带通滤波保留 0.5-45Hz（去除直流漂移和高频噪声），陷波滤波去除 50Hz 工频干扰。</p>
                """,
                "decode": """
                <h3>🧮 百分制专注度</h3>
                <p>专注度 = (θ能量 + α能量) / β能量</p>
                <p>游戏开始前进行 <b>10秒基线校准</b>，计算个人平均比值。之后将当前比值与基线比较：</p>
                <p style="font-size:16px;text-align:center;"><b>百分制 = (当前比值 / 基线比值) × 50</b></p>
                <p>50% = 你的正常水平，>65% = 高专注，<35% = 低专注。</p>
                """,
                "control": """
                <h3>🎮 专注度 → 游戏控制</h3>
                <ul>
                <li><b>凝神一矢（射箭）</b>：专注度控制准星向靶心靠拢的速度和抖动</li>
                <li><b>深海下潜</b>：专注度控制探照灯光圈大小和氧气消耗速度</li>
                </ul>
                <p>专注度通过 <b>WebSocket (端口 8768)</b> 以 JSON 格式实时发送给 Godot 游戏引擎。</p>
                """,
            },
        )
