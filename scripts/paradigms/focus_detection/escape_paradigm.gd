extends BaseParadigm
## EscapeParadigm — 全屏房间 密室逃脱

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
var _target_room: String = "客厅"
var _room_transition_cooldown: float = 0.0
var _keyboard_focus: bool = false

# 谜题可见性控制
var _safe_room: int = -1
var _bookshelf_room: int = -1
var _recipe_room: int = -1
var _keypad_room: int = -1
var _door_room: int = -1


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
	_room_transition_cooldown = 0.0
	_keyboard_focus = false
	_target_room = "客厅"
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
	_narrate("你睁开眼。陌生的天花板。", 2.0, func():
		_narrate("头痛欲裂。什么也想不起来。", 2.0, func():
			_narrate("手中攥着一张字条:\n「失忆的访客，你好。」\n「你的记忆锁在这间密室里。」\n「每个房间藏着一个数字。集齐四个。」\n「然后找到键盘，输入密码。」\n「门会开，你会记起一切。」\n—— X", 5.0, func():
				_story_phase = 1
				_hud.update_layer(0)
				_hud.update_info("探索房间  谜题: 0/3   → %s" % _target_room)
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

	# 保险箱 → 客厅
	_safe = SafePuzzle.new()
	_safe.name = "Safe"
	_safe.position = Vector2(GlobalConfig.GAME_WIDTH * 0.3 - 100, GlobalConfig.GAME_HEIGHT * 0.6 - 100)
	_safe.setup(4, 7, _spotlight)
	add_child(_safe)
	_safe_room = RoomManager.Room.LIVING

	# 书架 → 书房
	_bookshelf = BookshelfPuzzle.new()
	_bookshelf.name = "Bookshelf"
	_bookshelf.position = Vector2(GlobalConfig.GAME_WIDTH * 0.55, GlobalConfig.GAME_HEIGHT * 0.45)
	_bookshelf.setup(_spotlight)
	add_child(_bookshelf)
	_bookshelf_room = RoomManager.Room.STUDY

	# 食谱 → 厨房
	_recipe = RecipePuzzle.new()
	_recipe.name = "Recipe"
	_recipe.position = Vector2(GlobalConfig.GAME_WIDTH * 0.4, GlobalConfig.GAME_HEIGHT * 0.3)
	_recipe.setup(_spotlight)
	add_child(_recipe)
	_recipe_room = RoomManager.Room.KITCHEN

	# 键盘 → 客厅
	_keypad = EscapeKeypad.new()
	_keypad.name = "Keypad"
	_keypad.set_spotlight(_spotlight)
	_keypad.position = Vector2(GlobalConfig.GAME_WIDTH * 0.3 - 150, GlobalConfig.GAME_HEIGHT * 0.3 - 200)
	add_child(_keypad)
	_keypad_room = RoomManager.Room.LIVING

	# 出口 → 卧室
	_door = ExitDoor.new()
	_door.name = "ExitDoor"
	_door.door_escaped.connect(_on_escaped)
	_door.position = Vector2(GlobalConfig.GAME_WIDTH - 240, (GlobalConfig.GAME_HEIGHT - 300) / 2.0)
	add_child(_door)
	_door_room = RoomManager.Room.BEDROOM

	_mode = EscapeMode.new()
	_hud = EscapeHUD.new()
	_hud.name = "HUD"
	_hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_hud)
	_hud.show_narrative("")

	_update_puzzle_visibility()


func _update_puzzle_visibility() -> void:
	var cr := _rooms.current_room
	_safe.visible = (cr == _safe_room)
	_bookshelf.visible = (cr == _bookshelf_room)
	_recipe.visible = (cr == _recipe_room)
	_keypad.visible = (cr == _keypad_room)
	_door.visible = (cr == _door_room)


func _on_room_changed(_from: int, to: int) -> void:
	_update_puzzle_visibility()
	var rname := _rooms.get_room_name(to)
	_hud.show_narrative("—— %s ——" % rname)
	get_tree().create_timer(1.0).timeout.connect(func(): _hud.show_narrative(""))


# ============================================================
# 谜题回调
# ============================================================

func on_safe_solved() -> void:
	_code_digits[0] = _safe.digit1
	_code_digits[1] = _safe.digit2
	_target_room = "书房"
	_on_puzzle_solved("划痕显示: %d 和 %d\n去书房——纸条背面有线索" % [_safe.digit1, _safe.digit2])


func on_bookshelf_solved() -> void:
	_code_digits[2] = _bookshelf.missing_digit
	_target_room = "厨房"
	_on_puzzle_solved("缺失的编号是 %d\n书架底层刻着:答案在厨房" % _bookshelf.missing_digit)


func _on_recipe_read() -> void:
	if _recipe.solved:
		return
	_recipe.mark_solved()
	_code_digits[3] = _recipe.digit1
	_target_room = "客厅"
	_on_puzzle_solved("食谱主料: %dg\n三个谜题已破，回客厅!" % _recipe.digit1)


func _on_puzzle_solved(msg: String) -> void:
	_solved_count += 1
	_hud.show_narrative(msg)
	AudioManager.play_hit(8)

	var progress := ""
	for i in range(4):
		progress += str(_code_digits[i]) if _code_digits[i] > 0 else "_"
	_hud.update_info("密码: %s  谜题: %d/3   → %s" % [progress, _solved_count, _target_room])

	get_tree().create_timer(2.5).timeout.connect(func():
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
	_hud.update_info("密码: %s" % code)
	_mode.code = code
	_target_room = "客厅"
	_narrate("三个谜题已破。密码是 %s。\n回客厅输入键盘。" % code, 3.0, func():
		_hud.show_narrative("")
		_keypad.show_for_code(code)
	)


# ============================================================
# 解锁 → 逃脱
# ============================================================

func on_keypad_unlocked() -> void:
	_target_room = "卧室"
	_hud.update_layer(2)
	_hud.update_info("去卧室 → 光照门锁按 Enter")
	_narrate("键盘亮了绿灯。卧室的门锁——\n你听到了清脆的咔嗒声。", 2.5, func():
		_hud.show_narrative("")
		_door.activate(_spotlight)
	)


func _on_escaped() -> void:
	_mode.escape()
	var score := _mode.get_score()
	var rating := _mode.get_rating()
	_narrate("门开了。光涌进来。\n记忆如潮水——你不是别人。\n你就是X。这一切都是你为自己设下的试炼。", 4.5, func():
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

	# 房间过渡冷却
	_room_transition_cooldown = maxf(0.0, _room_transition_cooldown - delta)

	# 检查门洞过渡
	if _room_transition_cooldown <= 0.0:
		var target := _rooms.check_door_transition(_spotlight.position, _spotlight.get_radius())
		if target >= 0:
			_room_transition_cooldown = 0.5
			_spotlight.position = _rooms.transition_to(target)

	# 食谱自动读取
	if not _recipe.solved and _rooms.current_room == _recipe_room and _spotlight:
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
	_target_room = "客厅"
	await get_tree().process_frame
	_on_paradigm_start()
