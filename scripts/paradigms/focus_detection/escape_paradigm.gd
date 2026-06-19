extends BaseParadigm
## EscapeParadigm — 密室逃脱: 4室1厅地图 + 情景引入

var _spotlight: Spotlight
var _digits: Array[HiddenDigit] = []
var _keypad: EscapeKeypad
var _door: ExitDoor
var _map: RoomMap
var _mode: EscapeMode
var _hud: EscapeHUD
var _keyboard_focus: bool = false
var _intro_done: bool = false


func _ready() -> void:
	paradigm_type = GlobalConfig.ParadigmType.FOCUS_DETECTION
	super._ready()


func _on_paradigm_start() -> void:
	_setup_room()
	_setup_game()
	_mode.start_new(4)
	_show_intro()


func _on_paradigm_end() -> void:
	print("[密室逃脱] 得分: %d" % _mode.get_score())


func _on_bci_data(data: Dictionary) -> void:
	_spotlight.focus_ratio = data.get("ratio", 1.5)


# --- 情景引入 ---

func _show_intro() -> void:
	_hud.layer_label.text = "⚡ 停电了！"
	_hud.info_label.text = "用你的专注力照亮黑暗，找到密码逃出去..."
	get_tree().create_timer(3.0).timeout.connect(func():
		_intro_done = true
		_hud.update_layer(0)
		_hud.update_info("已发现: 0 / 4")
	)


# --- 场景 ---

func _setup_room() -> void:
	var bg := ColorRect.new()
	bg.name = "Background"
	bg.color = Color("0A0A0A")
	bg.size = Vector2(GlobalConfig.GAME_WIDTH, GlobalConfig.GAME_HEIGHT)
	bg.position = Vector2.ZERO
	add_child(bg)
	move_child(bg, 0)


func _setup_game() -> void:
	# 地图
	_map = RoomMap.new()
	_map.name = "RoomMap"
	add_child(_map)

	# 光圈 — 从客厅开始
	_spotlight = Spotlight.new()
	_spotlight.name = "Spotlight"
	_spotlight.position = _map.get_room_center(0)
	add_child(_spotlight)

	# 隐藏数字分布: 书房2个, 厨房2个
	var placements := [
		{"room": 1, "idx": 0}, {"room": 1, "idx": 1},
		{"room": 2, "idx": 2}, {"room": 2, "idx": 3},
	]
	for p in placements:
		var d := HiddenDigit.new()
		d.name = "Digit%d" % p.idx
		d.index = p.idx
		d.digit = randi_range(1, 9)
		d.position = _map.get_random_pos_in_room(p.room)
		d.set_spotlight(_spotlight)
		add_child(d)
		_digits.append(d)

	# 密码键盘 — 客厅左侧
	_keypad = EscapeKeypad.new()
	_keypad.name = "Keypad"
	_keypad.set_spotlight(_spotlight)
	_keypad.position = Vector2(100, 150)
	add_child(_keypad)

	# 出口门 — 卧室
	_door = ExitDoor.new()
	_door.name = "ExitDoor"
	_door.door_escaped.connect(_on_escaped)
	_door.position = _map.get_room_center(3) - Vector2(100, 150)
	add_child(_door)

	_mode = EscapeMode.new()

	_hud = EscapeHUD.new()
	_hud.name = "HUD"
	_hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_hud)


# --- 数字被发现 ---

func on_digit_found(_index: int) -> void:
	if not _intro_done:
		return
	var all_found := _mode.digit_found()
	_hud.update_info("已发现: %d / 4" % _mode.found_digits)

	if all_found:
		AudioManager.play_hit(8)
		_hud.update_layer(1)
		_hud.update_info("密码: 看看你找到的数字, 去客厅开锁!")
		_keypad.show_for_code(_mode.get_code())


# --- 键盘解锁 ---

func on_keypad_unlocked() -> void:
	_hud.update_layer(2)
	_hud.update_info("去卧室! 光照门锁按 Enter 逃脱!")
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
	if not _intro_done:
		return
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
	_intro_done = false
	await get_tree().process_frame
	_on_paradigm_start()
