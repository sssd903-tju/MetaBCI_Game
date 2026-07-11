# -*- coding: utf-8 -*-
"""
训练中心 — 基于 MetaBCI brainstim 的范式训练与基线校准 [MetaBCI]

为比赛加分项：使用 brainstim 标准范式进行游戏前的训练和基线采集。
PsychoPy 全屏呈现刺激，训练数据用于优化在线解码。

流程:
  选择范式 → 配置参数 → 开始训练 (PsychoPy 窗口) → 完成 → 启动游戏
"""

import os
import sys
import json
import subprocess
import threading

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QPushButton, QSpinBox, QDoubleSpinBox, QProgressBar, QTextEdit,
    QMessageBox, QGroupBox, QFormLayout,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont

from metabci.brainviz.theme import TEXT, TEXT2, TEXT3, ACCENT, SURFACE, BORDER, BG, GREEN, RED


# ── 训练模式定义 ──

TRAINING_MODES = [
    {
        'id': 'focus_baseline',
        'icon': '🧘',
        'name': '专注度基线',
        'paradigm': '专注度检测',
        'desc': '闭眼放松 → 睁眼专注 → 自由状态\n采集个人专注度基线，优化游戏中的专注度计算',
        'color': '#4CAF50',
        'duration': 30,
        'has_trials': False,
        'has_freqs': False,
    },
    {
        'id': 'ssvep',
        'icon': '👁',
        'name': 'SSVEP 校准',
        'paradigm': 'SSVEP 稳态视觉诱发电位',
        'desc': '注视闪烁目标训练 SSVEP 响应\n贪吃蛇: ↑8Hz →10Hz ↓12Hz ←15Hz\n打地鼠: 8~15.6Hz 七频池',
        'color': '#FF6F00',
        'trials': 20,
        'freqs': [8.0, 15.0],
        'layout': 'snake',
        'has_trials': True,
        'has_freqs': True,
        'has_layout': True,
        'layouts': [
            ('snake', '思维贪吃蛇 (↑8Hz ←15Hz)'),
            ('mole', '打地鼠 (8Hz / 15Hz)'),
        ],
    },
    {
        'id': 'p300',
        'icon': '🃏',
        'name': 'P300 校准',
        'paradigm': 'P300 事件相关电位',
        'desc': '标准行列闪烁 oddball 范式\n采集目标/非目标 P300 响应，校准分类器',
        'color': '#E91E63',
        'trials': 12,
        'has_trials': True,
        'has_freqs': False,
    },
    {
        'id': 'mi',
        'icon': '💪',
        'name': 'MI 校准',
        'paradigm': 'MI 运动想象',
        'desc': '左右手运动想象提示训练\n采集想象期间的脑电特征，训练 CSP 分类器',
        'color': '#29B6F6',
        'trials': 20,
        'has_trials': True,
        'has_freqs': False,
    },
]


