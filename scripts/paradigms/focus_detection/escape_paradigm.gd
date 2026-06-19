extends BaseParadigm
## EscapeParadigm — 密室逃脱: 保险箱→书架→食谱→逃脱

var _spotlight: Spotlight
var _map: RoomMap
var _keypad: EscapeKeypad
var _door: ExitDoor
var _mode: EscapeMode
var _hud: EscapeHUD
var _safe: SafePuzzle
var _bookshelf: BookshelfPuzzle
var _recipe: RecipePuzzle

var _keyboard_focus: bool = false
var _story_phase: int = 0
var _code_digits: Array = [0, 0, 0, 0]
var _solved_count: int = 0
var _current_clue: String = ""


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
	_current_clue = ""
	_play_intro()


func _on_paradigm_end() -> void:
	print("[密室逃脱] 得分: %d" % _mode.get_score())


func _on_bci_data(data: Dictionary) -> void:
	_spotlight.focus_ratio = data.get("ratio", 1.5)


# ============================================================
# 剧情
# ============================================================

func _play_intro() -> void:
	_hud.show_narrative("")
	_narrate("你睁开眼。\n陌生的天花板。空气里弥漫着灰尘。", 2.5, func():
		_narrate("你试图起身——头痛得厉害。", 2.0, func():
			_narrate("这是哪儿？为什么你什么都不记得了。", 2.0, func():
				_narrate("你摸到面前一张字条，\n借着微弱的光，你读到：", 2.5, func():
					_narrate("「亲爱的访客，\n你失去的记忆，锁在这间密室里。\n每个房间都藏着一把钥匙——\n不是铁的，是数字的。\n集齐它们，门就会开。」\n—— X", 4.5, func():
						_begin_phase1()
					)
				)
			)
		)
	)


func _begin_phase1() -> void:
	_story_phase = 1
	_current_clue = "客厅"
	_hud.update_layer(0)
	_hud.update_info("先在客厅找找线索吧")
	_narrate("你环顾四周——客厅里似乎有什么东西\n在黑暗中泛着微光。\n走近看看。", 3.0, func():
		_hud.show_narrative("")
	)


func _narrate(text: String, dur: float, cb: Callable) -> void:
	_hud.show_narrative(text)
	get_tree().create_timer(dur).timeout.connect(cb)


# ============================================================
# 场景
# ============================================================

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

	# 客厅: 保险箱 (2位)
	_safe = SafePuzzle.new()
	_safe.name = "Safe"
	_safe.position = _map.get_room_center(0) - Vector2(100, 100)
	_safe.setup(4, 7, _spotlight)
	add_child(_safe)

	# 书房: 书架 (1位)
	_bookshelf = BookshelfPuzzle.new()
	_bookshelf.name = "Bookshelf"
	_bookshelf.position = _map.get_room_center(1) - Vector2(200, 60)
	_bookshelf.setup(_spotlight)
	add_child(_bookshelf)

	# 厨房: 食谱 (1位)
	_recipe = RecipePuzzle.new()
	_recipe.name = "Recipe"
	_recipe.position = _map.get_room_center(2) - Vector2(160, 80)
	_recipe.setup(_spotlight)
	add_child(_recipe)

	# 客厅: 键盘
	_keypad = EscapeKeypad.new()
	_keypad.name = "Keypad"
	_keypad.set_spotlight(_spotlight)
	_keypad.position = Vector2(100, 220)
	add_child(_keypad)

	# 卧室: 出口
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


# ============================================================
# 谜题回调
# ============================================================

func on_safe_solved() -> void:
	_code_digits[0] = _safe.digit1
	_code_digits[1] = _safe.digit2
	_on_puzzle_solved(
		"保险箱上的划痕指向 %d 和 %d" % [_safe.digit1, _safe.digit2],
		"书房",
		"纸条背面写着：「去书房看看书架」"
	)


func on_bookshelf_solved() -> void:
	_code_digits[2] = _bookshelf.missing_digit
	_on_puzzle_solved(
		"缺失的那本书编号是 %d" % _bookshelf.missing_digit,
		"厨房",
		"书架底层刻着一行小字：「答案在厨房」"
	)


func _on_recipe_read() -> void:
	if _recipe.solved:
		return
	_recipe.mark_solved()
	_code_digits[3] = _recipe.digit1
	_on_puzzle_solved(
		"食谱上标注的克数: %dg" % _recipe.digit1,
		"客厅",
		"所有数字都齐了——回客厅输入密码"
	)


func _on_puzzle_solved(msg: String, next_room: String, hint: String) -> void:
	_solved_count += 1
	_current_clue = next_room
	_hud.show_narrative(msg + "\n\n" + hint)
	AudioManager.play_hit(8)

	var progress := ""
	for i in range(4):
		progress += str(_code_digits[i]) if _code_digits[i] > 0 else "_"
	_hud.update_info("密码: %s  谜题: %d/3   → %s" % [progress, _solved_count, next_room])

	get_tree().create_timer(3.0).timeout.connect(func():
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
	_hud.update_info("密码: %s  回客厅输入键盘!" % code)
	_mode.code = code
	_narrate("三个谜题已破。\n密码是 %s。\n握着它，走向客厅的键盘。" % code, 3.0, func():
		_hud.show_narrative("")
		_keypad.show_for_code(code)
	)


# ============================================================
# 解锁 → 逃脱
# ============================================================

func on_keypad_unlocked() -> void:
	_hud.update_layer(2)
	_hud.update_info("卧室的门可以打开了!")
	_narrate("键盘亮了绿灯。\n你听到卧室方向传来一声闷响——\n门锁开了。", 2.5, func():
		_hud.show_narrative("")
		_door.activate(_spotlight)
	)


func _on_escaped() -> void:
	_mode.escape()
	var score := _mode.get_score()
	var rating := _mode.get_rating()
	_narrate("门开了。光线涌入。\n你看到了镜子里的自己——\n记忆如潮水般涌回。\n\n「你不是别人。\n你就是 X。」", 4.5, func():
		_hud.update_layer(3)
		_hud.show_escaped(score, rating)
		_hud.show_narrative("")
	)
	_spotlight.focus_ratio = 0
	AudioManager.play_hit(10)


# ============================================================
# 主循环
# ============================================================

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

	# 食谱自动读取
	if _story_phase >= 1 and not _recipe.solved and _spotlight:
		var rc := _recipe.global_position + _recipe.size / 2.0
		if rc.distance_to(_spotlight.global_position) < _spotlight.get_radius() * 0.5:
			_recipe._focus_time += delta
			if _recipe._focus_time >= 2.0:
				_on_recipe_read()


# ============================================================
# 键盘
# ============================================================

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
	_current_clue = ""
	await get_tree().process_frame
	_on_paradigm_start()
