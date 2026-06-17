extends Control
class_name MindSnakeHUD

var score_label: Label
var state_label: Label
var hint_label: Label


func _ready() -> void:
	_setup()


func _setup() -> void:
	score_label = Label.new()
	score_label.text = "分数: 0"
	score_label.add_theme_font_size_override("font_size", 18)
	score_label.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_PRIMARY)
	score_label.position = Vector2(24, 24)
	score_label.size = Vector2(300, 30)
	add_child(score_label)

	state_label = Label.new()
	state_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	state_label.add_theme_font_size_override("font_size", 22)
	state_label.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_PRIMARY)
	state_label.position = Vector2(0, 60)
	state_label.size = Vector2(GlobalConfig.GAME_WIDTH, 36)
	add_child(state_label)

	hint_label = Label.new()
	hint_label.text = "方向键控制蛇 | ESC 返回"
	hint_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint_label.add_theme_font_size_override("font_size", 13)
	hint_label.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_SECONDARY)
	hint_label.position = Vector2(0, GlobalConfig.GAME_HEIGHT - 40)
	hint_label.size = Vector2(GlobalConfig.GAME_WIDTH, 24)
	add_child(hint_label)


func update_score(s: int) -> void:
	score_label.text = "分数: %d  长度: %d" % [s, s / 10 + 3]


func update_state(text: String) -> void:
	state_label.text = text


func show_game_over(score: int, rating: String) -> void:
	state_label.text = "游戏结束"

	var panel := Panel.new()
	panel.size = Vector2(400, 160)
	panel.position = Vector2((GlobalConfig.GAME_WIDTH - 400) / 2.0, (GlobalConfig.GAME_HEIGHT - 160) / 2.0)

	var sb := StyleBoxFlat.new()
	sb.bg_color = GlobalConfig.PANEL_BG
	sb.border_color = GlobalConfig.UI_ACCENT
	sb.border_width_left = 2
	sb.border_width_right = 2
	sb.border_width_top = 2
	sb.border_width_bottom = 2
	sb.corner_radius_top_left = 12
	sb.corner_radius_top_right = 12
	sb.corner_radius_bottom_left = 12
	sb.corner_radius_bottom_right = 12
	panel.add_theme_stylebox_override("panel", sb)
	add_child(panel)

	var info := Label.new()
	info.text = "得分: %d — %s\n按 Enter 重新开始 | ESC 返回" % [score, rating]
	info.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	info.add_theme_font_size_override("font_size", 18)
	info.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_PRIMARY)
	info.position = Vector2(0, 30)
	info.size = Vector2(400, 100)
	panel.add_child(info)
