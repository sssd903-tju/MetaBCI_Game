# -*- coding: utf-8 -*-
"""
BaseParadigm — 范式抽象基类
"""

from dataclasses import dataclass, field


@dataclass
class Electrode:
    """10-20 系统电极"""
    name: str           # "Fp1"
    x: float            # 头部坐标系 x (0-1)
    y: float            # 头部坐标系 y (0-1)
    region: str         # 脑区名称
    description: str    # 功能说明


@dataclass
class ParadigmTab:
    """范式 Tab 配置"""
    tab_id: str
    label: str
    icon: str


@dataclass
class BaseParadigm:
    """BCI 范式抽象基类"""

    paradigm_id: str = ""
    name: str = ""
    icon: str = ""
    description: str = ""
    color: str = "#1976D2"

    # 活动电极 (≤4)
    active_electrodes: list[Electrode] = field(default_factory=list)

    # 10-20 系统关键电极位置
    all_electrodes: list[Electrode] = field(default_factory=list)

    # 处理管线说明
    pipeline_steps: list[str] = field(default_factory=list)

    # WebSocket 端口
    ws_port: int = 8768

    # 在线实验室结果标签
    result_label: str = ""
    # 讲解摘要 (显示在右侧说明卡片)
    explain_summary: str = ""
    explain_principle: str = ""

    # 四个 Tab 的科普内容 (Markdown/HTML)
    science: dict[str, str] = field(default_factory=dict)


# ============================================================
# 10-20 系统电极位置 (头部俯视图坐标系, 归一化 0-1)
# ============================================================

def _make_10_20_electrodes() -> list[Electrode]:
    """生成国际 10-20 系统关键电极"""
    return [
        # 前额
        Electrode("Fp1", 0.30, 0.15, "左前额叶", "情绪、决策"),
        Electrode("Fp2", 0.70, 0.15, "右前额叶", "情绪、决策"),
        Electrode("Fpz", 0.50, 0.08, "额极中线", "执行功能"),
        # 额叶
        Electrode("F3",  0.28, 0.30, "左额叶", "运动规划"),
        Electrode("F4",  0.72, 0.30, "右额叶", "运动规划"),
        Electrode("Fz",  0.50, 0.25, "额叶中线", "注意力"),
        Electrode("F7",  0.15, 0.28, "左前颞", "语言"),
        Electrode("F8",  0.85, 0.28, "右前颞", "语言"),
        # 中央
        Electrode("C3",  0.22, 0.50, "左感觉运动", "右手/右脚运动想象"),
        Electrode("C4",  0.78, 0.50, "右感觉运动", "左手/左脚运动想象"),
        Electrode("Cz",  0.50, 0.45, "中央中线", "运动准备"),
        # 顶叶
        Electrode("P3",  0.30, 0.68, "左顶叶", "感觉整合"),
        Electrode("P4",  0.70, 0.68, "右顶叶", "感觉整合"),
        Electrode("Pz",  0.50, 0.62, "顶叶中线", "P300 主要来源"),
        # 颞叶
        Electrode("T3",  0.08, 0.45, "左颞叶", "听觉"),
        Electrode("T4",  0.92, 0.45, "右颞叶", "听觉"),
        Electrode("T5",  0.12, 0.70, "左后颞", "听觉/语言"),
        Electrode("T6",  0.88, 0.70, "右后颞", "听觉/语言"),
        # 枕叶
        Electrode("O1",  0.35, 0.88, "左枕叶", "视觉处理"),
        Electrode("O2",  0.65, 0.88, "右枕叶", "视觉处理"),
        Electrode("Oz",  0.50, 0.92, "枕叶中线", "视觉诱发电位"),
        Electrode("POz", 0.50, 0.78, "顶枕中线", "SSVEP 主要来源"),
    ]


TEN_TWENTY_ELECTRODES = _make_10_20_electrodes()
