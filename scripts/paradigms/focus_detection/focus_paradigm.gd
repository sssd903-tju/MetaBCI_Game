extends BaseParadigm
## FocusParadigm — 专注度检测范式入口
##
## 管理: 状态机 + 模式 + 靶子 + 准星 + HUD

# 场景组件
var _sm: ArcheryStateMachine
var _mode: ArcheryMode
var _target: ArcheryTarget
var _crosshair: ArcheryCrosshair
var _hud: ArcheryHUD

# 当前专注度
var _current_focus := 1.5
var _peek_focus := 1.5  # 射箭时刻的专注度
var _last_result: Dictionary = {}  # 最近一次射箭结果


func _ready() -> void:
	paradigm_type = GlobalConfig.ParadigmType.FOCUS_DETECTION
	super._ready()


func _on_paradigm_start() -> void:
	_setup_background()
	_setup_game()
	_mode.start_new_game()
	_sm._enter_ready()


func _on_paradigm_end() -> void:
	print("[凝神一矢] 结束，总分: %d" % _mode.total_score)


func _on_bci_data(data: Dictionary) -> void:
	_current_focus = data.get("ratio", 1.5)
	_crosshair.focus_ratio = _current_focus
	_hud.update_focus(_current_focus)


# --- 场景构建 ---

func _setup_background() -> void:
	var bg := ColorRect.new()
	bg.name = "Background"
	bg.color = GlobalConfig.BG_WARM_CREAM
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	move_child(bg, 0)


func _setup_game() -> void:
	# 靶子 — 屏幕中央
	_target = ArcheryTarget.new()
	_target.name = "Target"
	_target.position = Vector2(GlobalConfig.GAME_WIDTH / 2.0, GlobalConfig.GAME_HEIGHT / 2.0 + 60)
	add_child(_target)

	# 准星
	_crosshair = ArcheryCrosshair.new()
	_crosshair.name = "Crosshair"
	add_child(_crosshair)

	# 状态机
	_sm = ArcheryStateMachine.new()
	_sm.name = "StateMachine"
	add_child(_sm)

	# 计分模式
	_mode = ArcheryMode.new()

	# HUD
	_hud = ArcheryHUD.new()
	_hud.name = "HUD"
	_hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_hud)

	# 连接状态机信号
	_sm.state_changed.connect(_on_state_changed)
	_sm.ready_started.connect(_on_ready)
	_sm.aiming_started.connect(_on_aiming_start)
	_sm.fired.connect(_on_fired)
	_sm.scoring_started.connect(_on_scoring)
	_sm.finished.connect(_on_finished)


# --- 状态回调 ---

func _on_state_changed(_old: ArcheryStateMachine.State, new: ArcheryStateMachine.State) -> void:
	print("[凝神一矢] 状态: ", ArcheryStateMachine.State.keys()[new])


func _on_ready() -> void:
	_crosshair.active = false
	_crosshair.set_target(_target.get_center())
	_crosshair.reset_position()
	_hud.update_state("准备...")
	_hud.update_round(_sm.current_round + 1)
	_hud.show_timer(false)
	_hud.hide_result()


func _on_aiming_start() -> void:
	_crosshair.active = true
	_hud.update_state("瞄准中 — 保持专注！")
	_hud.show_timer(true)
	_peek_focus = _current_focus
	AudioManager.play_charge()


func _on_fired() -> void:
	_crosshair.active = false
	_hud.show_timer(false)
	AudioManager.stop_charge()

	# 记录射击时刻专注度 (取瞄准期间峰值)
	if _current_focus > _peek_focus:
		_peek_focus = _current_focus


func _on_scoring(_ring: int, _points: int) -> void:
	_hud.update_round(_sm.current_round)
	_hud.update_score(_mode.total_score)
	_hud.show_result(_last_result)

	# 音效
	var ring: int = _last_result.get("ring", 0)
	var combo: int = _last_result.get("combo_count", 0)
	if ring == 0:
		AudioManager.play_miss()
	else:
		AudioManager.play_hit(ring)
		if combo >= 2:
			AudioManager.play_combo(combo)


func _on_finished(_final_score: int) -> void:
	var summary := _mode.get_summary()
	_hud.show_final(summary.total_score, summary.rating, summary.best_combo, summary.bullseyes)


# --- 主循环 ---

func _process(delta: float) -> void:
	# 每帧同步专注度到准星和HUD（键盘模拟/BCI数据都覆盖）
	_crosshair.focus_ratio = _current_focus
	_hud.update_focus(_current_focus)

	if _sm.current_state == ArcheryStateMachine.State.AIMING:
		var progress := _sm.get_aiming_progress()
		_hud.update_timer(progress)
		AudioManager.update_charge(progress)

		# 检查瞄准是否到期，触发射箭
		if _sm._state_timer <= 0.0 and _crosshair.active:
			_fire_arrow()


## 射箭：计算环数，记录分数，触发布状态机
func _fire_arrow() -> void:
	AudioManager.play_bow_shoot()
	var ring := _crosshair.get_hit_ring(_target)
	_last_result = _mode.record_shot(ring, _peek_focus)
	_sm.trigger_fire(_last_result.ring, _last_result.total_points)


# --- 键盘输入 ---

func _input(event: InputEvent) -> void:
	if _sm.current_state == ArcheryStateMachine.State.FINISHED:
		if event.is_action_pressed("ui_accept"):
			_restart()
		elif event.is_action_pressed("ui_cancel"):
			ParadigmManager.go_to_main_menu()
		return

	if event.is_action_pressed("ui_cancel"):
		ParadigmManager.go_to_main_menu()

	# 调试：模拟专注度
	elif event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_1:
				_current_focus = 0.8
			KEY_2:
				_current_focus = 2.0
			KEY_3:
				_current_focus = 3.2


func _restart() -> void:
	for child in get_children():
		if child.name != "Background":
			child.queue_free()
	await get_tree().process_frame
	_on_paradigm_start()
