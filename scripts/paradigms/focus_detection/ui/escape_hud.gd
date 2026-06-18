extends Control
class_name EscapeHUD

var state_label: Label
var digit_label: Label
var timer_label: Label
var focus_label: Label
var focus_bar: ColorRect
var focus_bg: ColorRect
var hint_label: Label


func _ready() -> void:
	state_label = _lbl("找到隐藏在房间里的 4 个数字!", 18, GlobalConfig.UI_TEXT_PRIMARY)
	state_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	state_label.position = Vector2(0, 20)
	state_label.size = Vector2(GlobalConfig.GAME_WIDTH, 30)
	add_child(state_label)

	digit_label = _lbl("已发现: 0 / 4", 16, GlobalConfig.UI_TEXT_SECONDARY)
	digit_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	digit_label.position = Vector2(0, 54)
	digit_label.size = Vector2(GlobalConfig.GAME_WIDTH, 24)
	add_child(digit_label)

	timer_label = _lbl("⏱ 0s", 14, GlobalConfig.UI_TEXT_SECONDARY)
	timer_label.position = Vector2(24, 54)
	timer_label.size = Vector2(150, 20)
	add_child(timer_label)

	# 专注度条 — 右上
	focus_label = _lbl("专注", 12, GlobalConfig.UI_TEXT_SECONDARY)
	focus_label.position = Vector2(GlobalConfig.GAME_WIDTH - 120, 24)
	focus_label.size = Vector2(100, 16)
	add_child(focus_label)

	focus_bg = ColorRect.new()
	focus_bg.color = GlobalConfig.PANEL_BORDER
	focus_bg.size = Vector2(100, 8)
	focus_bg.position = Vector2(GlobalConfig.GAME_WIDTH - 120, 42)
	add_child(focus_bg)

	focus_bar = ColorRect.new()
	focus_bar.color = GlobalConfig.UI_SUCCESS
	focus_bar.size = Vector2(50, 8)
	focus_bar.position = focus_bg.position
	add_child(focus_bar)

	hint_label = _lbl("WASD/方向键 移动光  |  ESC 返回", 12, GlobalConfig.UI_TEXT_SECONDARY)
	hint_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint_label.position = Vector2(0, GlobalConfig.GAME_HEIGHT - 30)
	hint_label.size = Vector2(GlobalConfig.GAME_WIDTH, 20)
	add_child(hint_label)


func _lbl(text: String, font_size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", font_size)
	l.add_theme_color_override("font_color", color)
	return l


func update_state(text: String) -> void:
	state_label.text = text


func update_digits(found: int, total: int) -> void:
	digit_label.text = "已发现: %d / %d" % [found, total]


func update_timer(t: float) -> void:
	timer_label.text = "⏱ %ds" % int(t)


func update_focus(ratio: float) -> void:
	var pct := clampf(ratio / 4.0, 0.0, 1.0)
	focus_bar.size.x = focus_bg.size.x * pct
	focus_bar.color = GlobalConfig.focus_to_color(ratio)


func show_escaped(score: int, rating: String) -> void:
	state_label.text = "逃脱成功! %s" % rating
	digit_label.text = "得分: %d  |  Enter 再来一局  |  ESC 返回" % score
