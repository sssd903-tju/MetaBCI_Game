# -*- coding: utf-8 -*-
"""
算法工坊 — 插槽式管线 (Scheme B v2)
预处理: 多选勾选 | 特征提取/分类器: 范式相关单选
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QTextBrowser, QButtonGroup, QCheckBox,
    QSizePolicy, QDoubleSpinBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from metabci.brainviz.theme import TEXT, TEXT2, TEXT3, ACCENT, SURFACE, SURFACE2, BORDER
from metabci.brainviz.paradigm import PARADIGM_LIST, BaseParadigm

# ============================================================
# 算法数据
# ============================================================

PREPROC_OPTIONS = {
    '带通滤波': {'desc': '保留有效脑电频段，去除噪声',
                 'short': '像筛子一样，只让有用的脑电波通过，把噪音挡在外面。'},
    '陷波滤波': {'desc': '去除 50Hz 工频干扰',
                 'short': '精准拔掉50Hz这根"电线噪音"，它是插座里传来的。'},
    '基线校正': {'desc': '让信号回到零线附近',
                 'short': '把飘走的信号拉回来，让波形在中间线上上下摆动。'},
}

# 生动图文解释
STUDENT_GUIDE = """
<div style='line-height:1.8;'>
<h3>给同学们的话</h3>
<p>脑电信号就像<b>一个很轻的声音</b>，周围有很多噪音：</p>
<table>
<tr><td>汗水、电极移动</td><td>→ 信号慢慢飘走</td><td>基线校正 拉回来</td></tr>
<tr><td>肌肉活动、咬牙</td><td>→ 高频毛刺</td><td>带通滤波 挡在外面</td></tr>
<tr><td>电线（50Hz交流电）</td><td>→ 嗡嗡声干扰</td><td>陷波滤波 精准拔掉</td></tr>
</table>
<p><b>三个工具一起用，就能得到干净的脑电波！</b></p>
<p style='color:#9ca3af;font-size:11px;'>MetaBCI: scipy.signal.butter / iirnotch / filtfilt</p>
</div>"""

FEATURE_GUIDE = {
    'PSD频带能量': "<div style='line-height:1.8;'><h3>频带能量 — 数数不同节奏的脑电波</h3><p>就像音乐有低音、中音、高音，脑电波也分五个频段：</p><table><tr><td>δ 0.5-4Hz</td><td>深度睡眠时的慢波</td></tr><tr><td>θ 4-8Hz</td><td>放松、发呆时出现</td></tr><tr><td>α 8-13Hz</td><td>闭眼放松、平静专注</td></tr><tr><td>β 13-30Hz</td><td>思考、紧张、专注</td></tr><tr><td>γ 30-45Hz</td><td>高度集中、信息整合</td></tr></table><p>专注度 = β/(θ+α)。越放松专注，β越强、α越弱，分数越高！</p></div>",
    'CSP空间滤波': "<div style='line-height:1.8;'><h3>CSP — 找到左右手的'开关'</h3><p>想象一下：C3和C4两个电极在头顶两侧。</p><p>想象<b>左手</b>动 → C4活跃、C3安静<br>想象<b>右手</b>动 → C3活跃、C4安静</p><p>CSP算法就是找到<b>让这个差异最大化的方法</b>，就像调收音机找到最清晰的频道。</p></div>",
    'CCA特征': "<div style='line-height:1.8;'><h3>CCA — 脑电波'和声'检测</h3><p>你盯着一个以10Hz闪烁的光，后脑勺的脑细胞就会跟着10Hz的节奏一起'唱歌'。</p><p>CCA算法做的事：<b>拿各个频率的'歌谱'去和脑电波对比，看和哪个频率最合拍。</b>最合拍的那个就是你正在看的方向！</p></div>",
    '时域分段': "<div style='line-height:1.8;'><h3>时域分段 — 给脑电波'拍照'</h3><p>每次刺激出现（比如卡牌闪了一下），大脑都会做出反应。</p><p>我们以刺激出现的瞬间为基准，截取前后一小段脑电波。多截几次，叠加平均，随机噪声抵消了，P300信号就浮现出来了！</p></div>",
}

CLASSIFIER_GUIDE = {
    'β/(θ+α) 比值': "<div style='line-height:1.8;'><h3>专注度 = β ÷ (θ+α)</h3><p>很简单！放松时的α和θ能量，除以紧张时的β能量。</p><p>比值<b>越高 → 越专注</b>，比值<b>越低 → 越分心</b>。</p><p>游戏前先测10秒你的'平静状态'作为基准（100%），之后就能看到自己是比平时更专注还是更分心。</p></div>",
    'CCA分类': "<div style='line-height:1.8;'><h3>CCA — 最佳匹配 wins!</h3><p>四个方向、四个频率。CCA算出哪个频率和脑电波最'合拍'，那个方向就赢了！</p><p>就像KTV打分——你唱得最接近哪首歌的旋律，就判定你唱的是哪首。</p></div>",
    'LDA': "<div style='line-height:1.8;'><h3>LDA — 画一条线分开两类</h3><p>想象黑棋和白棋混在一起，LDA就是找到最好的一条线把它们分开。</p><p>对P300：分开'目标刺激'和'非目标刺激'的脑电反应。<br>对MI：分开'左手想'和'右手想'的脑电特征。</p></div>",
}


FEATURE_OPTIONS = {
    'focus': [
        ('PSD频带能量', 'Welch方法计算δθαβγ功率谱密度',
         '<h3>PSD 频带能量</h3><p>使用Welch方法计算功率谱密度，提取五个频带能量：δ(0.5-4) θ(4-8) α(8-13) β(13-30) γ(30-45)。</p><p>专注度=β/(θ+α) 就是基于这些频带。</p><p><b>MetaBCI:</b> <code>brainda.algorithms.feature_analysis.freq_analysis</code></p>'),
    ],
    'ssvep': [
        ('CCA特征', '多通道典型相关分析提取频率成分',
         '<h3>CCA 特征提取</h3><p>对多通道EEG与各频率参考模板做CCA，取最大相关系数作为特征。</p><p><b>MetaBCI:</b> <code>brainda.algorithms.decomposition.cca</code></p>'),
    ],
    'p300': [
        ('时域分段', '刺激锁定分段 + 叠加平均',
         '<h3>时域分段 (Epoching)</h3><p>以刺激出现时刻为基准，截取前后时间窗（如-100ms到600ms），多试次叠加平均后ERP波形浮现。</p><p><b>MetaBCI:</b> 基于 <code>brainda.paradigms</code> 的分段逻辑</p>'),
    ],
    'mi': [
        ('CSP空间滤波', '共空间模式最大化左右手特征差异',
         '<h3>CSP 共空间模式</h3><p>找到一组空间滤波器，最大化两类运动想象的方差差异。C3/C4信号经过CSP后差异极大化，是MI最经典的特征提取方法。</p><p><b>MetaBCI:</b> <code>brainda.algorithms.decomposition.csp</code></p>'),
        ('FBCSP', '滤波器组CSP，多频带并行提取',
         '<h3>FBCSP 滤波器组CSP</h3><p>在多个子频带上分别做CSP，再融合特征。比单频带CSP效果更好。</p><p><b>MetaBCI:</b> 基于 <code>csp.py</code> 扩展</p>'),
    ],
}

CLASSIFIER_OPTIONS = {
    'focus': [
        ('β/(θ+α) 比值', '频带能量比值计算专注度百分制',
         '<h3>β/(θ+α) 专注度算法</h3><p>这是我们为MetaBCI新增的专注度评估算法。计算θ和α能量之和与β能量的比值，再转为百分制。</p><p><b>MetaBCI新增:</b> 专注度评估算法</p>'),
    ],
    'ssvep': [
        ('CCA分类', '最大相关系数对应频率即为目标',
         '<h3>CCA 分类</h3><p>计算EEG与各频率模板的相关系数，最大值对应的频率即为注视目标。入门级，适合教学演示。</p><p><b>MetaBCI:</b> <code>brainda.algorithms.decomposition.cca</code></p>'),
        ('TRCA', '任务相关成分分析，信噪比更高',
         '<h3>TRCA 任务相关成分分析</h3><p>通过最大化试次间相关性提取SSVEP成分，比CCA更抗噪。</p><p><b>MetaBCI:</b> <code>brainda.algorithms.decomposition.tdca</code></p>'),
    ],
    'p300': [
        ('LDA', '线性判别分析，叠加平均后分类',
         '<h3>LDA 线性判别分析</h3><p>在P300时间窗内提取特征，用LDA区分目标/非目标。经典P300分类方法。</p><p><b>MetaBCI:</b> <code>brainda.algorithms.dynamic_stopping.lda</code></p>'),
        ('Bayesian', '贝叶斯动态停止，自适应试次数',
         '<h3>Bayesian 动态停止</h3><p>每试次后计算后验概率，达到置信阈值后停止。减少不必要的闪烁次数。</p><p><b>MetaBCI:</b> <code>brainda.algorithms.dynamic_stopping.bayes</code></p>'),
    ],
    'mi': [
        ('LDA', '线性判别分析，CSP特征后分类',
         '<h3>LDA 分类器</h3><p>CSP提取特征后，用LDA做二分类。简单高效，MI基线方法。</p><p><b>MetaBCI:</b> <code>brainda.algorithms.decomposition.SKLDA</code></p>'),
        ('SVM', '支持向量机，小样本效果好',
         '<h3>SVM 分类器</h3><p>在CSP特征空间中找最优分类超平面。小训练集下比LDA更稳定。</p>'),
    ],
}

PARADIGM_COLORS = {'focus': '#4CAF50', 'ssvep': '#FF6F00', 'p300': '#E91E63', 'mi': '#29B6F6'}


# ============================================================
# 管线节点
# ============================================================

class PipeNode(QFrame):
    """固定信息节点 (数据输入/输出)"""
    def __init__(self, title: str, subtitle: str = ''):
        super().__init__()
        self.setObjectName('card')
        self.setStyleSheet('padding:10px 14px;')
        self.setMinimumSize(140, 90)
        layout = QVBoxLayout(self); layout.setContentsMargins(10, 10, 10, 10); layout.setSpacing(2)
        name = QLabel(title); name.setFont(QFont('sans-serif', 13, QFont.Weight.Bold))
        name.setStyleSheet(f'color:{TEXT};border:none;background:transparent;'); name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)
        if subtitle:
            sub = QLabel(subtitle); sub.setWordWrap(True); sub.setFont(QFont('sans-serif', 9))
            sub.setStyleSheet(f'color:{TEXT3};border:none;background:transparent;'); sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(sub)
        layout.addStretch()


class SlotNode(QFrame):
    """可点击槽位 (预处理/特征/分类)"""
    clicked = Signal()
    changed = Signal()

    def __init__(self, title: str, default_text: str = ''):
        super().__init__()
        self._title = title
        self.setObjectName('card'); self.setMinimumSize(150, 90)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet('padding:8px 12px;')
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._setup(default_text)

    def _setup(self, text: str):
        layout = QVBoxLayout(self); layout.setContentsMargins(10, 8, 10, 8); layout.setSpacing(1)
        title_lbl = QLabel(self._title); title_lbl.setFont(QFont('sans-serif', 10, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f'color:{TEXT2};border:none;background:transparent;')
        layout.addWidget(title_lbl)
        self._text_lbl = QLabel(text); self._text_lbl.setWordWrap(True)
        self._text_lbl.setFont(QFont('sans-serif', 12, QFont.Weight.Bold))
        self._text_lbl.setStyleSheet(f'color:{TEXT};border:none;background:transparent;')
        layout.addWidget(self._text_lbl, 1)
        hint = QLabel('点击更换 ▸'); hint.setStyleSheet(f'color:{ACCENT};font-size:9px;font-weight:600;border:none;background:transparent;')
        layout.addWidget(hint)

    def set_text(self, text: str):
        self._text_lbl.setText(text)
        self.changed.emit()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.clicked.emit()


def _arrow():
    a = QLabel('→'); a.setFont(QFont('sans-serif', 26, QFont.Weight.Bold))
    a.setStyleSheet(f'color:{TEXT3};border:none;background:transparent;')
    a.setAlignment(Qt.AlignmentFlag.AlignCenter); a.setFixedWidth(50)
    return a


# ============================================================
# Algo Lab Page
# ============================================================

class AlgoLabPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self._mw = main_window
        self._paradigm_id = 'focus'
        self._preproc_selected = {'带通滤波': True, '陷波滤波': True, '基线校正': False}
        self._feature_selected = {'focus': 'PSD频带能量', 'ssvep': 'CCA特征', 'p300': '时域分段', 'mi': 'CSP空间滤波'}
        self._classifier_selected = {'focus': 'β/(θ+α) 比值', 'ssvep': 'CCA分类', 'p300': 'LDA', 'mi': 'LDA'}
        self._setup()

    def _setup(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(20, 16, 20, 12); layout.setSpacing(10)

        # —— 标题 + 范式选择 ——
        header = QHBoxLayout()
        title = QLabel('算法工坊'); title.setObjectName('pageTitle'); header.addWidget(title)
        header.addStretch()

        self._para_btns = QButtonGroup(self)
        for para in PARADIGM_LIST:
            btn = QPushButton(para.name); btn.setCheckable(True)
            btn.setStyleSheet(f'padding:4px 12px;font-weight:bold;')
            btn.clicked.connect(lambda checked, p=para.paradigm_id: self._switch_paradigm(p))
            self._para_btns.addButton(btn)
            header.addWidget(btn)
        self._para_btns.buttons()[0].setChecked(True)

        reset_btn = QPushButton('恢复默认'); reset_btn.clicked.connect(self._reset)
        apply_btn = QPushButton('应用配置')
        apply_btn.clicked.connect(self._apply_config)
        apply_btn.setStyleSheet(f'background:{ACCENT};color:#fff;font-weight:bold;padding:6px 14px;border-radius:4px;border:none;')
        for b in [reset_btn, apply_btn]: header.addWidget(b)
        layout.addLayout(header)

        sub = QLabel('预处理可多选（勾选启用），特征提取和分类器按范式选择')
        sub.setStyleSheet(f'color:{TEXT2};font-size:12px;'); layout.addWidget(sub)

        # —— 管线可视化 ——
        pipe = QFrame(); pipe.setObjectName('card')
        pl = QVBoxLayout(pipe); pl.setContentsMargins(20, 16, 20, 16); pl.setSpacing(8)
        pipe_title = QLabel('信号处理管线'); pipe_title.setFont(QFont('sans-serif', 12, QFont.Weight.Bold))
        pipe_title.setStyleSheet(f'color:{TEXT};border:none;background:transparent;'); pl.addWidget(pipe_title)

        pipe_row = QHBoxLayout(); pipe_row.setSpacing(6); pipe_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pipe_row.addWidget(PipeNode('原始数据', '脑电信号'))
        pipe_row.addWidget(_arrow())

        # 预处理 (多选)
        self._preproc_node = SlotNode('预处理', '带通滤波')
        self._preproc_node.clicked.connect(self._toggle_preproc_options)
        pipe_row.addWidget(self._preproc_node)
        pipe_row.addWidget(_arrow())

        # 特征提取
        self._feature_node = SlotNode('特征提取', 'PSD频带能量')
        self._feature_node.clicked.connect(self._toggle_feature_options)
        pipe_row.addWidget(self._feature_node)
        pipe_row.addWidget(_arrow())

        # 分类器
        self._class_node = SlotNode('分类器', 'β/(θ+α) 比值')
        self._class_node.clicked.connect(self._toggle_classifier_options)
        pipe_row.addWidget(self._class_node)
        pipe_row.addWidget(_arrow())

        pipe_row.addWidget(PipeNode('输出', '控制指令 / 百分制'))
        pipe_row.addStretch()
        pl.addLayout(pipe_row)
        layout.addWidget(pipe)

        # —— 预处理勾选栏 ——
        self._preproc_bar = QFrame(); self._preproc_bar.setObjectName('card'); self._preproc_bar.setVisible(False)
        pbl = QVBoxLayout(self._preproc_bar); pbl.setSpacing(6); pbl.setContentsMargins(16, 10, 16, 10)

        cb_row = QHBoxLayout(); cb_row.setSpacing(16)
        cb_row.addWidget(QLabel('预处理:'))
        self._preproc_cbs: dict[str, QCheckBox] = {}
        for name in PREPROC_OPTIONS:
            cb = QCheckBox(name)
            cb.setChecked(self._preproc_selected.get(name, False))
            cb.toggled.connect(lambda checked, n=name: self._on_preproc_toggle(n, checked))
            self._preproc_cbs[name] = cb
            cb_row.addWidget(cb)
        cb_row.addStretch()
        pbl.addLayout(cb_row)

        # 频率参数
        freq_row = QHBoxLayout(); freq_row.setSpacing(12)
        freq_row.addWidget(QLabel('带通:'))
        self._lowcut = QDoubleSpinBox(); self._lowcut.setRange(0.1, 5.0); self._lowcut.setValue(0.5); self._lowcut.setSingleStep(0.5); self._lowcut.setSuffix(' Hz')
        freq_row.addWidget(QLabel('低切'))
        freq_row.addWidget(self._lowcut)
        self._highcut = QDoubleSpinBox(); self._highcut.setRange(10.0, 100.0); self._highcut.setValue(45.0); self._highcut.setSingleStep(5.0); self._highcut.setSuffix(' Hz')
        freq_row.addWidget(QLabel('高切'))
        freq_row.addWidget(self._highcut)
        freq_row.addWidget(QLabel('  陷波:'))
        self._notch = QDoubleSpinBox(); self._notch.setRange(45.0, 60.0); self._notch.setValue(50.0); self._notch.setSingleStep(1.0); self._notch.setSuffix(' Hz')
        freq_row.addWidget(self._notch)
        freq_row.addStretch()
        pbl.addLayout(freq_row)

        layout.addWidget(self._preproc_bar)

        # —— 特征提取/分类器选项栏 ——
        self._opt_bar = QFrame(); self._opt_bar.setObjectName('card'); self._opt_bar.setVisible(False)
        self._opt_layout = QHBoxLayout(self._opt_bar); self._opt_layout.setSpacing(8); self._opt_layout.setContentsMargins(16, 10, 16, 10)
        layout.addWidget(self._opt_bar)

        # —— 详情 ——
        detail = QFrame(); detail.setObjectName('card')
        dl = QVBoxLayout(detail); dl.setContentsMargins(14, 10, 14, 10)
        self._detail = QTextBrowser()
        self._detail.setStyleSheet(f'background:transparent;border:none;font-size:12px;'); self._detail.setMinimumHeight(140)
        dl.addWidget(self._detail)
        layout.addWidget(detail)

        self._update_all()

    def _switch_paradigm(self, pid: str):
        self._paradigm_id = pid
        self._update_all()

    def _update_all(self):
        pid = self._paradigm_id
        active_preproc = [k for k, v in self._preproc_selected.items() if v]
        self._preproc_node.set_text(', '.join(active_preproc) if active_preproc else '无')
        feat = self._feature_selected.get(pid, '')
        self._feature_node.set_text(feat)
        clf = self._classifier_selected.get(pid, '')
        self._class_node.set_text(clf)
        # 图文解释
        parts = [STUDENT_GUIDE]
        for n in active_preproc:
            short = PREPROC_OPTIONS.get(n, {}).get('short', '')
            if short: parts.append(f'<p>✅ <b>{n}</b>：{short}</p>')
        feat_guide = FEATURE_GUIDE.get(feat, '')
        if feat_guide: parts.append(feat_guide)
        clf_guide = CLASSIFIER_GUIDE.get(clf, '')
        if clf_guide: parts.append(clf_guide)
        self._detail.setHtml(''.join(parts))

    def _on_preproc_toggle(self, name: str, checked: bool):
        self._preproc_selected[name] = checked
        self._update_all()

    def _toggle_preproc_options(self):
        self._preproc_bar.setVisible(not self._preproc_bar.isVisible())
        self._opt_bar.setVisible(False)

    def _show_options(self, title: str, options: list, current: str, callback):
        # 彻底清空布局
        while self._opt_layout.count():
            item = self._opt_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # 递归清理子布局
                sub = item.layout()
                while sub.count():
                    si = sub.takeAt(0)
                    if si.widget(): si.widget().deleteLater()
        self._opt_layout.addWidget(QLabel(f'{title}:'))
        group = QButtonGroup(self)
        for name, desc, _ in options:
            btn = QPushButton(f'{name}\n{desc}'); btn.setCheckable(True)
            btn.setMinimumSize(130, 60); btn.setStyleSheet('text-align:center;padding:6px;font-size:10px;')
            btn.setChecked(name == current)
            btn.clicked.connect(lambda checked, n=name: (callback(n), self._opt_bar.setVisible(False)))
            group.addButton(btn); self._opt_layout.addWidget(btn)
        self._opt_layout.addStretch()
        self._preproc_bar.setVisible(False)
        self._opt_bar.setVisible(True)

    def _toggle_feature_options(self):
        pid = self._paradigm_id
        opts = FEATURE_OPTIONS.get(pid, [])
        if not opts: return
        self._show_options('特征提取', opts, self._feature_selected.get(pid, ''),
                          lambda n: self._set_feature(pid, n))

    def _toggle_classifier_options(self):
        pid = self._paradigm_id
        opts = CLASSIFIER_OPTIONS.get(pid, [])
        if not opts: return
        self._show_options('分类器', opts, self._classifier_selected.get(pid, ''),
                          lambda n: self._set_classifier(pid, n))

    def _set_feature(self, pid: str, name: str):
        self._feature_selected[pid] = name; self._update_all()
        # 显示详情
        for n, d, detail in FEATURE_OPTIONS.get(pid, []):
            if n == name: self._detail.setHtml(detail)

    def _set_classifier(self, pid: str, name: str):
        self._classifier_selected[pid] = name; self._update_all()
        for n, d, detail in CLASSIFIER_OPTIONS.get(pid, []):
            if n == name: self._detail.setHtml(detail)

    def _apply_config(self):
        """把配置推送到在线实验室的 worker"""
        from PySide6.QtWidgets import QMessageBox
        live_lab = self._mw._page_cache.get('live_lab')
        config = {
            'filters': dict(self._preproc_selected),
            'params': {'lowcut': self._lowcut.value(), 'highcut': self._highcut.value(), 'notch': self._notch.value()},
        }
        if live_lab:
            live_lab._saved_preproc_config = config
            if hasattr(live_lab, '_worker') and live_lab._worker:
                live_lab._worker.set_preproc(config)
            QMessageBox.information(self, '应用成功', '配置已保存，断开重连后也不会丢失')
        else:
            QMessageBox.warning(self, '提示', '请先在在线实验室连接设备')

    def _reset(self):
        self._preproc_selected = {'带通滤波': True, '陷波滤波': True, '基线校正': False}
        self._feature_selected = {'focus': 'PSD频带能量', 'ssvep': 'CCA特征', 'p300': '时域分段', 'mi': 'CSP空间滤波'}
        self._classifier_selected = {'focus': 'β/(θ+α) 比值', 'ssvep': 'CCA分类', 'p300': 'LDA', 'mi': 'LDA'}
        for name, cb in self._preproc_cbs.items():
            cb.setChecked(self._preproc_selected.get(name, False))
        self._update_all()
