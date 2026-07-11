# -*- coding: utf-8 -*-
"""游戏平台 — Godot 游戏范式启动与管理 [MetaBCI]

通过 WebSocket 桥接 (GameBridge) 将 BCI 解码结果推送到 Godot 游戏引擎。
支持一键启动 Godot 游戏、连接状态实时显示、范式联动。
"""

import os
import json
import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QPushButton, QDialog, QLineEdit, QFormLayout, QDialogButtonBox,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont

from metabci.brainviz.theme import TEXT, TEXT2, TEXT3, ACCENT, SURFACE, BORDER, BG

# ── 游戏定义 ──

GAMES = [
    {
        'icon': '🧠', 'name': '凝神一矢', 'paradigm': '专注度检测 · 射箭',
        'desc': '控制专注度让准星命中靶心',
        'detail': '前额叶 Fp1/Fp2 采集专注度信号。专注度越高，准星越稳越准！',
        'color': '#4CAF50', 'paradigm_id': 'focus',
        'godot_scene': 'res://scenes/focus_detection/FocusHub.tscn',
        'mode': 'archery',
    },
    {
        'icon': '🌊', 'name': '深海下潜', 'paradigm': '专注度检测 · 探索',
        'desc': '保持专注照亮海底收集标本',
        'detail': '探照灯光圈随专注度变化，高专注时视野开阔、氧气消耗慢。',
        'color': '#4CAF50', 'paradigm_id': 'focus',
        'godot_scene': 'res://scenes/focus_detection/FocusHub.tscn',
        'mode': 'dive',
    },
    {
        'icon': '👁', 'name': '思维贪吃蛇', 'paradigm': 'SSVEP · 方向控制',
        'desc': '注视闪烁目标用脑电波控制方向',
        'detail': '四个方向以不同频率闪烁（8/10/12/15Hz），盯哪个方向蛇往哪走！',
        'color': '#FF6F00', 'paradigm_id': 'ssvep',
        'godot_scene': 'res://scenes/ssvep/SSVEPHub.tscn',
        'mode': 'snake',
    },
    {
        'icon': '🔨', 'name': '打地鼠', 'paradigm': 'SSVEP · 目标选择',
        'desc': '注视闪烁的洞口打中地鼠',
        'detail': '2×2 到 4×4 动态网格，每个洞以不同频率闪烁。看哪个洞锤子落在哪。',
        'color': '#FF6F00', 'paradigm_id': 'ssvep',
        'godot_scene': 'res://scenes/ssvep/SSVEPHub.tscn',
        'mode': 'whack',
    },
    {
        'icon': '🃏', 'name': '卡牌读心', 'paradigm': 'P300 · 目标检测',
        'desc': '心里默想一张牌，电脑能猜到',
        'detail': '6张卡牌随机闪烁，默想目标那张。大脑 P300 信号会暴露你的选择！',
        'color': '#E91E63', 'paradigm_id': 'p300',
        'godot_scene': 'res://scenes/p300/P300Hub.tscn',
        'mode': 'card',
    },
    {
        'icon': '💪', 'name': '运动想象', 'paradigm': 'MI · 方向控制',
        'desc': '想象左右手运动来控制方向',
        'detail': '不需要动手，光靠想象就能控制。想象左手→左跳，想象右手→右跳。',
        'color': '#29B6F6', 'paradigm_id': 'mi',
        'godot_scene': 'res://scenes/mi/MIGame.tscn',
        'mode': 'mi',
    },
]

CONFIG_PATH = os.path.expanduser("~/.metabci_game_config.json")


# ═══════════════════════════════════════════════════════════
# Godot 路径配置对话框
# ═══════════════════════════════════════════════════════════

