# -*- coding: utf-8 -*-
"""
科普教育面板 — BCI 知识 + 范式原理
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextBrowser, QListWidget, QListWidgetItem,
    QSplitter
)
from PySide6.QtCore import Qt

from metabci.brainviz.config import COLORS

SCIENCE_CONTENT = {
    "什么是脑机接口？": """
<h3>脑机接口 (Brain-Computer Interface, BCI)</h3>
<p>脑机接口是一种<b>不依赖外周神经和肌肉</b>，直接在大脑与外部设备之间建立通信的技术。</p>
<h4>工作原理</h4>
<ol>
<li><b>信号采集</b> — 通过电极从头皮采集脑电信号 (EEG)</li>
<li><b>信号处理</b> — 滤波、去噪、提取特征</li>
<li><b>模式识别</b> — 用算法解码用户意图</li>
<li><b>指令输出</b> — 将结果转化为控制命令</li>
</ol>
<h4>MetaBCI 平台架构</h4>
<p>
<b>brainflow</b> → 数据采集与预处理<br>
<b>brainda</b> → 算法解码 (CCA/CSP/P300/深度学习)<br>
<b>brainstim</b> → 范式呈现 (SSVEP/MI/P300)<br>
<b>brainviz</b> → 实时可视化 (本模块)
</p>
""",

    "脑电波的五种节律": """
<h3>脑电节律 (EEG Rhythms)</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>δ 波</b></td><td>0.5-4 Hz</td><td>深度睡眠</td></tr>
<tr><td><b>θ 波</b></td><td>4-8 Hz</td><td>冥想、困倦、放松</td></tr>
<tr><td><b>α 波</b></td><td>8-13 Hz</td><td>闭眼放松、平静专注</td></tr>
<tr><td><b>β 波</b></td><td>13-30 Hz</td><td>活跃思考、注意力集中、紧张</td></tr>
<tr><td><b>γ 波</b></td><td>30-45 Hz</td><td>高级认知、信息整合</td></tr>
</table>
<h4>专注度公式</h4>
<p style="background:#3A3A3A; padding:8px; border-radius:4px;">
专注度 = (θ + α) / β<br>
<i>越放松而清醒，比值越高；越紧张焦虑，比值越低。</i>
</p>
""",

    "SSVEP 范式原理": """
<h3>稳态视觉诱发电位 (SSVEP)</h3>
<p>当人眼注视一个<b>以特定频率闪烁</b>的视觉刺激时，大脑视觉皮层会产生<b>相同频率</b>的脑电响应。</p>
<h4>MetaBCI 实现</h4>
<ul>
<li>brainstim: 正弦采样法生成刺激 (sinusoidal_sample)</li>
<li>brainda: CCA / eCCA / TRCA / TDCA 解码算法</li>
<li>关键算法: FBMsCCA, FBeCCA, sceTRCA</li>
</ul>
<h4>特点</h4>
<ul><li>识别准确率高 (≥90%)</li><li>无需训练</li><li>可支持多目标</li></ul>
""",

    "P300 范式原理": """
<h3>P300 事件相关电位</h3>
<p>当大脑识别到<b>小概率、目标刺激</b>时，在刺激出现后约 <b>300ms</b> 会产生一个正向电位峰值。</p>
<h4>MetaBCI 实现</h4>
<ul>
<li>brainstim: Oddball 范式随机闪烁</li>
<li>brainda: LDA / Bayesian 动态停止</li>
<li>深度学习: EEGNet, DeepNet</li>
</ul>
<h4>特点</h4>
<ul><li>适合多选项场景</li><li>无需主动运动</li><li>单次识别需时间叠加</li></ul>
""",

    "运动想象 (MI) 范式原理": """
<h3>运动想象 (Motor Imagery)</h3>
<p>当人<b>想象</b>肢体运动时，感觉运动皮层的 μ 节律 (8-12Hz) 和 β 节律发生<b>事件相关去同步 (ERD)</b>。</p>
<h4>MetaBCI 实现</h4>
<ul>
<li>brainda: CSP / FBCSP / multiCSP 特征提取</li>
<li>分类器: LDA, SVM, MDMR</li>
<li>深度学习: EEGNet, ShallowNet, ConvNet</li>
<li>迁移学习: MEKT, SAME, LST, RPA</li>
</ul>
<h4>特点</h4>
<ul><li>无需外部刺激</li><li>适合意念控制</li><li>需要训练 (个体差异大)</li></ul>
""",

    "MetaBCI 数据流架构": """
<h3>MetaBCI 数据流程</h3>
<pre style="background:#3A3A3A; padding:8px; border-radius:4px;">
LSL 数据流 → brainflow (采集/预处理)
              ↓
         brainda (算法解码)
              ↓
         brainstim (范式呈现)  ←→  brainviz (可视化)
              ↓
         WebSocket → Godot 游戏引擎
</pre>
<h4>关键指标</h4>
<ul>
<li>在线延迟 &lt; 50ms (LSL → 处理 → 反馈)</li>
<li>支持 1-16 导联</li>
<li>250Hz 采样率</li>
</ul>
""",
}


class SciencePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(QLabel("📖 科普讲解"))

        splitter = QSplitter(Qt.Orientation.Vertical)

        self._list = QListWidget()
        self._list.setStyleSheet(f"""
            QListWidget {{
                background: {COLORS['bg_panel']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['grid']}; border-radius: 6px; font-size: 13px;
            }}
            QListWidget::item {{ padding: 8px 12px; border-bottom: 1px solid {COLORS['grid']}; }}
            QListWidget::item:selected {{ background: {COLORS['accent_green']}; color: white; }}
            QListWidget::item:hover {{ background: #4A4A4A; }}
        """)
        for topic in SCIENCE_CONTENT:
            self._list.addItem(QListWidgetItem(topic))
        self._list.currentTextChanged.connect(self._on_select)
        splitter.addWidget(self._list)

        self._content = QTextBrowser()
        self._content.setStyleSheet(f"""
            QTextBrowser {{
                background: {COLORS['bg_dark']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['grid']}; border-radius: 6px;
                padding: 8px; font-size: 12px;
            }}
        """)
        self._content.setOpenExternalLinks(True)
        splitter.addWidget(self._content)

        splitter.setSizes([200, 600])
        layout.addWidget(splitter)
        self._list.setCurrentRow(0)

    def _on_select(self, topic: str):
        self._content.setHtml(SCIENCE_CONTENT.get(topic, ""))
