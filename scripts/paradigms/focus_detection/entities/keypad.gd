extends Control
class_name EscapeKeypad
## Keypad — 密码输入面板, 光照到才可见

var target_code: String = ""
var entered: String = ""
var unlocked: bool = false
var is_active: bool = false
var _spotlight: Spotlight = null
var _buttons: Array[Button] = []
var _display: Label
var _bg: ColorRect


func _ready() -> void:
	size = Vector2(300, 400)
	position = Vector2((GlobalConfig.GAME_WIDTH - 300) / 2.0, (GlobalConfig.GAME_HEIGHT - 400) / 2.0 + 30)

	_bg = ColorRect.new()
	_bg.size = size
	_bg.color = Color("1A1A2E")
	add_child(_bg)

	_display = Label.new()
	_display.text = "____"
	_display.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_display.add_theme_font_size_override("font_size", 32)
	_display.add_theme_color_override("font_color", Color("F0C040"))
	_display.size = Vector2(300, 50)
	_display.position = Vector2(0, 20)
	add_child(_display)

	# 数字按钮 0-9
	var btn_size := Vector2(70, 50)
	var start_x := 25.0
	var start_y := 90.0
	var layout := [
		[1,2,3], [4,5,6], [7,8,9], [-1, 0, -2]
	]  # -1=清除, -2=确认

	for row in range(4):
		for col in range(3):
			var val: int = layout[row][col]
			var btn := Button.new()
			btn.size = btn_size
			btn.position = Vector2(start_x + col * 85, start_y + row * 65)
			if val == -1:
				btn.text = "←"
				btn.pressed.connect(_on_clear)
			elif val == -2:
				btn.text = "✓"
				btn.pressed.connect(_on_confirm)
			else:
				btn.text = str(val)
				btn.pressed.connect(_on_digit.bind(val))
			add_child(btn)
			_buttons.append(btn)

	modulate.a = 0.0
	hide()


func set_spotlight(s: Spotlight) -> void:
	_spotlight = s


func show_for_code(code: String) -> void:
	target_code = code
	entered = ""
	unlocked = false
	_display.text = "____"
	is_active = true
	show()


func _process(_delta: float) -> void:
	if not is_active or unlocked:
		return

	# 光照可见性: 越近越亮
	if _spotlight:
		var center := global_position + size / 2.0
		var dist := center.distance_to(_spotlight.global_position)
		var radius := _spotlight.get_radius()
		modulate.a = lerpf(modulate.a, 1.0 if dist < radius * 1.5 else 0.0, 5.0 * _delta)
	else:
		modulate.a = 0.5


func _on_digit(val: int) -> void:
	if entered.length() >= 4:
		return
	entered += str(val)
	_update_display()
	AudioManager.play_combo(1)


func _on_clear() -> void:
	entered = ""
	_update_display()


func _on_confirm() -> void:
	if entered.length() < 4:
		return
	if entered == target_code:
		unlocked = true
		_display.text = "解锁!"
		_display.add_theme_color_override("font_color", Color.GREEN)
		get_parent().on_keypad_unlocked()
		AudioManager.play_hit(10)
	else:
		_display.text = "错误"
		_display.add_theme_color_override("font_color", Color.RED)
		entered = ""
		AudioManager.play_miss()
		get_tree().create_timer(0.8).timeout.connect(func():
			_display.text = "____"
			_display.add_theme_color_override("font_color", Color("F0C040"))
		)


func _update_display() -> void:
	var txt := entered
	while txt.length() < 4:
		txt += "_"
	_display.text = txt
