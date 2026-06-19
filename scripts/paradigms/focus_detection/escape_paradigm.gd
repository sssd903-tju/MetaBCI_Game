extends BaseParadigm
## EscapeParadigm — 密室逃脱: 4种解谜 + 剧情驱动

var _spotlight: Spotlight
var _map: RoomMap
var _keypad: EscapeKeypad
var _door: ExitDoor
var _mode: EscapeMode
var _hud: EscapeHUD

# 谜题
var _clock: ClockPuzzle
var _bookshelf: BookshelfPuzzle
var _recipe: RecipePuzzle

var _keyboard_focus: bool = false
var _story_phase: int = 0
var _code_digits: Array = [0, 0, 0, 0]
var _solved_count: int = 0


func _ready() -> void:
	paradigm_type = GlobalConfig.ParadigmType.FOCUS_DETECTION
	super._ready()


func _on_paradigm_start() -> void:
	_setup_room()
	_setup_game()
	_mode.start_new(4)
	_story_phase = 0
	_solved_count = 0
	_code_digits = [0, 0, 0, 0]
	_play_intro()


func _on_paradigm_end() -> void:
	print("[密室逃脱] 得分: %d" % _mode.get_score())


func _on_bci_data(data: Dictionary) -> void:
	_spotlight.focus_ratio = data.get("ratio", 1.5)


# --- 剧情 ---

func _play_intro() -> void:
	_narrate("头痛欲裂…\n你在黑暗中睁开眼。", 2.5, func():
		_narrate("陌生的房间。冰冷的空气。", 2.0, func():
			_narrate("桌上压着一张字条，墨迹未干:", 2.0, func():
				_narrate("「你只有一条命，一间密室，\n和三个谜题。破解它们，\n密码自现。出门之后，\n你会知道我是谁。」\n—— X", 4.0, func():
					_hud.update_layer(0)
					_hud.update_info("探索房间, 破解谜题, 收集密码")
					_story_phase = 1
				)
			)
		)
	)


func _narrate(text: String, dur: float, cb: Callable) -> void:
	_hud.show_narrative(text)
	get_tree().create_timer(dur).timeout.connect(cb)


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

	# 客厅: 挂钟谜题 (2位)
	_clock = ClockPuzzle.new()
	_clock.name = "Clock"
	_clock.position = _map.get_room_center(0) - Vector2(90, 100)
	_clock.setup(7, 3, _spotlight)  # 7:30 → digits 7,3
	add_child(_clock)

	# 书房: 书架谜题 (1位)
	_bookshelf = BookshelfPuzzle.new()
	_bookshelf.name = "Bookshelf"
	_bookshelf.position = _map.get_room_center(1) - Vector2(200, 60)
	_bookshelf.setup(_spotlight)
	add_child(_bookshelf)

	# 厨房: 食谱谜题 (1位)
	_recipe = RecipePuzzle.new()
	_recipe.name = "Recipe"
	_recipe.position = _map.get_room_center(2) - Vector2(160, 80)
	_recipe.setup(_spotlight)
	add_child(_recipe)

	# 客厅: 密码键盘
	_keypad = EscapeKeypad.new()
	_keypad.name = "Keypad"
	_keypad.set_spotlight(_spotlight)
	_keypad.position = Vector2(100, 200)
	add_child(_keypad)

	# 卧室: 出口门
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
	_hud.show_narrative("")


# --- 谜题回调 ---

func on_clock_solved() -> void:
	_code_digits[0] = _clock.hour_digit
	_code_digits[1] = _clock.min_digit
	_on_puzzle_solved("挂钟指针指向 %d:%d0" % [_clock.hour_digit, _clock.min_digit])


func on_bookshelf_solved() -> void:
	_code_digits[2] = _bookshelf.missing_digit
	_on_puzzle_solved("缺失的编号是 %d" % _bookshelf.missing_digit)


func _on_recipe_read() -> void:
	if _recipe.solved:
		return
	_recipe.mark_solved()
	_code_digits[3] = _recipe.digit1
	_on_puzzle_solved("食谱主料: %dg" % _recipe.digit1)


func _on_puzzle_solved(msg: String) -> void:
	_solved_count += 1
	_hud.show_narrative(msg)
	AudioManager.play_hit(8)

	var progress := ""
	for i in range(4):
		progress += str(_code_digits[i]) if _code_digits[i] > 0 else "_"
	_hud.update_info("密码: %s   谜题: %d/3" % [progress, _solved_count])

	get_tree().create_timer(2.0).timeout.connect(func():
		_hud.show_narrative("")
		if _solved_count >= 3:
			_all_solved()
	)


func _all_solved() -> void:
	var code := ""
	for d in _code_digits:
		code += str(d)
	_story_phase = 2
	_hud.update_layer(1)
	_hud.update_info("密码: %s  去客厅输入键盘!" % code)
	_narrate("三个谜题都解开了…\n密码是 %s\n去客厅的键盘输入吧。" % code, 3.0, func():
		_hud.show_narrative("")
		_keypad.show_for_code(code)
	)
	_mode.code = code


# --- 键盘解锁 ---

func on_keypad_unlocked() -> void:
	_narrate("咔——锁芯转动。\n卧室的门可以打开了。", 2.5, func():
		_hud.update_layer(2)
		_hud.update_info("去卧室! 光照门锁按 Enter 逃脱")
		_door.activate(_spotlight)
	)


# --- 逃脱 ---

func _on_escaped() -> void:
	_mode.escape()
	var score := _mode.get_score()
	var rating := _mode.get_rating()
	_narrate("阳光刺破黑暗。\n门外站着一个熟悉的身影。\n「你终于醒了。」\n—— 那是你自己。", 4.0, func():
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

	# 食谱: 当光照超过2秒自动读取
	if _story_phase >= 1 and not _recipe.solved and _spotlight:
		var rcenter := _recipe.global_position + _recipe.size / 2.0
		if rcenter.distance_to(_spotlight.global_position) < _spotlight.get_radius() * 0.5:
			_recipe._focus_time += delta
			if _recipe._focus_time >= 2.0:
				_on_recipe_read()


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
	_keyboard_focus = false
	_story_phase = 0
	_solved_count = 0
	_code_digits = [0, 0, 0, 0]
	await get_tree().process_frame
	_on_paradigm_start()
