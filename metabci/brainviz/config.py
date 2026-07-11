# -*- coding: utf-8 -*-
"""
brainviz — 全局配置 (Material Design 暗色主题)
"""

WINDOW_TITLE = "MetaBCI 全流程可视化科普平台"
WINDOW_WIDTH = 1500
WINDOW_HEIGHT = 950

# ============================================================
# Material Design 配色
# ============================================================

COLORS = {
    # 核心色
    "primary":        "#1976D2",
    "primary_light":  "#63A4FF",
    "primary_dark":   "#004BA0",
    "secondary":      "#00897B",
    "secondary_light":"#4DB6AC",
    # 背景
    "bg":             "#121212",
    "surface":        "#1E1E1E",
    "surface_light":  "#2C2C2C",
    # 文字
    "on_bg":          "#E0E0E0",
    "on_surface":     "#FFFFFF",
    "text_secondary": "#9E9E9E",
    # 功能色
    "accent":         "#FF6F00",
    "success":        "#4CAF50",
    "warning":        "#FFC107",
    "error":          "#CF6679",
    "info":           "#29B6F6",
    # 网格
    "grid":           "#333333",
    "divider":        "#424242",
}

# ============================================================
# 频带
# ============================================================

BANDS = {
    "δ delta":   (0.5, 4),
    "θ theta":   (4, 8),
    "α alpha":   (8, 13),
    "β beta":    (13, 30),
    "γ gamma":   (30, 45),
}

BAND_COLORS = {
    "δ delta":   "#9E9E9E",
    "θ theta":   "#63A4FF",
    "α alpha":   "#4CAF50",
    "β beta":    "#FFC107",
    "γ gamma":   "#CF6679",
}

# ============================================================
# 参数
# ============================================================

PLOT_REFRESH_MS = 50
WAVEFORM_SECONDS = 5.0
SPECTRUM_SECONDS = 3.0
LSL_TIMEOUT = 5.0
LSL_BUFFER_SECONDS = 10.0
