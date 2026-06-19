extends Control
class_name EscapeHUD

var layer_label: Label
var info_label: Label
var timer_label: Label
var focus_bar: ColorRect
var focus_bg: ColorRect
var hint_label: Label
var narrate_label: Label


func _ready() -> void:
	layer_label = _lbl("第一关: 寻找密码", 20, GlobalConfig.UI_TEXT_PRIMARY)
	layer_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	layer_label.position = Vector2(0, 16)
	layer_label.size = Vector2(GlobalConfig.GAME_WIDTH, 30)
	add_child(layer_label)

	info_label = _lbl("已发现: 0 / 4", 15, GlobalConfig.UI_TEXT_SECONDARY)
	info_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	info_label.position = Vector2(0, 50)
	info_label.size = Vector2(GlobalConfig.GAME_WIDTH, 22)
	add_child(info_label)

	timer_label = _lbl("⏱ 0s", 14, GlobalConfig.UI_TEXT_SECONDARY)
	timer_label.position = Vector2(24, 50)
	timer_label.size = Vector2(150, 20)
	add_child(timer_label)

	focus_bg = ColorRect.new()
	focus_bg.color = GlobalConfig.PANEL_BORDER
	focus_bg.size = Vector2(100, 8)
	focus_bg.position = Vector2(GlobalConfig.GAME_WIDTH - 130, 24)
	add_child(focus_bg)

	focus_bar = ColorRect.new()
	focus_bar.color = GlobalConfig.UI_SUCCESS
	focus_bar.size = Vector2(50, 8)
	focus_bar.position = focus_bg.position
	add_child(focus_bar)

	hint_label = _lbl("WASD 移动  |  1/2/3 模拟专注度  |  ESC 返回", 11, GlobalConfig.UI_TEXT_SECONDARY)
	hint_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint_label.position = Vector2(0, GlobalConfig.GAME_HEIGHT - 26)
	hint_label.size = Vector2(GlobalConfig.GAME_WIDTH, 20)
	add_child(hint_label)


func _lbl(text: String, font_size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", font_size)
	l.add_theme_color_override("font_color", color)
	return l


func update_layer(layer: int) -> void:
	match layer:
		0: layer_label.text = "第一关: 寻找密码"
		1: layer_label.text = "第二关: 输入密码解锁"
		2: layer_label.text = "第三关: 找到出口逃脱!"
		3: layer_label.text = "逃脱成功!"


func update_info(text: String) -> void:
	info_label.text = text


func update_timer(t: float) -> void:
	timer_label.text = "⏱ %ds" % int(t)


func update_focus(ratio: float) -> void:
	var pct := clampf(ratio / 4.0, 0.0, 1.0)
	focus_bar.size.x = focus_bg.size.x * pct
	focus_bar.color = GlobalConfig.focus_to_color(ratio)


func show_narrative(text: String) -> void:
	if narrate_label == null:
		narrate_label = _lbl("", 17, Color("C0B090"))
		narrate_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		narrate_label.position = Vector2(0, GlobalConfig.GAME_HEIGHT / 2.0 - 80)
		narrate_label.size = Vector2(GlobalConfig.GAME_WIDTH, 120)
		add_child(narrate_label)
	narrate_label.text = text


func show_narrative_room(room: String, icon: String, text: String) -> void:
	show_narrative("[%s %s]\n%s" % [icon, room, text])


func show_escaped(score: int, rating: String) -> void:
	show_narrative("")
	info_label.text = "得分: %d — %s  |  Enter 再来 | ESC 返回" % [score, rating]

