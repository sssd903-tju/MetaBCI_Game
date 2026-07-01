extends Node
## GlobalConfig — 全局配色方案与常量定义
##
## 莫兰迪配色方案（Morandi Color Scheme）
## 所有颜色值均为 Godot Color (0.0 - 1.0)

# ============================================================
# 配色方案 — 莫兰迪色系
# ============================================================

# 背景色
const BG_WARM_CREAM := Color("EFE9D8")      # 暖米色背景
const BG_DARK := Color("3F4045")             # 深色背景 (备用)

# 平台颜色
const PLATFORM_NORMAL := Color("5A8A6A")     # 莫兰迪绿 — 正常平台
const PLATFORM_FRAGILE := Color("C4956A")    # 暖棕色 — 脆弱平台
const PLATFORM_MOVING := Color("6A8ABF")     # 灰蓝色 — 移动平台

# UI 颜色
const UI_TEXT_PRIMARY := Color("3F6850")     # 深绿 — 主文字
const UI_TEXT_SECONDARY := Color("8BA89A")   # 浅绿 — 次要文字
const UI_ACCENT := Color("B8936B")           # 暖棕 — 强调色
const UI_SUCCESS := Color("5A8A6A")          # 成功绿
const UI_WARNING := Color("D4A84B")          # 警告黄
const UI_DANGER := Color("C4665A")           # 危险红

# 玩家
const PLAYER_COLOR := Color("2C2C2C")         # 近黑色方块
const PLAYER_GLOW_HIGH := Color("5A8A6A")     # 高专注光晕
const PLAYER_GLOW_MEDIUM := Color("D4A84B")   # 中等专注光晕
const PLAYER_GLOW_LOW := Color("C4665A")      # 低专注光晕

# 面板/卡片
const PANEL_BG := Color("F5F1E6")             # 卡片背景
const PANEL_BORDER := Color("D5CFBF")          # 卡片边框

# ============================================================
# 专注度检测 — 阈值配置
# ============================================================

# 专注度百分制 (基线=50, 0-100)
# 高专注 > 基线, 低专注 < 基线
const FOCUS_HIGH_THRESHOLD := 65    # >= 此值: 高专注
const FOCUS_MEDIUM_THRESHOLD := 35  # >= 此值: 中等专注
# < FOCUS_MEDIUM_THRESHOLD: 低专注

# ============================================================
# 游戏参数
# ============================================================

const GAME_WIDTH := 1600
const GAME_HEIGHT := 900
const PLATFORM_WIDTH := 120
const PLATFORM_HEIGHT := 20
const PLAYER_SIZE := 32
const GRAVITY := 980.0
const BASE_JUMP_VELOCITY := -420.0
const FOCUS_JUMP_BONUS := -180.0   # 满专注额外跳跃速度
const MOVE_SPEED := 200.0           # 平台移动速度
const PLATFORM_SPAWN_INTERVAL := 2.0

# ============================================================
# 网络配置
# ============================================================

const BCI_WS_URL := "ws://127.0.0.1:8768"
const BCI_RECONNECT_INTERVAL := 1.0
const BCI_DATA_TIMEOUT := 2.0  # 数据超时秒数

# ============================================================
# 范式标识
# ============================================================

enum ParadigmType {
	FOCUS_DETECTION = 0,
	SSVEP = 1,
	P300 = 2,
	MI = 3,
}

const PARADIGM_NAMES := {
	ParadigmType.FOCUS_DETECTION: "专注度检测",
	ParadigmType.SSVEP: "SSVEP 稳态视觉诱发电位",
	ParadigmType.P300: "P300 事件相关电位",
	ParadigmType.MI: "MI 运动想象",
}

const PARADIGM_SCENES := {
	ParadigmType.FOCUS_DETECTION: "res://scenes/focus_detection/FocusHub.tscn",
	ParadigmType.SSVEP: "res://scenes/ssvep/SSVEPHub.tscn",
	ParadigmType.P300: "res://scenes/p300/P300Hub.tscn",
	ParadigmType.MI: "res://scenes/mi/MIGame.tscn",
}

# ============================================================
# 工具函数
# ============================================================

func hex_to_color(hex_string: String) -> Color:
	"""将 HEX 颜色字符串转为 Godot Color"""
	return Color(hex_string)


func lerp_color(a: Color, b: Color, t: float) -> Color:
	"""在两个颜色之间线性插值"""
	return a.lerp(b, clampf(t, 0.0, 1.0))


func focus_to_color(ratio: float) -> Color:
	"""将专注度比值映射到颜色（绿→黄→红）"""
	if ratio >= FOCUS_HIGH_THRESHOLD:
		return UI_SUCCESS
	elif ratio >= FOCUS_MEDIUM_THRESHOLD:
		return lerp_color(UI_WARNING, UI_SUCCESS,
			(ratio - FOCUS_MEDIUM_THRESHOLD) / (FOCUS_HIGH_THRESHOLD - FOCUS_MEDIUM_THRESHOLD))
	else:
		var t := clampf(ratio / FOCUS_MEDIUM_THRESHOLD, 0.0, 1.0)
		return lerp_color(UI_DANGER, UI_WARNING, t)
