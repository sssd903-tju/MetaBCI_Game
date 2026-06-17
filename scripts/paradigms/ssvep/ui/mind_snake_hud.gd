extends Control
class_name MindSnakeHUD
## HUD — 贪吃蛇界面

var _score_label: Label
var _state_label: Label
var _hint_label: Label


func _ready() -> void:
	_setup()


func _setup() -> void:
	_score_label = _lbl("分数: 0", 18, GlobalConfig.UI_TEXT_PRIMARY)
	_score_label.position = Vector2(24, 24)
	_score_label.size = Vector2(300, 30)
	add_child(_score_label)

	_state_label = _lbl("", 22, GlobalConfig.UI_TEXT_PRIMARY)
	_state_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_state_label.position = Vector2(0, 60)
	_state_label.size = Vector2(GlobalConfig.GAME_WIDTH, 36)
	add_child(_state_label)

	_hint_label = _lbl("方向键控制蛇 | ESC 返回", 13, GlobalConfig.UI_TEXT_SECONDARY)
	_hint_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hint_label.position = Vector2(0, GlobalConfig.GAME_HEIGHT - 40)
	_hint_label.size = Vector2(GlobalConfig.GAME_WIDTH, 24)
	add_child(_hint_label)


func _lbl(text: String, font_size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", font_size)
	l.add_theme_color_override("font_color", color)
	return l


func update_score(s: int) -> void:
	_score_label.text = "分数: %d  长度: %d" % [s, s / MindSnakeMode.FOOD_SCORE + 3]


func update_state(text: String) -> void:
	_state_label.text = text


func show_game_over(score: int, rating: String) -> void:
	_state_label.text = "游戏结束"
	var panel := Panel.new()
	panel.size = Vector2(400, 160)
	panel.position = Vector2((GlobalConfig.GAME_WIDTH - 400) / 2.0, (GlobalConfig.GAME_HEIGHT - 160) / 2.0)
	var s := StyleBoxFlat.new()
	s.bg_color = GlobalConfig.PANEL_BG
	s.border_color = GlobalConfig.UI_ACCENT
	s.border_width_left = s.border_width_right = s.border_width_top = s.border_width_bottom = 2
	s.corner_radius_top_left = s.corner_radius_top_right = s.corner_radius_bottom_left = s.corner_radius_bottom_right = 12
	panel.add_theme_stylebox_override("panel", s)
	add_child(panel)

	var info := _lbl("得分: %d — %s\n按 Enter 重新开始 | ESC 返回" % [score, rating], 18, GlobalConfig.UI_TEXT_PRIMARY)
	info.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	info.position = Vector2(0, 30)
	info.size = Vector2(400, 100)
	panel.add_child(info)
