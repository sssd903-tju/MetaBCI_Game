extends BaseParadigm
## MindCardParadigm — 卡牌读心 (P300)

var _sm: CardStateMachine
var _mode: MindCardMode
var _grid: CardGrid
var _hud: MindCardHUD
var _target_idx: int = -1
var _guessed_idx: int = -1


func _ready() -> void:
	paradigm_type = GlobalConfig.ParadigmType.P300
	super._ready()


func _on_paradigm_start() -> void:
	_setup_background()
	_setup_game()
	_mode.start_new()


func _on_paradigm_end() -> void:
	print("[卡牌读心] 分数: %d" % _mode.total_score)


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
	_sm.confirm_started.connect(_on_confirm)
	_sm.answered_correct.connect(_on_correct)
	_sm.answered_wrong.connect(_on_wrong)
	_sm.finished.connect(_on_finished)
	_grid.scan_finished.connect(_on_scan_done)


# --- 状态 ---

func _on_think() -> void:
	if _mode.is_game_over():
		_sm.go_game_over()
		return
	_target_idx = -1
	_grid.hide_all()
	_hud.update_state("记住一张牌, 按 空格 开始")
	_hud.update_round(_mode.current_round + 1)
	_hud.hide_result()
	# 展示牌面
	_grid.reveal_all()


func _on_scan() -> void:
	_hud.update_state("正在扫描脑电波... 保持注视!")
	_grid.hide_all()
	_grid.start_scan()


func _on_scan_done() -> void:
	_guessed_idx = _grid.get_guessed()
	_sm.trigger_reveal(_guessed_idx)


func _on_reveal(idx: int) -> void:
	# 放大猜测的牌
	_grid.reveal_all()
	_grid.enlarge_card(idx)
	var sym: String = CardGrid.SYMBOLS[idx]
	_hud.update_state("系统猜测: %s" % sym)


func _on_confirm(idx: int) -> void:
	_hud.update_state("猜对了吗? Y=是 / N=否")
	_hud.show_confirm()


func _on_correct() -> void:
	var result := _mode.record(true)
	_hud.update_score(result.score)
	_hud.update_state("太棒了! 读心成功 ✓")
	AudioManager.play_combo(1)


func _on_wrong() -> void:
	var result := _mode.record(false)
	_hud.update_score(result.score)
	_hud.update_state("猜错了... ✗")
	AudioManager.play_miss()


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
			if event.keycode == KEY_SPACE:
				_sm.enter_scan()

		elif _sm.current_state == CardStateMachine.State.CONFIRM:
			match event.keycode:
				KEY_Y: _sm.answer(true)
				KEY_N: _sm.answer(false)


func _restart() -> void:
	for child in get_children():
		if child.name != "Background":
			child.queue_free()
	await get_tree().process_frame
	_on_paradigm_start()