def _trainer_path() -> str:
    """获取 trainer.py 的绝对路径"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "training", "trainer.py")


def _find_trainer_python() -> str:
    """查找包含 PsychoPy 的 Python 解释器路径

    优先级:
      1. conda 环境 metabci-brainstim (Python 3.10 + PsychoPy)
      2. 系统全局 conda 环境
      3. 当前 Python (如果直接安装了 PsychoPy)
    """
    # 搜索可能的 conda 路径
    conda_roots = [
        os.path.expanduser("~/anaconda3"),
        os.path.expanduser("~/miniconda3"),
        "/opt/anaconda3",
        "/opt/miniconda3",
        "/usr/local/anaconda3",
    ]
    for root in conda_roots:
        env_python = os.path.join(root, "envs", "metabci-brainstim", "bin", "python")
        if os.path.exists(env_python):
            try:
                r = subprocess.run(
                    [env_python, "-c", "import psychopy"],
                    capture_output=True, timeout=5,
                )
                if r.returncode == 0:
                    return env_python
            except Exception:
                pass

    # 回退到当前 Python
    return sys.executable


def _check_psychopy() -> bool:
    """检查 PsychoPy 是否可用（在当前解释器或 conda 环境中）"""
    try:
        import psychopy  # noqa: F401
        return True
    except ImportError:
        pass
    # 检查 conda 环境
    python = _find_trainer_python()
    if python != sys.executable:
        return True
    return False


# ═══════════════════════════════════════════════════════════
# 训练中心页面
# ═══════════════════════════════════════════════════════════

class TrainingCenterPage(QWidget):
    """[MetaBCI] 训练中心 — 基于 brainstim 的范式训练

    功能:
      - 4 种范式训练卡片 (专注/SSVEP/P300/MI)
      - 可配置训练参数 (试次/时长/频率)
      - 一键启动 PsychoPy 全屏训练
      - 实时训练进度与结果展示
    """

    training_started = Signal(str)    # mode_id
    training_progress = Signal(str, int, int)  # phase, current, total
    training_done = Signal(str, object)  # mode_id, results
    training_error = Signal(str)     # error message

    def __init__(self, main_window):
        super().__init__()
        self._mw = main_window
        self._process: subprocess.Popen | None = None
        self._current_mode: str | None = None
        self._params: dict = {}
        self._setup()

        # 检查依赖
        if not _check_psychopy():
            self._status_text.setText(
                "⚠ PsychoPy 未安装。请运行: pip install psychopy\n"
                "PsychoPy 是 MetaBCI brainstim 的依赖，用于呈现标准范式刺激。"
            )
            self._status_text.setStyleSheet(
                f'color:#e6a817;font-size:12px;padding:8px;'
                f'background:{SURFACE};border-radius:6px;'
            )

    def _setup(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 16)
        layout.setSpacing(16)

        # ── 标题行 ──
        header = QHBoxLayout()
        title = QLabel('训练中心')
        title.setObjectName('pageTitle')
        header.addWidget(title)
        header.addStretch()

        # 依赖状态
        deps_ok = _check_psychopy()
        dep_label = QLabel('● brainstim 就绪' if deps_ok else '○ PsychoPy 未安装')
        dep_label.setStyleSheet(
            f'font-size:12px;color:{"#22c55e" if deps_ok else "#e6a817"};'
            f'padding:6px 14px;background:{SURFACE};border-radius:12px;'
        )
        header.addWidget(dep_label)
        layout.addLayout(header)

        sub = QLabel('在进行 BCI 游戏之前，使用 MetaBCI brainstim 标准范式进行训练和基线校准，提升解码效果。')
        sub.setStyleSheet(f'color:{TEXT2};font-size:13px;')
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # ── 训练卡片 (2×2) ──
        grid = QGridLayout()
        grid.setSpacing(14)
        for i, mode in enumerate(TRAINING_MODES):
            card = self._training_card(i, mode)
            row, col = divmod(i, 2)
            grid.addWidget(card, row, col)
        layout.addLayout(grid, 1)

        # ── 底部状态 ──
        self._status_text = QLabel('💡 选择上方训练模式，配置参数后点击"开始训练"')
        self._status_text.setStyleSheet(
            f'color:{TEXT3};font-size:12px;padding:8px;'
            f'background:{SURFACE};border-radius:6px;'
        )
        self._status_text.setWordWrap(True)
        layout.addWidget(self._status_text)

        # 进度条
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFixedHeight(16)
        self._progress.setVisible(False)
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                background: {SURFACE}; border: 1px solid {BORDER};
                border-radius: 8px; text-align: center; color: {TEXT};
                font-size: 11px;
            }}
            QProgressBar::chunk {{
                background: {ACCENT}; border-radius: 7px;
            }}
        """)
        layout.addWidget(self._progress)

    # ── 训练卡片 ──

    def _training_card(self, index: int, mode: dict) -> QFrame:
        """构建训练模式卡片"""
        f = QFrame()
        f.setObjectName('card')
        f.setStyleSheet(f"""
            QFrame#card {{
                background: {SURFACE}; border: 1px solid {BORDER};
                border-radius: 10px;
            }}
        """)

        card_layout = QVBoxLayout(f)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(8)

        # 图标 + 名称
        hdr = QHBoxLayout()
        ic = QLabel(mode['icon'])
        ic.setStyleSheet('font-size:32px;border:none;background:transparent;')
        hdr.addWidget(ic)

        name_lbl = QLabel(mode['name'])
        name_lbl.setFont(QFont('sans-serif', 16, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f'color:{TEXT};border:none;background:transparent;')
        hdr.addWidget(name_lbl)
        hdr.addStretch()

        # 范式标签
        tag = QLabel(mode['paradigm'])
        tag.setStyleSheet(
            f'color:{mode["color"]};font-size:11px;font-weight:600;'
            'border:none;background:transparent;'
        )
        hdr.addWidget(tag)
        card_layout.addLayout(hdr)

        # 描述
        desc = QLabel(mode['desc'])
        desc.setWordWrap(True)
        desc.setStyleSheet(f'color:{TEXT2};font-size:12px;border:none;background:transparent;')
        card_layout.addWidget(desc)

        card_layout.addStretch()

        # 参数配置行
        param_row = QHBoxLayout()

        if mode['has_trials']:
            param_row.addWidget(QLabel('试次:'))
            trials_spin = QSpinBox()
            trials_spin.setRange(4, 100)
            trials_spin.setValue(mode.get('trials', 20))
            trials_spin.setFixedWidth(60)
            trials_spin.setStyleSheet(f'background:{BG};color:{TEXT};border:1px solid {BORDER};border-radius:4px;padding:2px;')
            trials_spin.setObjectName(f'trials_{mode["id"]}')
            param_row.addWidget(trials_spin)
            param_row.addSpacing(12)

        if mode.get('has_layout'):
            from PySide6.QtWidgets import QComboBox
            param_row.addWidget(QLabel('游戏:'))
            layout_combo = QComboBox()
            layout_combo.setObjectName(f'layout_{mode["id"]}')
            for lv, ll in mode['layouts']:
                layout_combo.addItem(ll, lv)
            layout_combo.setStyleSheet(f'background:{BG};color:{TEXT};border:1px solid {BORDER};border-radius:4px;padding:2px;font-size:12px;')
            layout_combo.currentIndexChanged.connect(
                lambda idx, m=mode: self._on_layout_changed(m, idx)
            )
            param_row.addWidget(layout_combo)
            param_row.addSpacing(12)

        if mode['has_freqs']:
            param_row.addWidget(QLabel('频率:'))
            freqs_edit = QLabel(', '.join(str(f) for f in mode.get('freqs', [])))
            freqs_edit.setStyleSheet(f'color:{TEXT2};font-size:12px;border:none;')
            freqs_edit.setObjectName(f'freqs_{mode["id"]}')
            param_row.addWidget(freqs_edit)

        if not mode['has_trials']:
            param_row.addWidget(QLabel('时长(秒):'))
            dur_spin = QSpinBox()
            dur_spin.setRange(10, 120)
            dur_spin.setValue(mode.get('duration', 30))
            dur_spin.setFixedWidth(60)
            dur_spin.setStyleSheet(f'background:{BG};color:{TEXT};border:1px solid {BORDER};border-radius:4px;padding:2px;')
            dur_spin.setObjectName(f'duration_{mode["id"]}')
            param_row.addWidget(dur_spin)

        param_row.addStretch()
        card_layout.addLayout(param_row)

        # 启动按钮
        btn = QPushButton('▶ 开始训练')
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: #ffffff; color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 6px; padding: 8px 0px;
                font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {SURFACE}; border-color: {mode['color']}; color: {mode['color']}; }}
        """)
        btn.clicked.connect(lambda checked, i=index: self._start_training(i))
        card_layout.addWidget(btn)

        return f

    # SSVEP 频率预设 (与 Godot 游戏对齐)
    _SSVEP_PRESETS = {
        'snake': [8.0, 15.0],
        'mole': [8.0, 15.0],
    }

    def _on_layout_changed(self, mode: dict, idx: int):
        """切换 SSVEP 游戏布局时更新频率显示"""
        layout_key = mode['layouts'][idx][0]
        freqs = self._SSVEP_PRESETS.get(layout_key, mode.get('freqs', []))
        freqs_widget = self.findChild(QLabel, f'freqs_{mode["id"]}')
        if freqs_widget:
            freqs_widget.setText(', '.join(str(f) for f in freqs))

    # ── 训练控制 ──

    def _start_training(self, index: int):
        """启动训练子进程"""
        mode = TRAINING_MODES[index]

        # 范式匹配检查
        current_para = self._mw.current_paradigm
        para_map = {
            'focus_baseline': 'focus', 'ssvep': 'ssvep', 'p300': 'p300', 'mi': 'mi',
        }
        expected_para = para_map.get(mode['id'], '')
        if current_para and current_para.paradigm_id != expected_para:
            para_names = {'focus': '专注度检测', 'ssvep': 'SSVEP', 'p300': 'P300', 'mi': '运动想象'}
            current_name = para_names.get(current_para.paradigm_id, current_para.name)
            expected_name = para_names.get(expected_para, mode['name'])
            reply = QMessageBox.warning(
                self, '范式不匹配',
                f'当前范式是「{current_name}」\n'
                f'但训练需要「{expected_name}」范式。\n\n'
                f'是否仍要继续训练？',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        if not _check_psychopy():
            QMessageBox.critical(self, '依赖缺失',
                                 'PsychoPy 未安装，无法启动训练。\n\n'
                                 '请运行: pip install psychopy')
            return

        # 收集参数
        self._current_mode = mode['id']
        self._params = {'mode': mode['id']}

        if mode['has_trials']:
            trials_widget = self.findChild(QSpinBox, f'trials_{mode["id"]}')
            self._params['trials'] = trials_widget.value() if trials_widget else 20
        else:
            dur_widget = self.findChild(QSpinBox, f'duration_{mode["id"]}')
            self._params['duration'] = dur_widget.value() if dur_widget else 30

        if mode['has_freqs']:
            freqs_widget = self.findChild(QLabel, f'freqs_{mode["id"]}')
            freqs_str = freqs_widget.text() if freqs_widget else '8,10,12,15'
            self._params['freqs'] = freqs_str

        if mode.get('has_layout'):
            from PySide6.QtWidgets import QComboBox
            layout_widget = self.findChild(QComboBox, f'layout_{mode["id"]}')
            self._params['layout'] = layout_widget.currentData() if layout_widget else 'snake'

        # 构建命令 — 使用包含 PsychoPy 的 Python 解释器
        trainer_python = _find_trainer_python()
        trainer_path = _trainer_path()
        cmd = [trainer_python, trainer_path, '--mode', mode['id']]
        if 'trials' in self._params:
            cmd.extend(['--trials', str(self._params['trials'])])
        if 'duration' in self._params:
            cmd.extend(['--duration', str(self._params['duration'])])
        if 'freqs' in self._params:
            cmd.extend(['--freqs', self._params['freqs']])
        if 'layout' in self._params:
            cmd.extend(['--layout', self._params['layout']])

        # 自动开始录制 EEG 数据
        rec_path = self._auto_start_recording()
        # 重置准确率统计 + 清理解码日志
        self._trial_targets = []
        self._trial_times = []
        import metabci.brainviz.pages.live_lab as _ll
        _ll._ssvep_decode_log.clear()
        # 根据布局切换 SSVEP 解码频率 + 强制临时范式
        if mode['id'] == 'ssvep':
            self._switch_ssvep_freqs()
            self._force_ssvep_paradigm()
        elif mode['id'] == 'focus_baseline':
            self._force_focus_paradigm()

        # 更新 UI
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._status_text.setText(f'🚀 正在启动 {mode["name"]} 训练... PsychoPy 窗口即将打开')
        self._status_text.setStyleSheet(
            f'color:{ACCENT};font-size:12px;padding:8px;'
            f'background:{SURFACE};border-radius:6px;'
        )

        # 启动子进程
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            # 待处理消息 (线程安全 — reader 线程写入, QTimer 主线程读取)
            self._pending_messages: list[dict] = []
            self._messages_lock = threading.Lock()
            self._trainer_finished = False  # 防止 _check_process 覆盖已完成/出错的状态

            # 后台线程读取 stdout
            self._reader_thread = threading.Thread(
                target=self._read_process, daemon=True
            )
            self._reader_thread.start()

            # 定时检查进程状态和待处理消息
            self._poll_timer = QTimer(self)
            self._poll_timer.timeout.connect(self._check_process)
            self._poll_timer.start(200)

            self.training_started.emit(mode['id'])

        except Exception as e:
            self._status_text.setText(f'❌ 启动失败: {e}')
            self._status_text.setStyleSheet(
                f'color:#e74c3c;font-size:12px;padding:8px;'
                f'background:{SURFACE};border-radius:6px;'
            )

    def _read_process(self):
        """后台线程 — 读取子进程 stdout JSON 行，存入线程安全队列"""
        if not self._process:
            return
        try:
            for line in self._process.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    with self._messages_lock:
                        self._pending_messages.append(data)
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass

    def _check_process(self):
        """主线程定时器 — 处理待处理消息 + 检查进程退出"""
        # 1. 处理线程安全队列中的消息 (在主线程中更新 UI)
        with self._messages_lock:
            msgs = self._pending_messages[:]
            self._pending_messages.clear()
        for data in msgs:
            self._apply_message(data)

        if not self._process:
            self._poll_timer.stop()
            return

        # 2. 检查进程是否退出
        ret = self._process.poll()
        if ret is not None:
            self._poll_timer.stop()
            # 只在没有收到过 complete/error/cancelled 消息时才报告异常退出
            if not self._trainer_finished:
                # 读取 stderr 获取错误详情
                try:
                    stderr_text = self._process.stderr.read()
                except Exception:
                    stderr_text = ""
                self._status_text.setText(
                    f'❌ 训练进程异常退出 (code={ret})\n{stderr_text[:300]}'
                )
                self._status_text.setStyleSheet(
                    f'color:#e74c3c;font-size:12px;padding:8px;'
                    f'background:{SURFACE};border-radius:6px;'
                )
            self._process = None

    def _apply_message(self, data: dict):
        """在主线程中应用 trainer 消息，安全更新 UI"""
        status = data.get("status", "")

        if status == "progress":
            phase = data.get("phase", "")
            if phase == "trial":
                trial = data.get("trial", 0)
                total = data.get("total", 1)
                pct = int(trial / total * 100)
                self._progress.setValue(pct)
                self._progress.setFormat(f'{phase}: {trial}/{total}')
                self.training_progress.emit(phase, trial, total)
                # 仅记录试次开始消息 (有 trial_time 字段)
                if "trial_time" in data:
                    if not hasattr(self, '_trial_targets'):
                        self._trial_targets = []
                        self._trial_times = []
                    self._trial_targets.append(data.get("target_freq", 0))
                    self._trial_times.append(data["trial_time"])
            else:
                msg = data.get("message", "")
                self._status_text.setText(f'⏳ {msg}')
                self.training_progress.emit(phase, 0, 0)

        elif status == "complete":
            results = data.get("results", {})
            self._trainer_finished = True
            self._progress.setValue(100)
            self._progress.setFormat('完成!')
            self._restore_paradigm()
            # 计算训练准确率
            accuracy_text = self._compute_accuracy(results)
            # 自动停止录制 + 一站式保存数据
            rec_path = self._auto_stop_recording()
            self._compute_and_apply_model(rec_path, results, accuracy_text)
            mode_name = next((m['name'] for m in TRAINING_MODES
                            if m['id'] == self._current_mode), '训练')
            msg = f'✅ {mode_name}完成！{accuracy_text}可以启动对应游戏了'
            self._status_text.setText(msg)
            self._status_text.setStyleSheet(
                f'color:#22c55e;font-size:12px;padding:8px;'
                f'background:{SURFACE};border-radius:6px;'
            )
            self.training_done.emit(self._current_mode, results)

        elif status == "error":
            msg = data.get("message", "未知错误")
            self._trainer_finished = True
            self._restore_paradigm()
            self._status_text.setText(f'❌ 训练出错: {msg}')
            self._status_text.setStyleSheet(
                f'color:#e74c3c;font-size:12px;padding:8px;'
                f'background:{SURFACE};border-radius:6px;'
            )
            self.training_error.emit(msg)

        elif status == "cancelled":
            self._trainer_finished = True
            self._status_text.setText('⏹ 训练已取消')
            self._status_text.setStyleSheet(
                f'color:{TEXT2};font-size:12px;padding:8px;'
                f'background:{SURFACE};border-radius:6px;'
            )
            self._progress.setVisible(False)

    def _get_live_lab(self):
        """获取 LiveLab 页面实例"""
        cache = getattr(self._mw, '_page_cache', {})
        return cache.get('live_lab')

    def _auto_start_recording(self):
        """自动开始录制 EEG 数据"""
        live = self._get_live_lab()
        if live and live._buffer is not None and live._buffer.sample_count > 0:
            if not live._recording:
                live._toggle_recording()
                print("[训练] 自动录制已启动")
                return True
        print("[训练] ⚠ 自动录制未启动 (无LiveLab或无EEG数据)")
        return False

    def _auto_stop_recording(self):
        """自动停止录制，返回保存路径"""
        live = self._get_live_lab()
        if live and getattr(live, '_recording', False):
            # 记录当前录制目录 — toggle 后 _recording 变 False
            live._toggle_recording()
            # 找最新的录制目录
            import os, glob
            rec_dir = os.path.expanduser('~/MetaBCI_Recordings')
            if os.path.isdir(rec_dir):
                dirs = sorted(glob.glob(os.path.join(rec_dir, '*/')), key=os.path.getmtime, reverse=True)
                if dirs:
                    return dirs[0]
        return None

    def _compute_and_apply_model(self, rec_path: str, results: dict, accuracy: str):
        """一站式: 从录制数据生成模板 + 复制试次标签 + 打包到统一目录"""
        import shutil, json as _json
        try:
            # 创建统一训练数据目录
            from datetime import datetime
            tstamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            mode_name = self._current_mode or 'training'
            data_dir = os.path.expanduser(
                f'~/MetaBCI_Training_Data/{mode_name}_{tstamp}')
            os.makedirs(data_dir, exist_ok=True)

            # 复制录制数据
            if rec_path and os.path.isdir(rec_path):
                for fname in ['raw.npy', 'preprocessed.npy', 'meta.json']:
                    src = os.path.join(rec_path, fname)
                    if os.path.exists(src):
                        shutil.copy2(src, os.path.join(data_dir, fname))

            # 保存试次标签
            trials = results.get('trials', [])
            trial_info = {
                'mode': self._current_mode,
                'layout': self._params.get('layout', 'snake'),
                'freqs': self._params.get('freqs', ''),
                'trials': trials,
                'total_trials': len(trials),
                'accuracy': accuracy.strip(),
            }
            with open(os.path.join(data_dir, 'trials.json'), 'w') as f:
                _json.dump(trial_info, f, ensure_ascii=False, indent=2)

            # 生成 SSVEP 模板
            if self._current_mode == 'ssvep':
                from metabci.brainviz.calibration import (
                    compute_templates_from_recording, reset_decoder)
                if rec_path and os.path.isdir(rec_path):
                    compute_templates_from_recording(rec_path)
                    # 复制模板到数据目录
                    tpl_src = os.path.expanduser(
                        '~/MetaBCI_Calibration/ssvep_templates.npz')
                    if os.path.exists(tpl_src):
                        shutil.copy2(tpl_src, os.path.join(data_dir, 'ssvep_templates.npz'))
                reset_decoder()

            self._last_training_dir = data_dir
            self._status_text.setText(
                self._status_text.text() +
                f'\n📁 数据已保存: {data_dir}'
            )
        except Exception as e:
            self._reload_decoder()
            print(f"[训练数据保存] 失败: {e}")

    def _force_ssvep_paradigm(self):
        """临时切换 Worker 到 SSVEP 解码（训练结束后恢复）"""
        live = self._get_live_lab()
        if live and live._worker:
            self._prev_paradigm = live._worker._paradigm
            live._worker.set_paradigm('ssvep')
            live._paradigm_id = 'ssvep'
            print(f"[训练] 强制切换范式: {self._prev_paradigm} → ssvep")
        else:
            print(f"[训练] ⚠ 无法切换范式: live={bool(live)}, worker={bool(live._worker) if live else False}")

    def _force_focus_paradigm(self):
        """临时切换 Worker 到 Focus 解码"""
        live = self._get_live_lab()
        if live and live._worker:
            self._prev_paradigm = live._worker._paradigm
            live._worker.set_paradigm('focus')
            live._paradigm_id = 'focus'

    def _restore_paradigm(self):
        """恢复训练前的范式"""
        live = self._get_live_lab()
        if live and live._worker and hasattr(self, '_prev_paradigm'):
            live._worker.set_paradigm(self._prev_paradigm)
            live._paradigm_id = self._prev_paradigm

    def _switch_ssvep_freqs(self):
        """根据训练布局切换 SSVEP 解码频率"""
        layout = self._params.get('layout', 'snake')
        try:
            from metabci.brainviz.calibration import reset_decoder, SSVEPDecoder
            from metabci.brainviz.live_worker import SSVEP_FREQS as worker_freqs
            from metabci.brainviz.game_bridge import SNAKE_FREQS, MOLE_FREQS
            # 更新 LiveWorker 的全局频率列表
            new_freqs = SNAKE_FREQS if layout == 'snake' else MOLE_FREQS
            import metabci.brainviz.live_worker as lw
            lw.SSVEP_FREQS[:] = new_freqs
            # 重置解码器使其重新创建
            reset_decoder()
        except Exception:
            pass

    def _compute_accuracy(self, results: dict) -> str:
        """计算 SSVEP 训练准确率 — 时间对齐"""
        if self._current_mode != 'ssvep':
            return ''
        trials = results.get('trials', [])
        if not trials:
            return ''
        import metabci.brainviz.pages.live_lab as _ll
        from collections import Counter
        decode_log = _ll._ssvep_decode_log
        if not decode_log:
            print(f"[训练准确率] 无解码数据 ({len(trials)}试次)")
            return f'(无解码数据) '
        trial_times = getattr(self, '_trial_times', [])
        trial_targets = getattr(self, '_trial_targets', [])
        print(f"[训练准确率] trials={len(trials)} trial_times={len(trial_times)} "
              f"trial_targets={len(trial_targets)} decode={len(decode_log)}")
        if not trial_times:
            # fallback: 均匀分布
            n = len(trials)
            step = max(1, len(decode_log) // n)
            correct = 0
            for i in range(n):
                idx = min(i * step, len(decode_log) - 1)
                df = decode_log[idx]['freq']
                tf = trials[i]['freq']
                if abs(df - tf) < 1.5:
                    correct += 1
            print(f"[训练准确率-fallback] {correct}/{n} = {correct/n*100:.0f}%")
        else:
            correct = 0
            for i in range(min(len(trials), len(trial_times))):
                t_start = trial_times[i]
                t_stim = t_start + 1.0
                t_end = t_start + 3.0
                tf = trial_targets[i]
                window_freqs = [d['freq'] for d in decode_log
                                if t_stim <= d['time'] <= t_end]
                if window_freqs:
                    mode_freq = Counter(window_freqs).most_common(1)[0][0]
                    hit = abs(mode_freq - tf) < 1.5
                    if hit: correct += 1
                    print(f"  试次{i+1}: 目标{tf}Hz 窗口{len(window_freqs)}次解码 "
                          f"众数{mode_freq}Hz {'✓' if hit else '✗'}")
                else:
                    # 放宽窗口到 [t_start, t_start+4s]
                    w2 = [d for d in decode_log
                          if t_start <= d['time'] <= t_start + 4.0]
                    print(f"  试次{i+1}: 目标{tf}Hz stim窗口无数据!"
                          f" 放宽窗口有{len(w2)}条")
            n = min(len(trials), len(trial_times))
        acc = correct / n * 100 if n > 0 else 0
        print(f"[训练准确率] {correct}/{n} = {acc:.0f}%")
        _ll._ssvep_decode_log.clear()
        self._trial_targets = []
        self._trial_times = []
        if n >= 3:
            return f'准确率 {acc:.0f}% ({correct}/{n}) | '
        return f'({len(decode_log)}次解码) | '

    def _reload_decoder(self):
        """训练完成后重载 SSVEP 解码器，使模板立即生效"""
        try:
            from metabci.brainviz.calibration import reset_decoder
            reset_decoder()
        except Exception:
            pass

    def closeEvent(self, event):
        """关闭页面时终止训练子进程"""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self._process.wait(timeout=3)
        super().closeEvent(event)
