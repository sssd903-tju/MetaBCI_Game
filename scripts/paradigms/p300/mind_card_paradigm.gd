extends BaseParadigm
## MindCardParadigm — 卡牌读心 (P300)

var _sm: CardStateMachine
var _mode: MindCardMode
var _grid: CardGrid
var _hud: MindCardHUD
var _target_idx: int = -1
var _guessed_idx: int = -1
var _last_correct: bool = false


func _ready() -> void:
	paradigm_type = GlobalConfig.ParadigmType.P300
	super._ready()


func _on_paradigm_start() -> void:
	_setup_background()
	_setup_game()
	_mode.start_new()


func _on_paradigm_end() -> void:
	print("[卡牌读心] 结束, 分数: %d" % _mode.total_score)


func _on_bci_data(_data: Dictionary) -> void:
	pass


# --- 场景 ---

func _setup_background() -> void:
	var bg := ColorRect.new()
	bg.name = "Background"
	bg.color = GlobalConfig.BG_WARM_CREAM
	bg.size = Vector2(GlobalConfig.GAME_WIDTH, GlobalConfig.GAME_HEIGHT)
	bg.position = Vector2.ZERO
	add_child(bg)
	move_child(bg, 0)


func _setup_game() -> void:
	_grid = CardGrid.new()
	_grid.name = "CardGrid"
	add_child(_grid)

	_sm = CardStateMachine.new()
	_sm.name = "StateMachine"
	add_child(_sm)

	_mode = MindCardMode.new()

	_hud = MindCardHUD.new()
	_hud.name = "HUD"
	_hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_hud)

	_sm.think_started.connect(_on_think)
	_sm.scan_started.connect(_on_scan)
	_sm.reveal_started.connect(_on_reveal)
	_sm.correct.connect(_on_correct)
	_sm.wrong.connect(_on_wrong)
	_sm.finished.connect(_on_finished)
	_grid.scan_finished.connect(_on_scan_done)


# --- 状态 ---

func _on_think() -> void:
	if _mode.is_game_over():
		_sm.go_game_over()
		return
	_target_idx = -1
	_grid.hide_all()
	_hud.update_state("在心里想一张牌...")
	_hud.update_round(_mode.current_round + 1)


func _on_scan() -> void:
	_hud.update_state("正在扫描你的脑电波...")
	_grid.start_scan()


func _on_scan_done() -> void:
	_guessed_idx = _grid.get_guessed()
	_sm.trigger_reveal(_guessed_idx)


func _on_reveal(idx: int) -> void:
	var sym := CardGrid.SYMBOLS[idx]
	_grid.reveal_all()
	var correct := (idx == _target_idx)
	_last_correct = correct

	if _target_idx >= 0:
		_hud.show_result(sym, correct)
	else:
		_hud.show_result(sym, false)  # 未选目标, 默认错
		_last_correct = false

	var result := _mode.record(_last_correct)
	_hud.update_score(result.score)

	if _last_correct:
		AudioManager.play_combo(1)
	else:
		AudioManager.play_miss()


func _on_correct() -> void:
	pass


func _on_wrong() -> void:
	pass


func _on_finished() -> void:
	var s := _mode.get_summary()
	_hud.show_final(s.total_score, s.correct, s.wrong, s.rating)


# --- 键盘 ---

func _input(event: InputEvent) -> void:
	if _sm.current_state == CardStateMachine.State.GAME_OVER:
		if event.is_action_pressed("ui_accept"):
			_restart()
		elif event.is_action_pressed("ui_cancel"):
			ParadigmManager.go_to_main_menu()
		return

	if event.is_action_pressed("ui_cancel"):
		ParadigmManager.go_to_main_menu()

	if event is InputEventKey and event.pressed:
		if _sm.current_state == CardStateMachine.State.THINK:
			match event.keycode:
				KEY_1: _target_idx = 0
				KEY_2: _target_idx = 1
				KEY_3: _target_idx = 2
				KEY_4: _target_idx = 3
				KEY_5: _target_idx = 4
				KEY_6: _target_idx = 5
			if _target_idx >= 0:
				_grid.set_target(_target_idx)
				_hud.update_state("已选: %s" % CardGrid.SYMBOLS[_target_idx])


func _restart() -> void:
	for child in get_children():
		if child.name != "Background":
			child.queue_free()
	await get_tree().process_frame
	_on_paradigm_start()
