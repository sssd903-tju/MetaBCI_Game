extends BaseParadigm
## EscapeParadigm — 专注之光密室逃脱

var _spotlight: Spotlight
var _digits: Array[HiddenDigit] = []
var _mode: EscapeMode
var _hud: EscapeHUD
var _escaped: bool = false
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
	var ratio: float = data.get("ratio", 1.5)
	_spotlight.focus_ratio = ratio


# --- 场景 ---

func _setup_room() -> void:
	# 暗室背景
	var bg := ColorRect.new()
	bg.name = "Background"
	bg.color = Color("0A0A0A")
	bg.size = Vector2(GlobalConfig.GAME_WIDTH, GlobalConfig.GAME_HEIGHT)
	bg.position = Vector2.ZERO
	add_child(bg)
	move_child(bg, 0)

	# 房间轮廓 (微弱可见)
	var wall_hint := ColorRect.new()
	wall_hint.color = Color("1A1A1A")
	wall_hint.size = Vector2(GlobalConfig.GAME_WIDTH - 40, GlobalConfig.GAME_HEIGHT - 40)
	wall_hint.position = Vector2(20, 20)
	add_child(wall_hint)

	# 地板纹理提示 (微弱线条)
	for i in range(1, 5):
		var line := ColorRect.new()
		line.color = Color("1A1A1A")
		line.size = Vector2(GlobalConfig.GAME_WIDTH - 40, 1)
		line.position = Vector2(20, i * GlobalConfig.GAME_HEIGHT / 5.0)
		add_child(line)


func _setup_game() -> void:
	_spotlight = Spotlight.new()
	_spotlight.name = "Spotlight"
	add_child(_spotlight)

	# 生成 4 个隐藏数字
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

	_mode = EscapeMode.new()

	_hud = EscapeHUD.new()
	_hud.name = "HUD"
	_hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_hud)


# --- 回调 ---

func on_digit_found(index: int) -> void:
	if _escaped:
		return
	var all_found := _mode.digit_found()
	_hud.update_digits(_mode.found_count, _mode.total_digits)
	AudioManager.play_combo(1)

	if all_found:
		_escaped = true
		var score := _mode.get_score()
		var rating := _mode.get_rating()
		_hud.show_escaped(score, rating)
		_spotlight.focus_ratio = 0  # 灯灭
		AudioManager.play_hit(10)


# --- 主循环 ---

func _process(delta: float) -> void:
	if not _escaped:
		if not _keyboard_focus:
			_spotlight.focus_ratio = BCIConnector.latest_focus_ratio
		_mode.elapsed_time += delta
		_mode.track_focus(_spotlight.focus_ratio)
		_hud.update_timer(_mode.elapsed_time)
		_hud.update_focus(_spotlight.focus_ratio)


# --- 键盘 ---

func _input(event: InputEvent) -> void:
	if _escaped:
		if event.is_action_pressed("ui_accept"):
			_restart()
		elif event.is_action_pressed("ui_cancel"):
			ParadigmManager.go_to_main_menu()
		return

	if event.is_action_pressed("ui_cancel"):
		ParadigmManager.go_to_main_menu()

	# 调试专注度
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
	_escaped = false
	_keyboard_focus = false
	await get_tree().process_frame
	_on_paradigm_start()
