extends BaseParadigm
## EscapeParadigm — 密室逃脱: 顺序解锁 + 线索收集

var _spotlight: Spotlight
var _rooms: RoomManager
var _keypad: EscapeKeypad
var _door: ExitDoor
var _mode: EscapeMode
var _hud: EscapeHUD
var _safe: SafePuzzle
var _bookshelf: BookshelfPuzzle
var _recipe: RecipePuzzle

var _story_phase: int = 0
var _code_digits: Array = [0, 0, 0, 0]
var _solved_count: int = 0
var _room_cooldown: float = 0.0
var _keyboard_focus: bool = false
var _clues_found: Array[String] = []


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
	_room_cooldown = 0.0
	_keyboard_focus = false
	_clues_found.clear()
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
	_narrate("黑暗中，你摸索着坐起来。", 2.0, func():
		_narrate("指尖触到一张揉皱的纸。", 1.5, func():
			_narrate("「如果你读到这个——\n你已经接受了试炼。」\n「每个房间都锁着通往记忆的门。」\n「解开谜题，门就会开。」\n「线索散落四处，\n全部找到才能逃脱。」\n—— X", 5.0, func():
				_story_phase = 1
				_hud.update_layer(0)
				_hud.update_info("谜题: 0/3  线索: 0/3  在客厅找保险箱")
			)
		)
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
	_rooms = RoomManager.new()
	_rooms.name = "Rooms"
	_rooms.room_changed.connect(_on_room_changed)
	add_child(_rooms)

	_spotlight = Spotlight.new()
	_spotlight.name = "Spotlight"
	_spotlight.position = Vector2(GlobalConfig.GAME_WIDTH * 0.3, GlobalConfig.GAME_HEIGHT * 0.5)
	add_child(_spotlight)

	# 保险箱 (客厅)
	_safe = SafePuzzle.new()
	_safe.position = Vector2(GlobalConfig.GAME_WIDTH * 0.25, GlobalConfig.GAME_HEIGHT * 0.55)
	_safe.setup(4, 7, _spotlight)
	add_child(_safe)

	# 书架 (书房)
	_bookshelf = BookshelfPuzzle.new()
	_bookshelf.position = Vector2(GlobalConfig.GAME_WIDTH * 0.5, GlobalConfig.GAME_HEIGHT * 0.4)
	_bookshelf.setup(_spotlight)
	add_child(_bookshelf)

	# 食谱 (厨房)
	_recipe = RecipePuzzle.new()
	_recipe.position = Vector2(GlobalConfig.GAME_WIDTH * 0.35, GlobalConfig.GAME_HEIGHT * 0.3)
	_recipe.setup(_spotlight)
	add_child(_recipe)

	# 键盘 (客厅)
	_keypad = EscapeKeypad.new()
	_keypad.set_spotlight(_spotlight)
	_keypad.position = Vector2(GlobalConfig.GAME_WIDTH * 0.25, GlobalConfig.GAME_HEIGHT * 0.2)
	add_child(_keypad)

	# 出口 (卧室)
	_door = ExitDoor.new()
	_door.door_escaped.connect(_on_escaped)
	_door.position = Vector2(GlobalConfig.GAME_WIDTH - 240, (GlobalConfig.GAME_HEIGHT - 300) / 2.0)
	add_child(_door)

	_mode = EscapeMode.new()
	_hud = EscapeHUD.new()
	_hud.name = "HUD"
	_hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_hud)
	_hud.show_narrative("")

	_update_visibility()


func _update_visibility() -> void:
	var cr := _rooms.current_room
	_safe.visible = (cr == RoomManager.Room.LIVING)
	_bookshelf.visible = (cr == RoomManager.Room.STUDY)
	_recipe.visible = (cr == RoomManager.Room.KITCHEN)
	_keypad.visible = (cr == RoomManager.Room.LIVING)
	_door.visible = (cr == RoomManager.Room.BEDROOM)


func _on_room_changed(_from: int, to: int) -> void:
	_update_visibility()
	var rn := _rooms.get_room_name(to)
	_hud.show_narrative("—— %s ——" % rn)
	get_tree().create_timer(1.0).timeout.connect(func():
		if _story_phase >= 1:
			_hud.show_narrative("")
	)


# ============================================================
# 谜题 → 解锁门
# ============================================================

func on_safe_solved() -> void:
	_code_digits[0] = _safe.digit1
	_code_digits[1] = _safe.digit2
	_add_clue("客厅线索: 「她最后一次出现在书房」")
	_rooms.unlock_door("living_study")
	_solved(1, "书房的门开了。去看看。")

