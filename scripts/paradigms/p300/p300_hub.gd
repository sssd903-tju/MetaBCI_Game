extends Control

func _ready() -> void:
	var bg := ColorRect.new()
	bg.color = GlobalConfig.BG_WARM_CREAM
	bg.size = Vector2(GlobalConfig.GAME_WIDTH, GlobalConfig.GAME_HEIGHT)
	add_child(bg)

	var title := _lbl("P300 事件相关电位", 28, GlobalConfig.UI_TEXT_PRIMARY)
	title.position = Vector2(0, 200)
	title.size = Vector2(GlobalConfig.GAME_WIDTH, 40)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(title)

	var modes := [
		{"name": "🃏 卡牌读心", "scene": "res://scenes/p300/CardGame.tscn"},
		{"name": "🚀 太空采矿", "scene": "res://scenes/p300/SpaceMiner.tscn"},
	]
	for i in range(modes.size()):
		var m: Dictionary = modes[i]
		var btn := Button.new()
		btn.text = m.name
		btn.position = Vector2((GlobalConfig.GAME_WIDTH - 400) / 2.0, 380 + i * 100)
		btn.size = Vector2(400, 56)
		var s := StyleBoxFlat.new()
		s.bg_color = GlobalConfig.BG_WARM_CREAM
		s.border_color = GlobalConfig.PLATFORM_NORMAL
		s.border_width_left = 2
		s.border_width_right = 2
		s.border_width_top = 2
		s.border_width_bottom = 2
		s.set_corner_radius_all(10)
		btn.add_theme_stylebox_override("normal", s)
		btn.add_theme_font_size_override("font_size", 20)
		btn.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_PRIMARY)
		btn.pressed.connect(_go.bind(m.scene))
		add_child(btn)

	var back := _lbl("ESC 返回主菜单", 13, GlobalConfig.UI_TEXT_SECONDARY)
	back.position = Vector2(0, GlobalConfig.GAME_HEIGHT - 50)
	back.size = Vector2(GlobalConfig.GAME_WIDTH, 24)
	back.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(back)


func _lbl(text: String, font_size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", font_size)
	l.add_theme_color_override("font_color", color)
	return l


func _go(path: String) -> void:
	get_tree().change_scene_to_file(path)


func _input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel"):
		ParadigmManager.go_to_main_menu()