class GodotConfigDialog(QDialog):
    """Godot 可执行文件路径和项目路径配置"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Godot 配置")
        self.resize(520, 180)
        self.setStyleSheet(f"""
            QDialog {{ background: {BG}; }}
            QLabel {{ color: {TEXT}; font-size: 13px; }}
            QLineEdit {{
                background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 4px; padding: 6px 10px; font-size: 13px;
            }}
        """)
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        cfg = _load_config()

        self._godot_path = QLineEdit()
        self._godot_path.setText(cfg.get("godot_path", _default_godot_path()))
        self._godot_path.setPlaceholderText("例如: /Applications/Godot.app/Contents/MacOS/Godot")
        layout.addRow("Godot 可执行文件:", self._godot_path)

        self._project_path = QLineEdit()
        self._project_path.setText(cfg.get("project_path", _default_project_path()))
        self._project_path.setPlaceholderText("Godot 项目目录 (包含 project.godot)")
        layout.addRow("Godot 项目目录:", self._project_path)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                    QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self._save_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addRow(btn_box)

    def _save_and_accept(self):
        _save_config({
            "godot_path": self._godot_path.text().strip(),
            "project_path": self._project_path.text().strip(),
        })
        self.accept()

    def get_config(self) -> dict:
        return {
            "godot_path": self._godot_path.text().strip(),
            "project_path": self._project_path.text().strip(),
        }


def _default_godot_path() -> str:
    """根据平台推断 Godot 可执行文件路径"""
    if sys.platform == "darwin":
        # macOS — 优先检查常见安装位置
        candidates = [
            "/Applications/Godot.app/Contents/MacOS/Godot",
            "/Applications/Godot_mono.app/Contents/MacOS/Godot",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return "godot"
    elif sys.platform == "win32":
        return "godot.exe"
    else:
        return "godot"


def _default_project_path() -> str:
    """推断 Godot 项目目录默认路径"""
    # brainviz 位于: .../MetaBCI脑机接口游戏范式平台/MetaBCI/metabci/brainviz/pages/
    # Godot 项目:  .../MetaBCI脑机接口游戏范式平台/基于meta-bci的脑机接口游戏平台/
    try:
        # 向上 5 层到达工作区根目录
        workspace = Path(__file__).resolve().parent.parent.parent.parent.parent
        godot_dir = workspace / "基于meta-bci的脑机接口游戏平台"
        if godot_dir.is_dir():
            return str(godot_dir)
    except Exception:
        pass
    return ""


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(cfg: dict):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════
# 游戏平台页面
# ═══════════════════════════════════════════════════════════

class GamePlatformPage(QWidget):
    """[MetaBCI] 游戏平台 — BCI 游戏启动中心

    功能:
      - 6 款 BCI 游戏卡片，点击启动对应 Godot 场景
      - WebSocket 连接状态实时显示
      - 一键启动 Godot（自动打开对应场景）
      - 范式联动高亮
    """

    def __init__(self, main_window):
        super().__init__()
        self._mw = main_window
        self._bridge = main_window.game_bridge
        self._active_game: int = -1  # 当前活跃的游戏索引
        self._card_frames: list[QFrame] = []
        self._status_label: QLabel = None
        self._client_label: QLabel = None
        self._setup()

        # 连接桥接状态信号
        self._bridge.client_connected.connect(self._on_client_connected)
        self._bridge.client_disconnected.connect(self._on_client_disconnected)
        self._bridge.server_started.connect(self._on_server_started)
        self._bridge.server_stopped.connect(self._on_server_stopped)

        # 定时刷新状态
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start(1000)

    def _setup(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 16)
        layout.setSpacing(16)

        # ── 标题行 + 连接状态 ──
        header_row = QHBoxLayout()
        title = QLabel('游戏平台')
        title.setObjectName('pageTitle')
        header_row.addWidget(title)
        header_row.addStretch()

        # WebSocket 状态指示灯
        self._status_label = QLabel('● 未启动')
        self._status_label.setStyleSheet(
            f'font-size:13px;color:{TEXT3};padding:6px 14px;'
            f'background:{SURFACE};border-radius:12px;'
        )
        header_row.addWidget(self._status_label)

        # 客户端计数
        self._client_label = QLabel('')
        self._client_label.setStyleSheet(
            f'font-size:12px;color:{TEXT2};padding:6px 14px;'
            f'background:{SURFACE};border-radius:12px;'
        )
        header_row.addWidget(self._client_label)

        # 配置按钮
        cfg_btn = QPushButton('⚙ 设置')
        cfg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cfg_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT2}; border: 1px solid {BORDER};
                border-radius: 6px; padding: 6px 14px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {SURFACE}; color: {TEXT}; }}
        """)
        cfg_btn.clicked.connect(self._show_config)
        header_row.addWidget(cfg_btn)

        layout.addLayout(header_row)

        sub = QLabel('选择 BCI 游戏范式，启动 Godot 游戏引擎进行脑机互动体验')
        sub.setStyleSheet(f'color:{TEXT2};font-size:13px;')
        layout.addWidget(sub)

        # ── 游戏卡片网格 (3×2) ──
        grid = QGridLayout()
        grid.setSpacing(14)
        for i, game in enumerate(GAMES):
            card = self._game_card(i, game)
            row, col = divmod(i, 3)
            grid.addWidget(card, row, col)
        layout.addLayout(grid, 1)

        # ── 底部操作栏 ──
        bottom = QHBoxLayout()

        # 范式提示
        self._paradigm_hint = QLabel('💡 请先在科普广场或在线实验室中确认当前范式')
        self._paradigm_hint.setStyleSheet(f'color:{TEXT3};font-size:12px;')
        bottom.addWidget(self._paradigm_hint)
        bottom.addStretch()

        # 启动/停止全部
        self._toggle_btn = QPushButton('🚀 启动桥接服务器')
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: #ffffff; border: none;
                border-radius: 8px; padding: 10px 22px;
                font-size: 14px; font-weight: 600;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
        """)
        self._toggle_btn.clicked.connect(self._toggle_bridge)
        bottom.addWidget(self._toggle_btn)

        layout.addLayout(bottom)

    # ── 游戏卡片 ──

    def _game_card(self, index: int, game: dict) -> QFrame:
        """构建单个游戏卡片"""
        f = QFrame()
        f.setObjectName('card')
        f.setCursor(Qt.CursorShape.PointingHandCursor)
        self._card_frames.append(f)

        card_layout = QVBoxLayout(f)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(8)

        # 图标 + 名称
        header = QHBoxLayout()
        ic = QLabel(game['icon'])
        ic.setStyleSheet('font-size:36px;border:none;background:transparent;')
        header.addWidget(ic)

        title_lbl = QLabel(game['name'])
        title_lbl.setFont(QFont('sans-serif', 18, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f'color:{TEXT};border:none;background:transparent;')
        header.addWidget(title_lbl)
        header.addStretch()
        card_layout.addLayout(header)

        # 范式标签
        tag = QLabel(game['paradigm'])
        tag.setStyleSheet(
            f'color:{game["color"]};font-size:11px;font-weight:600;'
            'border:none;background:transparent;'
        )
        card_layout.addWidget(tag)

        # 简短描述
        desc = QLabel(game['desc'])
        desc.setWordWrap(True)
        desc.setStyleSheet(f'color:{TEXT2};font-size:13px;border:none;background:transparent;')
        card_layout.addWidget(desc)

        # 详细说明
        detail = QLabel(game['detail'])
        detail.setWordWrap(True)
        detail.setStyleSheet(
            f'color:{TEXT3};font-size:11px;line-height:1.5;border:none;background:transparent;'
        )
        card_layout.addWidget(detail)

        card_layout.addStretch()

        # 启动按钮 — 统一白色
        btn = QPushButton('▶ 启动游戏')
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: #ffffff; color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 6px; padding: 8px 0px;
                font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {SURFACE}; border-color: {ACCENT}; color: {ACCENT}; }}
        """)
        btn.clicked.connect(lambda checked, i=index: self._launch_game(i))
        card_layout.addWidget(btn)

        return f

    # ── 游戏启动 ──

    def _launch_game(self, index: int):
        """启动指定游戏"""
        game = GAMES[index]

        # 1. 范式匹配检查 — 不匹配时弹框警告
        current_para = self._mw.current_paradigm
        if current_para and current_para.paradigm_id != game['paradigm_id']:
            para_name_map = {
                'focus': '专注度检测', 'ssvep': 'SSVEP', 'p300': 'P300', 'mi': '运动想象',
            }
            current_name = para_name_map.get(current_para.paradigm_id, current_para.name)
            game_name = para_name_map.get(game['paradigm_id'], game['paradigm'])

            reply = QMessageBox.warning(
                self,
                '范式不匹配',
                f'当前选择的范式是「{current_name}」\n'
                f'但「{game["name"]}」需要的是「{game_name}」范式。\n\n'
                f'脑电解码将与游戏不匹配，游戏可能无法正常响应。\n\n'
                f'是否仍要继续启动？',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._active_game = index

        # 2. 切换 SSVEP 频率组 (贪吃蛇=4频 / 打地鼠=7频)
        if game['paradigm_id'] == 'ssvep':
            self._switch_ssvep_freqs(game.get('mode', 'snake'))

        # 3. 确保桥接服务器运行 (阻塞等待就绪)
        if not self._bridge.is_running:
            self._bridge.start()  # 内部等待服务器监听就绪

        # 4. 范式匹配提示
        if current_para and current_para.paradigm_id == game['paradigm_id']:
            self._paradigm_hint.setText('✅ 范式匹配，脑电解码将实时控制游戏')
            self._paradigm_hint.setStyleSheet(f'color:#22c55e;font-size:12px;')
        else:
            self._paradigm_hint.setText(
                f'⚠ 范式不匹配，请在科普广场切换到 {game["name"]} 对应范式'
            )
            self._paradigm_hint.setStyleSheet(f'color:#e6a817;font-size:12px;')

        # 5. 尝试启动 Godot
        self._try_launch_godot(game)

        # 6. 高亮当前卡片
        self._highlight_card(index)

    def _try_launch_godot(self, game: dict):
        """自动启动 Godot 游戏 — 优先直接打开，失败时才提示"""
        cfg = _load_config()
        godot_path = cfg.get("godot_path", _default_godot_path())
        project_path = cfg.get("project_path", _default_project_path())

        # 1. 校验项目路径
        if not project_path or not os.path.isdir(project_path):
            self._show_config_needed('未找到 Godot 项目目录，请在设置中配置')
            return

        if not os.path.exists(os.path.join(project_path, "project.godot")):
            self._show_config_needed('项目目录中未找到 project.godot，请检查路径')
            return

        # 2. 查找 Godot 可执行文件
        godot_exe = self._find_godot(godot_path)

        # 3. 启动
        scene = game['godot_scene']
        try:
            cmd = [godot_exe, '--path', project_path]
            if scene:
                cmd.extend(['--scene', scene])

            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)

            self._paradigm_hint.setText(f'🚀 {game["name"]} 正在启动...')
            self._paradigm_hint.setStyleSheet(f'color:{ACCENT};font-size:12px;')

        except FileNotFoundError:
            self._show_config_needed(
                f'未找到 Godot 可执行文件\n\n'
                f'尝试过: {godot_exe}\n\n'
                f'请在 ⚙ 设置 中配置 Godot 路径'
            )
        except Exception as e:
            self._paradigm_hint.setText(f'❌ 启动失败: {e}')
            self._paradigm_hint.setStyleSheet(f'color:#e74c3c;font-size:12px;')

    def _find_godot(self, configured_path: str) -> str:
        """查找 Godot 可执行文件，找不到则返回原值（让 subprocess 报 FileNotFoundError）"""
        # 如果配置的路径存在，直接用
        if os.path.isfile(configured_path) and os.access(configured_path, os.X_OK):
            return configured_path

        # macOS: 搜索常见 .app 路径
        if sys.platform == "darwin":
            candidates = [
                "/Applications/Godot.app/Contents/MacOS/Godot",
                "/Applications/Godot_mono.app/Contents/MacOS/Godot",
                os.path.expanduser("~/Applications/Godot.app/Contents/MacOS/Godot"),
            ]
            for c in candidates:
                if os.path.isfile(c) and os.access(c, os.X_OK):
                    return c

        # 尝试 PATH 中的 godot
        import shutil
        path_godot = shutil.which("godot") or shutil.which("godot.exe")
        if path_godot:
            return path_godot

        # 都没找到，返回用户配置的路径（让 subprocess 报错）
        return configured_path

    def _show_config_needed(self, reason: str):
        """配置不完整提示 — 引导用户打开设置"""
        box = QMessageBox(self)
        box.setWindowTitle("需要配置")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(f"{reason}")
        box.setInformativeText("是否现在打开设置？")
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.Yes)
        box.setStyleSheet(f"""
            QMessageBox {{ background: {BG}; }}
            QLabel {{ color: {TEXT}; font-size: 13px; }}
        """)
        if box.exec() == QMessageBox.StandardButton.Yes:
            self._show_config()

    def _highlight_card(self, index: int):
        """高亮选中的游戏卡片"""
        for i, frame in enumerate(self._card_frames):
            if i == index:
                frame.setStyleSheet(f"""
                    QFrame#card {{
                        background: {SURFACE}; border: 2px solid {ACCENT};
                        border-radius: 10px;
                    }}
                """)
            else:
                frame.setStyleSheet(f"""
                    QFrame#card {{
                        background: {SURFACE}; border: 1px solid {BORDER};
                        border-radius: 10px;
                    }}
                """)

    # ── 桥接控制 ──

    def _toggle_bridge(self):
        """启动/停止 WebSocket 桥接服务器"""
        if self._bridge.is_running:
            self._bridge.stop()
        else:
            self._bridge.start()

    def _on_server_started(self, port: int):
        self._status_label.setText(f'● 运行中 :{port}')
        self._status_label.setStyleSheet(
            f'font-size:13px;color:#22c55e;padding:6px 14px;'
            f'background:{SURFACE};border-radius:12px;font-weight:600;'
        )
        self._toggle_btn.setText('⏹ 停止服务器')
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: #e74c3c; color: #ffffff; border: none;
                border-radius: 8px; padding: 10px 22px;
                font-size: 14px; font-weight: 600;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
        """)

    def _on_server_stopped(self):
        self._status_label.setText('● 未启动')
        self._status_label.setStyleSheet(
            f'font-size:13px;color:{TEXT3};padding:6px 14px;'
            f'background:{SURFACE};border-radius:12px;'
        )
        self._client_label.setText('')
        self._toggle_btn.setText('🚀 启动桥接服务器')
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: #ffffff; border: none;
                border-radius: 8px; padding: 10px 22px;
                font-size: 14px; font-weight: 600;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
        """)

    def _on_client_connected(self, addr: str):
        count = self._bridge.client_count
        self._client_label.setText(f'🎮 {count} 个游戏连接')
        self._client_label.setStyleSheet(
            f'font-size:12px;color:#22c55e;padding:6px 14px;'
            f'background:{SURFACE};border-radius:12px;'
        )

    def _on_client_disconnected(self, addr: str):
        count = self._bridge.client_count
        if count > 0:
            self._client_label.setText(f'🎮 {count} 个游戏连接')
        else:
            self._client_label.setText('')

    def _refresh_status(self):
        """定时刷新状态（处理外部启动/停止的情况）"""
        if self._bridge.is_running:
            count = self._bridge.client_count
            if count > 0 and not self._client_label.text():
                self._client_label.setText(f'🎮 {count} 个游戏连接')
                self._client_label.setStyleSheet(
                    f'font-size:12px;color:#22c55e;padding:6px 14px;'
                    f'background:{SURFACE};border-radius:12px;'
                )
        else:
            if self._status_label.text() != '● 未启动':
                pass  # 信号处理

    def _switch_ssvep_freqs(self, mode: str):
        """根据游戏类型切换 SSVEP 频率组"""
        try:
            from metabci.brainviz.calibration import reset_decoder
            import metabci.brainviz.live_worker as lw
            if mode == 'whack':  # 打地鼠 → 7频
                lw.SSVEP_FREQS[:] = lw.MOLE_FREQS
            else:               # 贪吃蛇 → 2频 (8/15Hz)
                lw.SSVEP_FREQS[:] = [8.0, 15.0]
            reset_decoder()
        except Exception:
            pass

    # ── 配置 ──

    def _show_config(self):
        """打开 Godot 路径配置对话框"""
        dlg = GodotConfigDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            cfg = dlg.get_config()
            self._paradigm_hint.setText(
                f'✅ 配置已保存 — Godot: {os.path.basename(cfg["godot_path"])}'
            )
            self._paradigm_hint.setStyleSheet(f'color:#22c55e;font-size:12px;')