func on_bookshelf_solved() -> void:
	_code_digits[2] = _bookshelf.missing_digit
	_add_clue("书房线索: 「食谱里有重要的数字」")
	_rooms.unlock_door("study_bedroom")
	# 也解锁 书房→厨房 (通过客厅绕)
	_rooms.unlock_door("living_kitchen")
	_solved(2, "厨房和卧室的门可以通行了。")

func _on_recipe_read() -> void:
	if _recipe.solved: return
	_recipe.mark_solved()
	_code_digits[3] = _recipe.digit1
	_add_clue("厨房线索: 「所有数字都在字条背面」")
	_rooms.unlock_door("kitchen_bedroom")
	_solved(3, "最后一个门也开了。密码已完整。")


func _add_clue(clue: String) -> void:
	if clue not in _clues_found:
		_clues_found.append(clue)


func _solved(n: int, msg: String) -> void:
	_solved_count = n
	_hud.show_narrative(msg)
	AudioManager.play_hit(8)

	var progress := ""
	for i in range(4):
		progress += str(_code_digits[i]) if _code_digits[i] > 0 else "_"
	_hud.update_info("谜题: %d/3  线索: %d/3  密码: %s" % [_solved_count, _clues_found.size(), progress])

	get_tree().create_timer(2.5).timeout.connect(func():
		_hud.show_narrative("")
		if _solved_count >= 3:
			_ready_to_escape()
	)


func _ready_to_escape() -> void:
	var code := ""
	for d in _code_digits:
		code += str(d)
	_story_phase = 2
	_mode.code = code
	_hud.update_layer(1)
	_hud.update_info("密码: %s  回客厅输入!" % code)
	_narrate("三个谜题已破。\n密码是 %s。\n回到客厅，输入键盘。" % code, 3.0, func():
		_hud.show_narrative("")
		_keypad.show_for_code(code)
	)


# ============================================================
# 解锁 → 逃脱
# ============================================================

func on_keypad_unlocked() -> void:
	_hud.update_layer(2)
	_hud.update_info("去卧室! 光照门锁按 Enter")
	_narrate("绿灯亮了。卧室传来门锁弹开的声音——", 2.0, func():
		_hud.show_narrative("")
		_door.activate(_spotlight)
	)


func _on_escaped() -> void:
	_mode.escape()
	var score := _mode.get_score()
	var rating := _mode.get_rating()
	var all_clues := ""
	for c in _clues_found:
		all_clues += c + "\n"
	_narrate("门开了。你看到了镜子里的自己。\n" + all_clues + "\n「你终于走到这一步。」\n「记住——谜题从来不在房间里。」\n「而是在你心里。」", 5.0, func():
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
	if _story_phase < 1: return
	if _mode.current_layer == EscapeMode.Layer.DONE: return

	if not _keyboard_focus:
		_spotlight.focus_ratio = BCIConnector.latest_focus_ratio
	_mode.elapsed_time += delta
	_mode.track_focus(_spotlight.focus_ratio)
	_hud.update_timer(_mode.elapsed_time)
	_hud.update_focus(_spotlight.focus_ratio)

	_room_cooldown = maxf(0.0, _room_cooldown - delta)
	if _room_cooldown <= 0.0:
		var t := _rooms.check_door_transition(_spotlight.position, _spotlight.get_radius())
		if t >= 0:
			_room_cooldown = 0.5
			_spotlight.position = _rooms.transition_to(t)

	# 食谱自动读取
	if not _recipe.solved and _rooms.current_room == RoomManager.Room.KITCHEN and _spotlight:
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
		if event.is_action_pressed("ui_accept"): _restart()
		elif event.is_action_pressed("ui_cancel"): ParadigmManager.go_to_main_menu()
		return
	if event.is_action_pressed("ui_cancel"): ParadigmManager.go_to_main_menu()
	if _mode.current_layer == EscapeMode.Layer.ESCAPE:
		if event.is_action_pressed("ui_accept"): _door.try_escape()
	if event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_1: _spotlight.focus_ratio = 0.8; _keyboard_focus = true
			KEY_2: _spotlight.focus_ratio = 2.0; _keyboard_focus = true
			KEY_3: _spotlight.focus_ratio = 3.2; _keyboard_focus = true


func _restart() -> void:
	for child in get_children():
		if child.name != "Background": child.queue_free()
	_keyboard_focus = false; _story_phase = 0; _solved_count = 0
	_code_digits = [0, 0, 0, 0]; _clues_found.clear()
	await get_tree().process_frame; _on_paradigm_start()
