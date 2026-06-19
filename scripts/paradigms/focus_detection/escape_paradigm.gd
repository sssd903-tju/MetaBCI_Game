extends BaseParadigm
## EscapeParadigm — 密室逃脱: 门锁谜题 + 线索谜题

var _spotlight: Spotlight
var _rooms: RoomManager
var _keypad: EscapeKeypad
var _door: ExitDoor
var _mode: EscapeMode
var _hud: EscapeHUD
var _safe: SafePuzzle
var _bookshelf: BookshelfPuzzle
var _recipe: RecipePuzzle

# 门锁小谜题
var _door_locks: Array[DoorLock] = []

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
	_story_phase = 0; _solved_count = 0
	_code_digits = [0, 0, 0, 0]
	_room_cooldown = 0.0; _keyboard_focus = false
	_clues_found.clear(); _door_locks.clear()
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
	_narrate("你在黑暗中醒来。什么都看不见。", 2.0, func():
		_narrate("等等——你的手中握着一张字条:", 1.5, func():
			_narrate("「欢迎，访客。」\n「每个房间的门都锁着。」\n「找到门锁，用光照亮它——」\n「光会打开通往下一个房间的路。」\n「每个房间还藏着一个数字。」\n「集齐它们，输入客厅的键盘。」\n「卧室的门会打开。你会记起一切。」\n—— X", 6.0, func():
				_story_phase = 1
				_hud.update_layer(0)
				_hud.update_info("先找到门锁→照亮它!  谜题:0/3  线索:0/3")
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

	# ---- 门锁小谜题 (每个需要解锁的门) ----
	_add_door_lock(Vector2(GlobalConfig.GAME_WIDTH - 160, GlobalConfig.GAME_HEIGHT/2 - 30),
		"书房", "living_study", RoomManager.Room.LIVING, "照亮门锁→打开书房")
	_add_door_lock(Vector2(GlobalConfig.GAME_WIDTH/2 - 70, GlobalConfig.GAME_HEIGHT - 70),
		"厨房", "living_kitchen", RoomManager.Room.LIVING, "照亮门锁→打开厨房")
	_add_door_lock(Vector2(GlobalConfig.GAME_WIDTH/2 - 70, GlobalConfig.GAME_HEIGHT - 70),
		"卧室", "study_bedroom", RoomManager.Room.STUDY, "照亮门锁→打开卧室")
	_add_door_lock(Vector2(GlobalConfig.GAME_WIDTH - 160, GlobalConfig.GAME_HEIGHT/2 - 30),
		"卧室", "kitchen_bedroom", RoomManager.Room.KITCHEN, "照亮门锁→打开卧室")

	# ---- 线索谜题 ----
	_safe = SafePuzzle.new()
	_safe.position = Vector2(GlobalConfig.GAME_WIDTH * 0.2, GlobalConfig.GAME_HEIGHT * 0.55)
	_safe.setup(4, 7, _spotlight)
	add_child(_safe)

	_bookshelf = BookshelfPuzzle.new()
	_bookshelf.position = Vector2(GlobalConfig.GAME_WIDTH * 0.55, GlobalConfig.GAME_HEIGHT * 0.35)
	_bookshelf.setup(_spotlight)
	add_child(_bookshelf)

	_recipe = RecipePuzzle.new()
	_recipe.position = Vector2(GlobalConfig.GAME_WIDTH * 0.35, GlobalConfig.GAME_HEIGHT * 0.3)
	_recipe.setup(_spotlight)
	add_child(_recipe)

	_keypad = EscapeKeypad.new()
	_keypad.set_spotlight(_spotlight)
	_keypad.position = Vector2(GlobalConfig.GAME_WIDTH * 0.2, GlobalConfig.GAME_HEIGHT * 0.15)
	add_child(_keypad)

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


func _add_door_lock(pos: Vector2, label: String, key: String, room: int, _hint: String) -> void:
	var dl := DoorLock.new()
	dl.position = pos
	dl.setup(label, key, _spotlight)
	dl.visible = false
	add_child(dl)
	_door_locks.append({"node": dl, "room": room})


func _update_visibility() -> void:
	var cr := _rooms.current_room
	_safe.visible = (cr == RoomManager.Room.LIVING)
	_bookshelf.visible = (cr == RoomManager.Room.STUDY)
	_recipe.visible = (cr == RoomManager.Room.KITCHEN)
	_keypad.visible = (cr == RoomManager.Room.LIVING)
	_door.visible = (cr == RoomManager.Room.BEDROOM)

	for entry: Dictionary in _door_locks:
		var d: DoorLock = entry.node
		d.visible = (entry.room == cr and not d.unlocked)


func _on_room_changed(_from: int, to: int) -> void:
	_update_visibility()
	var rn := _rooms.get_room_name(to)
	_hud.show_narrative("—— %s ——" % rn)
	get_tree().create_timer(1.0).timeout.connect(func():
		if _story_phase >= 1: _hud.show_narrative("")
	)


# ============================================================
# 门锁回调
# ============================================================

func on_door_unlocked(key: String) -> void:
	_rooms.unlock_door(key)
	_hud.show_narrative("门开了!")
	get_tree().create_timer(1.5).timeout.connect(func():
		if _story_phase >= 1: _hud.show_narrative("")
	)
	_update_visibility()


# ============================================================
# 线索谜题回调
# ============================================================

func on_safe_solved() -> void:
	_code_digits[0] = _safe.digit1
	_code_digits[1] = _safe.digit2
	_add_clue("客厅线索: 「她的名字里有四个数字」")
	_puzzle_solved("保险箱划痕: %d 和 %d" % [_safe.digit1, _safe.digit2])

func on_bookshelf_solved() -> void:
	_code_digits[2] = _bookshelf.missing_digit
	_add_clue("书房线索: 「其中藏着命运的密码」")
	_puzzle_solved("缺失编号: %d" % _bookshelf.missing_digit)

func _on_recipe_read() -> void:
	if _recipe.solved: return
	_recipe.mark_solved()
	_code_digits[3] = _recipe.digit1
	_add_clue("厨房线索: 「四重锁，四段记忆」")
	_puzzle_solved("食谱主料: %dg" % _recipe.digit1)


func _add_clue(clue: String) -> void:
	if clue not in _clues_found:
		_clues_found.append(clue)


func _puzzle_solved(msg: String) -> void:
	_solved_count += 1
	_hud.show_narrative(msg)
	AudioManager.play_hit(8)
	var progress := ""
	for i in range(4):
		progress += str(_code_digits[i]) if _code_digits[i] > 0 else "_"
	_hud.update_info("谜题:%d/3  线索:%d/3  密码:%s" % [_solved_count, _clues_found.size(), progress])
	get_tree().create_timer(2.0).timeout.connect(func():
		_hud.show_narrative("")
		if _solved_count >= 3: _ready_to_escape()
	)


func _ready_to_escape() -> void:
	var code := ""
	for d in _code_digits: code += str(d)
	_mode.code = code
	_hud.update_layer(1)
	_hud.update_info("密码: %s  回客厅输入!" % code)
	_narrate("密码已完整: %s。回客厅吧。" % code, 2.5, func():
		_hud.show_narrative("")
		_keypad.show_for_code(code)
	)


# ============================================================
# 逃脱
# ============================================================

func on_keypad_unlocked() -> void:
	_hud.update_layer(2)
	_hud.update_info("去卧室! 光照门锁按 Enter")
	_narrate("绿灯。远处传来门锁弹开的声音。", 2.0, func():
		_hud.show_narrative("")
		_door.activate(_spotlight)
	)


func _on_escaped() -> void:
	_mode.escape(); var score := _mode.get_score(); var rating := _mode.get_rating()
	var all := ""
	for c in _clues_found: all += c + "\n"
	_narrate("门开了。光涌进来。\n\n" + all + "\n你终于想起来了——\n谜题从来不在房间里。\n它们是你自己锁住的记忆。", 5.0, func():
		_hud.update_layer(3); _hud.show_escaped(score, rating); _hud.show_narrative("")
	)
	_spotlight.focus_ratio = 0; AudioManager.play_hit(10)


# ============================================================
# 主循环 / 键盘
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

	if not _recipe.solved and _rooms.current_room == RoomManager.Room.KITCHEN and _spotlight:
		var rc := _recipe.global_position + _recipe.size / 2.0
		if rc.distance_to(_spotlight.global_position) < _spotlight.get_radius() * 0.5:
			_recipe._focus_time += delta
			if _recipe._focus_time >= 2.0: _on_recipe_read()


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
	_code_digits = [0, 0, 0, 0]; _clues_found.clear(); _door_locks.clear()
	await get_tree().process_frame; _on_paradigm_start()
