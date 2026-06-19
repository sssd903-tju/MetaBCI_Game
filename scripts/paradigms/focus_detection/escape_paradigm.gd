extends BaseParadigm
## EscapeParadigm — 密室逃脱: 剧情驱动

var _spotlight: Spotlight
var _digits: Array[HiddenDigit] = []
var _keypad: EscapeKeypad
var _door: ExitDoor
var _map: RoomMap
var _mode: EscapeMode
var _hud: EscapeHUD
var _keyboard_focus: bool = false
var _story_phase: int = 0


func _ready() -> void:
	paradigm_type = GlobalConfig.ParadigmType.FOCUS_DETECTION
	super._ready()


func _on_paradigm_start() -> void:
	_setup_room()
	_setup_game()
	_mode.start_new(4)
	_story_phase = 0
	_narrate("你在一间漆黑的屋子里醒来...", 2.0, func():
		_narrate("头痛欲裂, 什么都不记得了", 2.0, func():
			_narrate("桌上有一张纸条:", 1.5, func():
				_narrate_room("客厅", "🛋", "欢迎。我是X。\n找到藏在书房和厨房的4个数字密码。\n输入客厅的键盘。\n卧室的门会为你打开。\n—— 你只有时间, 没有退路", 3.0, func():
					_story_phase = 1
					_hud.update_layer(0)
					_hud.update_info("探索书房和厨房, 找到 4 个隐藏数字")
				)
			)
		)
	)


func _on_paradigm_end() -> void:
	print("[密室逃脱] 得分: %d" % _mode.get_score())


func _on_bci_data(data: Dictionary) -> void:
	_spotlight.focus_ratio = data.get("ratio", 1.5)


# --- 叙事 ---

func _narrate(text: String, duration: float, callback: Callable) -> void:
	_hud.show_narrative(text)
	get_tree().create_timer(duration).timeout.connect(callback)


func _narrate_room(room: String, icon: String, text: String, duration: float, callback: Callable) -> void:
	_hud.show_narrative_room(room, icon, text)
	get_tree().create_timer(duration).timeout.connect(callback)


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
	_map = RoomMap.new()
	_map.name = "RoomMap"
	add_child(_map)

	_spotlight = Spotlight.new()
	_spotlight.name = "Spotlight"
	_spotlight.position = _map.get_room_center(0)
	add_child(_spotlight)

	# 隐藏数字: 书房和厨房各2个, 每个有剧情文本
	var digit_clues := [
		{"room": 1, "clue": "书架上掉下一本书...\n第 7 页画着圈"},
		{"room": 1, "clue": "书桌抽屉里刻着一行字:\n'她最爱第 3 个季节'"},
		{"room": 2, "clue": "冰箱贴下面压着纸条:\n'买 5 个鸡蛋'"},
		{"room": 2, "clue": "橱柜门内侧写着:\n密码之一是 9"},
	]
	for i in range(4):
		var d := HiddenDigit.new()
		d.name = "Digit%d" % i
		d.index = i
		d.digit = [7, 3, 5, 9][i]  # 固定密码 7359
		d.position = _map.get_random_pos_in_room(digit_clues[i].room)
		d.clue_text = digit_clues[i].clue
		d.set_spotlight(_spotlight)
		add_child(d)
		_digits.append(d)

	_keypad = EscapeKeypad.new()
	_keypad.name = "Keypad"
	_keypad.set_spotlight(_spotlight)
	_keypad.position = Vector2(100, 150)
	add_child(_keypad)

	_door = ExitDoor.new()
	_door.name = "ExitDoor"
	_door.door_escaped.connect(_on_escaped)
	_door.position = _map.get_room_center(3) - Vector2(100, 150)
	add_child(_door)

	_mode = EscapeMode.new()
	# 固定密码
	_mode.code = "7359"

	_hud = EscapeHUD.new()
	_hud.name = "HUD"
	_hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_hud)

	_hud.show_narrative("")


# --- 数字被发现 ---

func on_digit_found(index: int) -> void:
	if _story_phase < 1:
		return

	var clue := ""
	if index < _digits.size():
		clue = _digits[index].clue_text

	_mode.digit_found()
	_hud.update_info("已发现: %d / 4   %s" % [_mode.found_digits, ["", "▮", "▮▮", "▮▮▮", "▮▮▮▮"][_mode.found_digits]])
	AudioManager.play_combo(1)

	# 显示线索
	if clue != "":
		_hud.show_narrative(clue)
		get_tree().create_timer(2.0).timeout.connect(func():
			if _mode.current_layer == EscapeMode.Layer.FIND_CODE:
				_hud.show_narrative("")
		)

	if _mode.found_digits >= _mode.total_digits:
		AudioManager.play_hit(8)
		_hud.update_layer(1)
		_hud.update_info("密码已全部找到! 去客厅输入键盘")
		_narrate("四位数都找到了...\n去客厅打开键盘锁", 2.5, func():
			_hud.show_narrative("")
			_keypad.show_for_code(_mode.get_code())
		)


# --- 键盘解锁 ---

func on_keypad_unlocked() -> void:
	_narrate("咔嗒——锁开了。\n卧室的门应该能打开了...", 2.5, func():
		_hud.show_narrative("")
		_hud.update_layer(2)
		_hud.update_info("去卧室! 光照门锁按 Enter 逃脱")
		_door.activate(_spotlight)
	)


# --- 逃脱 ---

func _on_escaped() -> void:
	_mode.escape()
	var score := _mode.get_score()
	var rating := _mode.get_rating()
	_narrate("门开了。光芒涌进来。\n你想起了自己的名字。\n但这只是开始...", 3.0, func():
		_hud.update_layer(3)
		_hud.show_escaped(score, rating)
		_hud.show_narrative("")
	)
	_spotlight.focus_ratio = 0
	AudioManager.play_hit(10)


# --- 主循环 ---

func _process(delta: float) -> void:
	if _story_phase < 1:
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
	_story_phase = 0
	await get_tree().process_frame
	_on_paradigm_start()
