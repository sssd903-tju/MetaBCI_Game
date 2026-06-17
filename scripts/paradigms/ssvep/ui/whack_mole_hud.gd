extends Control
class_name WhackMoleHUD
## HUD — 打地鼠界面

var _state_label: Label
var _score_label: Label
var _combo_label: Label
var _timer_bar: ColorRect
var _timer_bg: ColorRect
var _result_label: Label
var _round_label: Label


func _ready() -> void:
	_setup()


func _setup() -> void:
	# 左上: 轮次 + 分数
	var info := VBoxContainer.new()
	info.position = Vector2(24, 24)
	info.add_theme_constant_override("separation", 4)
	add_child(info)

	_round_label = _lbl("第 1 / %d 轮" % WhackMoleMode.TOTAL_ROUNDS, 16, GlobalConfig.UI_TEXT_PRIMARY)
	info.add_child(_round_label)

	_score_label = _lbl("分数: 0", 14, GlobalConfig.UI_TEXT_SECONDARY)
	info.add_child(_score_label)

	# 右上: combo
	_combo_label = _lbl("", 18, GlobalConfig.UI_ACCENT)
	_combo_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_combo_label.position = Vector2(GlobalConfig.GAME_WIDTH - 200, 24)
	_combo_label.size = Vector2(180, 30)
	add_child(_combo_label)

	# 居中: 状态文字
	_state_label = _lbl("", 24, GlobalConfig.UI_TEXT_PRIMARY)
	_state_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_state_label.position = Vector2(0, 60)
	_state_label.size = Vector2(GlobalConfig.GAME_WIDTH, 36)
	add_child(_state_label)

	# 解码进度条
	_timer_bg = ColorRect.new()
	_timer_bg.color = GlobalConfig.PANEL_BORDER
	_timer_bg.size = Vector2(300, 6)
	_timer_bg.position = Vector2((GlobalConfig.GAME_WIDTH - 300) / 2.0, 100)
	add_child(_timer_bg)

	_timer_bar = ColorRect.new()
	_timer_bar.color = GlobalConfig.PLATFORM_NORMAL
	_timer_bar.size = Vector2(300, 6)
	_timer_bar.position = _timer_bg.position
	add_child(_timer_bar)

	# 结果弹窗
	_result_label = _lbl("", 22, GlobalConfig.UI_ACCENT)
	_result_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_result_label.position = Vector2(0, GlobalConfig.GAME_HEIGHT - 100)
	_result_label.size = Vector2(GlobalConfig.GAME_WIDTH, 30)
	add_child(_result_label)


func _lbl(text: String, font_size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", font_size)
	l.add_theme_color_override("font_color", color)
	return l


func update_state(text: String) -> void:
	_state_label.text = text


func update_round(round_num: int) -> void:
	_round_label.text = "第 %d / %d 轮" % [round_num, WhackMoleMode.TOTAL_ROUNDS]


func update_score(total: int) -> void:
	_score_label.text = "分数: %d" % total


func update_combo(combo: int) -> void:
	if combo >= 2:
		_combo_label.text = "🔥 ×%d 连击！" % combo
	else:
		_combo_label.text = ""


func update_timer(progress: float) -> void:
	_timer_bar.size.x = _timer_bg.size.x * clampf(progress, 0.0, 1.0)


func show_timer(v: bool) -> void:
	_timer_bg.visible = v
	_timer_bar.visible = v


func show_result(text: String, color: Color) -> void:
	_result_label.text = text
	_result_label.add_theme_color_override("font_color", color)


func hide_result() -> void:
	_result_label.text = ""


func show_final(total: int, hits: int, misses: int, best_combo: int, rating: String) -> void:
	_state_label.text = "游戏结束"
	_result_label.text = "%s\n得分:%d  命中:%d  脱靶:%d  最佳连击:×%d\n按 Enter 重新开始 | ESC 返回" % [rating, total, hits, misses, best_combo]
	_result_label.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_PRIMARY)
