extends Control
## SSVEPHub — SSVEP 模式选择 (打地鼠 / 贪吃蛇)

func _ready() -> void:
	var bg := ColorRect.new()
	bg.color = GlobalConfig.BG_WARM_CREAM
	bg.size = Vector2(GlobalConfig.GAME_WIDTH, GlobalConfig.GAME_HEIGHT)
	add_child(bg)

	var title := _lbl("SSVEP 稳态视觉诱发电位", 28, GlobalConfig.UI_TEXT_PRIMARY)
	title.position = Vector2(0, 200)
	title.size = Vector2(GlobalConfig.GAME_WIDTH, 40)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(title)

	var modes := [
		{"name": "🔨 打地鼠", "scene": "res://scenes/ssvep/SSVEPGame.tscn"},
		{"name": "🐍 贪吃蛇", "scene": "res://scenes/ssvep/MindSnakeGame.tscn"},
	]

	for i in range(modes.size()):
		var m: Dictionary = modes[i]
		var btn := Button.new()
		btn.text = m.name
		btn.position = Vector2((GlobalConfig.GAME_WIDTH - 300) / 2.0, 300 + i * 60)
		btn.size = Vector2(300, 48)
		btn.pressed.connect(_load_scene.bind(m.scene))
		add_child(btn)

	var back := _lbl("ESC 返回主菜单", 13, GlobalConfig.UI_TEXT_SECONDARY)
	back.position = Vector2(0, GlobalConfig.GAME_HEIGHT - 50)
	back.size = Vector2(GlobalConfig.GAME_WIDTH, 24)
	back.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(back)


func _lbl(text: String, size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l


func _load_scene(path: String) -> void:
	get_tree().change_scene_to_file(path)


func _input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel"):
		ParadigmManager.go_to_main_menu()
