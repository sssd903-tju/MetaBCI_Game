extends BaseParadigm
## EscapeParadigm — 专注之光密室逃脱 (3层关卡)

var _spotlight: Spotlight
var _digits: Array[HiddenDigit] = []
var _keypad: EscapeKeypad
var _door: ExitDoor
var _mode: EscapeMode
var _hud: EscapeHUD
var _keyboard_focus: bool = false


func _ready() -> void:
	paradigm_type = GlobalConfig.ParadigmType.FOCUS_DETECTION
	super._ready()


func _on_paradigm_start() -> void:
	_setup_room()
	_setup_game()
	_mode.start_new(4)


func _on_paradigm_end() -> void:
	print("[密室逃脱] 得分: %d" % _mode.get_score())


func _on_bci_data(data: Dictionary) -> void:
	_spotlight.focus_ratio = data.get("ratio", 1.5)


# --- 场景构建 ---

func _setup_room() -> void:
	var bg := ColorRect.new()
	bg.name = "Background"
	bg.color = Color("0A0A0A")
	bg.size = Vector2(GlobalConfig.GAME_WIDTH, GlobalConfig.GAME_HEIGHT)
	bg.position = Vector2.ZERO
	add_child(bg)
	move_child(bg, 0)

	# 房间轮廓
	var wall := ColorRect.new()
	wall.color = Color("1A1A1A")
	wall.size = Vector2(GlobalConfig.GAME_WIDTH - 40, GlobalConfig.GAME_HEIGHT - 40)
	wall.position = Vector2(20, 20)
	add_child(wall)
	for i in range(1, 5):
		var line := ColorRect.new()
		line.color = Color("1A1A1A")
		line.size = Vector2(GlobalConfig.GAME_WIDTH - 40, 1)
		line.position = Vector2(20, i * GlobalConfig.GAME_HEIGHT / 5.0)
		add_child(line)


func _setup_game() -> void:
	# 光圈
	_spotlight = Spotlight.new()
	_spotlight.name = "Spotlight"
	add_child(_spotlight)

	# 4个隐藏数字
	var rng := RandomNumberGenerator.new()
	rng.seed = randi()
	var margin := 100.0
	for i in range(4):
		var d := HiddenDigit.new()
		d.name = "Digit%d" % i
		d.index = i
		d.digit = rng.randi_range(1, 9)
		d.position = Vector2(
			rng.randf_range(margin, GlobalConfig.GAME_WIDTH - margin),
			rng.randf_range(150, GlobalConfig.GAME_HEIGHT - margin)
		)
		d.set_spotlight(_spotlight)
		add_child(d)
		_digits.append(d)

	# 密码键盘 (先隐藏)
	_keypad = EscapeKeypad.new()
	_keypad.name = "Keypad"
	_keypad.set_spotlight(_spotlight)
	add_child(_keypad)

	# 出口门 (先隐藏)
	_door = ExitDoor.new()
	_door.name = "ExitDoor"
	_door.door_escaped.connect(_on_escaped)
	add_child(_door)

	_mode = EscapeMode.new()

	_hud = EscapeHUD.new()
	_hud.name = "HUD"
	_hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_hud)

	_hud.update_layer(0)
	_hud.update_info("已发现: 0 / 4")


# --- 数字被发现 ---

func on_digit_found(_index: int) -> void:
	var all_found := _mode.digit_found()
	_hud.update_info("已发现: %d / 4" % _mode.found_digits)

	if all_found:
		AudioManager.play_hit(8)
		_hud.update_layer(1)
		_hud.update_info("记住密码, 输入到键盘")
		_keypad.show_for_code(_mode.get_code())


# --- 键盘解锁 ---

func on_keypad_unlocked() -> void:
	_mode.current_layer = EscapeMode.Layer.ESCAPE
	_hud.update_layer(2)
	_hud.update_info("找到出口门, 光照锁孔按 Enter!")
	_door.activate(_spotlight)


# --- 逃脱 ---

func _on_escaped() -> void:
	_mode.escape()
	var score := _mode.get_score()
	var rating := _mode.get_rating()
	_hud.update_layer(3)
	_hud.show_escaped(score, rating)
	_spotlight.focus_ratio = 0
	AudioManager.play_hit(10)


# --- 主循环 ---

func _process(delta: float) -> void:
	if _mode.current_layer == EscapeMode.Layer.DONE:
		return

	if not _keyboard_focus:
		_spotlight.focus_ratio = BCIConnector.latest_focus_ratio

	_mode.elapsed_time += delta
	_mode.track_focus(_spotlight.focus_ratio)
	_hud.update_timer(_mode.elapsed_time)
	_hud.update_focus(_spotlight.focus_ratio)


# --- 键盘 ---

func _input(event: InputEvent) -> void:
	if _mode.current_layer == EscapeMode.Layer.DONE:
		if event.is_action_pressed("ui_accept"):
			_restart()
		elif event.is_action_pressed("ui_cancel"):
			ParadigmManager.go_to_main_menu()
		return

	if event.is_action_pressed("ui_cancel"):
		ParadigmManager.go_to_main_menu()

	if _mode.current_layer == EscapeMode.Layer.ESCAPE:
		if event.is_action_pressed("ui_accept"):
			_door.try_escape()

	if event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_1: _spotlight.focus_ratio = 0.8; _keyboard_focus = true
			KEY_2: _spotlight.focus_ratio = 2.0; _keyboard_focus = true
			KEY_3: _spotlight.focus_ratio = 3.2; _keyboard_focus = true


func _restart() -> void:
	for child in get_children():
		if child.name != "Background":
			child.queue_free()
	_digits.clear()
	_keyboard_focus = false
	await get_tree().process_frame
	_on_paradigm_start()
