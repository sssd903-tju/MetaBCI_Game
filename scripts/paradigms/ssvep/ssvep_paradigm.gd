extends BaseParadigm
## SSVEPParadigm — SSVEP 范式入口 (打地鼠)

var _sm: WhackMoleStateMachine
var _mode: WhackMoleMode
var _grid: MoleGrid
var _hud: WhackMoleHUD

# 模拟 SSVEP 解码 — 键盘选洞
var _selected_hole: int = -1


func _ready() -> void:
	paradigm_type = GlobalConfig.ParadigmType.SSVEP
	super._ready()


func _on_paradigm_start() -> void:
	_setup_background()
	_setup_game()
	_mode.start_new_game()
	_update_hud()


func _on_paradigm_end() -> void:
	print("[打地鼠] 结束，总分: %d" % _mode.total_score)


func _on_bci_data(_data: Dictionary) -> void:
	# SSVEP 解码结果: data["frequency"] 或 data["target_index"]
	var freq: float = _data.get("frequency", 0.0)
	if freq > 0.0:
		_selected_hole = _grid.match_frequency(freq)


# --- 场景构建 ---

func _setup_background() -> void:
	var bg := ColorRect.new()
	bg.name = "Background"
	bg.color = GlobalConfig.BG_WARM_CREAM
	bg.size = Vector2(GlobalConfig.GAME_WIDTH, GlobalConfig.GAME_HEIGHT)
	bg.position = Vector2.ZERO
	add_child(bg)
	move_child(bg, 0)


func _setup_game() -> void:
	_grid = MoleGrid.new()
	_grid.name = "MoleGrid"
	add_child(_grid)

	_sm = WhackMoleStateMachine.new()
	_sm.name = "StateMachine"
	add_child(_sm)

	_mode = WhackMoleMode.new()

	_hud = WhackMoleHUD.new()
	_hud.name = "HUD"
	_hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_hud)

	# 信号
	_sm.state_changed.connect(_on_state_changed)
	_sm.mole_shown.connect(_on_mole_shown)
	_sm.decode_started.connect(_on_decode_start)
	_sm.hit_detected.connect(_on_hit)
	_sm.miss_detected.connect(_on_miss)
	_sm.finished.connect(_on_finished)


# --- 状态回调 ---

func _on_state_changed(_old: WhackMoleStateMachine.State, _new: WhackMoleStateMachine.State) -> void:
	pass


func _on_mole_shown(_hole_index: int) -> void:
	var idx := _grid.spawn_mole()
	_selected_hole = -1
	_hud.update_state("地鼠出现！盯着闪烁的洞口")
	_hud.hide_result()


func _on_decode_start() -> void:
	_hud.update_state("解码中 — 保持注视...")
	_hud.show_timer(true)


func _on_hit(hole_index: int) -> void:
	var result := _mode.record_hit()
	_hud.show_result("命中！ +%d" % result.points, GlobalConfig.UI_SUCCESS)
	_hud.update_combo(result.combo)
	_update_hud()
	AudioManager.play_hit(8)  # 复用命中音效


func _on_miss() -> void:
	var result := _mode.record_miss()
	_hud.show_result("脱靶... ", GlobalConfig.UI_DANGER)
	_hud.update_combo(0)
	_update_hud()
	AudioManager.play_miss()


func _on_finished(_s: int) -> void:
	var summary := _mode.get_summary()
	_hud.show_final(summary.total_score, summary.hits, summary.misses, summary.best_combo, summary.rating)


func _update_hud() -> void:
	_hud.update_round(_mode.current_round + 1)
	_hud.update_score(_mode.total_score)


# --- 主循环 ---

func _process(_delta: float) -> void:
	if _sm.current_state == WhackMoleStateMachine.State.DECODE:
		_hud.update_timer(_sm.get_decode_progress())

		# 模拟 SSVEP 解码: 键盘或随机
		if _sm._state_timer <= 0.5:  # 解码窗口末段触发射击
			_resolve_shot()


func _check_game_over() -> void:
	if _mode.is_game_over():
		_sm.change_state(WhackMoleStateMachine.State.FINISHED)
		_sm.finished.emit(0)


func _resolve_shot() -> void:
	# 键盘选择优先，否则随机（模拟SSVEP解码）
	var detected := _selected_hole
	if detected < 0:
		# 随机模拟：70% 概率命中，30% 脱靶/错洞
		if randf() < 0.7:
			detected = _grid.active_hole_index
		else:
			detected = randi() % 4

	if detected == _grid.active_hole_index:
		_sm.trigger_hit(detected)
	else:
		_sm.trigger_miss()

	_grid.hide_current_mole()
	_check_game_over()


# --- 键盘输入 ---

func _input(event: InputEvent) -> void:
	if _sm.current_state == WhackMoleStateMachine.State.FINISHED:
		if event.is_action_pressed("ui_accept"):
			_restart()
		elif event.is_action_pressed("ui_cancel"):
			ParadigmManager.go_to_main_menu()
		return

	if event.is_action_pressed("ui_cancel"):
		ParadigmManager.go_to_main_menu()

	# 键盘模拟 SSVEP 选择
	if _sm.current_state == WhackMoleStateMachine.State.DECODE:
		if event is InputEventKey and event.pressed:
			match event.keycode:
				KEY_1: _selected_hole = 0
				KEY_2: _selected_hole = 1
				KEY_3: _selected_hole = 2
				KEY_4: _selected_hole = 3


func _restart() -> void:
	for child in get_children():
		if child.name != "Background":
			child.queue_free()
	await get_tree().process_frame
	_on_paradigm_start()
