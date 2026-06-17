extends BaseParadigm
## SpaceMinerParadigm — 太空采矿 (P300)

var _sm: MinerStateMachine
var _mode: SpaceMinerMode
var _field: AsteroidField
var _hud: SpaceMinerHUD
var _last_result: Dictionary = {}


func _ready() -> void:
	paradigm_type = GlobalConfig.ParadigmType.P300
	super._ready()


func _on_paradigm_start() -> void:
	_setup_background()
	_setup_game()
	_mode.start_new()


func _on_paradigm_end() -> void:
	print("[太空采矿] 总分: %d" % _mode.total_score)


func _on_bci_data(_data: Dictionary) -> void:
	pass


func _setup_background() -> void:
	var bg := ColorRect.new()
	bg.name = "Background"
	bg.color = Color("1A1A2E")  # 深空背景
	bg.size = Vector2(GlobalConfig.GAME_WIDTH, GlobalConfig.GAME_HEIGHT)
	bg.position = Vector2.ZERO
	add_child(bg)
	move_child(bg, 0)

	# 星星
	for i in range(40):
		var star := ColorRect.new()
		star.color = Color.WHITE
		star.color.a = randf_range(0.3, 0.8)
		var sz := randf_range(1.0, 3.0)
		star.size = Vector2(sz, sz)
		star.position = Vector2(randf_range(0, GlobalConfig.GAME_WIDTH), randf_range(0, GlobalConfig.GAME_HEIGHT))
		add_child(star)


func _setup_game() -> void:
	_field = AsteroidField.new()
	_field.name = "AsteroidField"
	add_child(_field)

	_sm = MinerStateMachine.new()
	_sm.name = "StateMachine"
	add_child(_sm)

	_mode = SpaceMinerMode.new()

	_hud = SpaceMinerHUD.new()
	_hud.name = "HUD"
	_hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_hud)

	_sm.scan_started.connect(_on_scan)
	_sm.flying_started.connect(_on_fly)
	_sm.collected.connect(_on_collect)
	_sm.finished.connect(_on_finished)
	_field.scan_finished.connect(_on_scan_done)
	_field.collect_finished.connect(_on_collect_done)

	_sm.enter_scan()


# --- 状态 ---

func _on_scan() -> void:
	if _mode.is_game_over():
		_sm.go_game_over()
		return
	_hud.update_state("注视想采集的矿石...")
	_hud.update_round(_mode.current_round + 1)
	_field.start_scan()


func _on_scan_done() -> void:
	var idx := _field.get_guessed()
	_sm.trigger_fly(idx)


func _on_fly(idx: int) -> void:
	_hud.update_state("飞船前往采集...")
	_field.fly_ship_to(idx)


func _on_collect_done(idx: int) -> void:
	_last_result = _field.collect_asteroid(idx)
	_sm.trigger_collect(_last_result.get("name", ""), _last_result.get("value", 0))


func _on_collect(ore_name: String, value: int) -> void:
	var result := _mode.collect(value)
	_hud.update_state("采集到 %s! +%d pts" % [ore_name, value])
	_hud.update_score(result.total)
	AudioManager.play_combo(1)
	# 短暂延迟后下一轮
	get_tree().create_timer(1.5).timeout.connect(func():
		_field.reset_ship()
		_sm.enter_scan()
	)


func _on_finished() -> void:
	var s := _mode.get_summary()
	_hud.show_final(s.total_score, s.collected, s.rating)


# --- 键盘 ---

func _input(event: InputEvent) -> void:
	if _sm.current_state == MinerStateMachine.State.GAME_OVER:
		if event.is_action_pressed("ui_accept"):
			_restart()
		elif event.is_action_pressed("ui_cancel"):
			ParadigmManager.go_to_main_menu()
		return

	if event.is_action_pressed("ui_cancel"):
		ParadigmManager.go_to_main_menu()


func _restart() -> void:
	for child in get_children():
		if child.name != "Background":
			child.queue_free()
	await get_tree().process_frame
	_on_paradigm_start()
