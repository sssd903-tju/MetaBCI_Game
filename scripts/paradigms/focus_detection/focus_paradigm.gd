extends BaseParadigm
## FocusParadigm — 凝神一矢：专注度检测·射箭范式
##
## 管理: 基线采集 → 状态机 + 模式 + 靶子 + 准星 + HUD

# 场景组件
var _sm: ArcheryStateMachine
var _mode: ArcheryMode
var _target: ArcheryTarget
var _crosshair: ArcheryCrosshair
var _hud: ArcheryHUD
var _distractor_spawner: DistractorSpawner

# 当前专注度 (百分制 0-100)
var _current_focus := 50
var _peek_focus := 50  # 射箭时刻的专注度
var _last_result: Dictionary = {}  # 最近一次射箭结果

# 基线采集 — 独立全屏界面
enum Phase { BASELINE_INTRO, BASELINE, PLAYING, OVER }
var _phase: int = Phase.BASELINE_INTRO
var _baseline_timer: float = 10.0
var _baseline_screen: Control
var _baseline_title: Label
var _baseline_instruction: Label
var _baseline_countdown: Label
var _baseline_bar: ColorRect
var _baseline_bg: ColorRect


func _ready() -> void:
	paradigm_type = GlobalConfig.ParadigmType.FOCUS_DETECTION
	super._ready()


func _on_paradigm_start() -> void:
	_setup_background()
	_setup_game()
	_phase = Phase.BASELINE_INTRO
	_baseline_timer = 10.0
	BCIConnector.send_game_event("baseline_start", {})
	_show_baseline_screen()


func _begin_baseline() -> void:
	_phase = Phase.BASELINE
	_baseline_timer = 10.0
	_baseline_title.text = "基线校准"
	_baseline_instruction.text = "请放松，闭上眼睛，保持自然呼吸"
	_baseline_bg.visible = true
	_baseline_bar.visible = true


func _baseline_done() -> void:
	_phase = Phase.PLAYING
	_hide_baseline_screen()
	BCIConnector.send_game_event("baseline_done", {})
	AudioManager.play_baseline_complete()
	_mode.start_new_game()
	_sm._enter_ready()


func _on_paradigm_end() -> void:
	print("[凝神一矢] 结束，总分: %d" % _mode.total_score)


func _on_bci_data(data: Dictionary) -> void:
	_current_focus = float(BCIConnector.latest_focus_pct)
	_crosshair.focus_ratio = _current_focus
	_hud.update_focus(_current_focus)


# ============================================================
# 基线采集 — 独立全屏界面
# ============================================================

func _create_baseline_screen() -> void:
	_baseline_screen = Control.new()
	_baseline_screen.name = "BaselineScreen"
	_baseline_screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_baseline_screen)

	# 半透明背景 — 莫兰迪暖米色
	var overlay := ColorRect.new()
	overlay.color = Color("EFE9D8", 1.0)
	overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_baseline_screen.add_child(overlay)

	# 图标
	var icon := Label.new()
	icon.text = "🧘"
	icon.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	icon.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	icon.add_theme_font_size_override("font_size", 64)
	icon.position = Vector2(0, 160)
	icon.size = Vector2(GlobalConfig.GAME_WIDTH, 80)
	_baseline_screen.add_child(icon)

	# 标题
	_baseline_title = _make_baseline_label("准备校准", 32, Color("3F6850"))
	_baseline_title.position = Vector2(0, 260)
	_baseline_title.size = Vector2(GlobalConfig.GAME_WIDTH, 42)
	_baseline_screen.add_child(_baseline_title)

	# 引导文字
	_baseline_instruction = _make_baseline_label("请放松，保持安静...", 20, Color("5A8A6A"))
	_baseline_instruction.position = Vector2(0, 320)
	_baseline_instruction.size = Vector2(GlobalConfig.GAME_WIDTH, 28)
	_baseline_screen.add_child(_baseline_instruction)

	# 进度条背景
	_baseline_bg = ColorRect.new()
	_baseline_bg.color = Color("D5CFBF", 0.6)
	_baseline_bg.size = Vector2(400, 12)
	_baseline_bg.position = Vector2((GlobalConfig.GAME_WIDTH - 400) / 2.0, 390)
	_baseline_bg.visible = false
	_baseline_screen.add_child(_baseline_bg)

	# 进度条
	_baseline_bar = ColorRect.new()
	_baseline_bar.color = Color("5A8A6A")
	_baseline_bar.size = Vector2(0, 12)
	_baseline_bar.position = _baseline_bg.position
	_baseline_bar.visible = false
	_baseline_screen.add_child(_baseline_bar)

	# 倒计时
	_baseline_countdown = _make_baseline_label("", 48, Color("3F6850"))
	_baseline_countdown.position = Vector2(0, 420)
	_baseline_countdown.size = Vector2(GlobalConfig.GAME_WIDTH, 56)
	_baseline_screen.add_child(_baseline_countdown)

	# 底部提示
	var hint := _make_baseline_label("脑电基线采集进行中，完成后自动开始游戏", 14, Color("8BA89A"))
	hint.position = Vector2(0, GlobalConfig.GAME_HEIGHT - 60)
	hint.size = Vector2(GlobalConfig.GAME_WIDTH, 20)
	_baseline_screen.add_child(hint)


func _make_baseline_label(text: String, font_size: int, color: Color) -> Label:
	var lbl := Label.new()
	lbl.text = text
	lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	lbl.add_theme_font_size_override("font_size", font_size)
	lbl.add_theme_color_override("font_color", color)
	return lbl


func _show_baseline_screen() -> void:
	_baseline_screen.visible = true
	_target.visible = false
	_crosshair.visible = false
	_hud.visible = false


func _hide_baseline_screen() -> void:
	_baseline_screen.visible = false
	_target.visible = true
	_crosshair.visible = true
	_hud.visible = true


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

	# HUD (创建基线界面需要 HUD 先存在)
	_hud = ArcheryHUD.new()
	_hud.name = "HUD"
	_hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_hud)

	# 干扰物生成器
	_distractor_spawner = DistractorSpawner.new()
	_distractor_spawner.name = "DistractorSpawner"
	add_child(_distractor_spawner)

	# 连接状态机信号
	_sm.state_changed.connect(_on_state_changed)
	_sm.ready_started.connect(_on_ready)
	_sm.aiming_started.connect(_on_aiming_start)
	_sm.fired.connect(_on_fired)
	_sm.scoring_started.connect(_on_scoring)
	_sm.finished.connect(_on_finished)

	# 独立基线界面 (最上层，放在 HUD 内)
	_create_baseline_screen()


# --- 状态回调 ---

func _on_state_changed(_old: ArcheryStateMachine.State, new: ArcheryStateMachine.State) -> void:
	print("[凝神一矢] 状态: ", ArcheryStateMachine.State.keys()[new])


func _on_ready() -> void:
	_crosshair.active = false
	_crosshair.set_target(_target.get_center())
	_crosshair.reset_position()
	_distractor_spawner.active = false
	_distractor_spawner.clear_all()
	_hud.update_state("准备...")
	_hud.update_round(_sm.current_round + 1)
	_hud.show_timer(false)
	_hud.hide_result()


func _on_aiming_start() -> void:
	_crosshair.active = true
	_distractor_spawner.active = true
	_hud.update_state("瞄准中 — 保持专注！")
	_hud.show_timer(true)
	_peek_focus = _current_focus
	AudioManager.play_charge()


func _on_fired() -> void:
	_crosshair.active = false
	_distractor_spawner.active = false
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
		var ding_count: int = combo
		if ring == 10:
			ding_count += 1  # 十环多叮一次
		if ding_count >= 1:
			AudioManager.play_combo(ding_count)


func _on_finished(_final_score: int) -> void:
	var summary := _mode.get_summary()
	_hud.show_final(summary.total_score, summary.rating, summary.best_combo, summary.bullseyes)


# --- 主循环 ---

func _process(delta: float) -> void:
	match _phase:
		Phase.BASELINE_INTRO:
			_baseline_timer -= delta
			if _baseline_timer <= 8.0:
				_begin_baseline()
		Phase.BASELINE:
			_baseline_timer -= delta
			_baseline_bar.size.x = _baseline_bg.size.x * (1.0 - _baseline_timer / 10.0)
			_baseline_countdown.text = "%d" % int(_baseline_timer)
			if _baseline_timer <= 0.0:
				_baseline_done()
			return
		Phase.OVER:
			return

	# 每帧同步专注度到准星和HUD（BCI数据优先）
	_current_focus = float(BCIConnector.latest_focus_pct)
	_crosshair.focus_ratio = _current_focus
	_hud.update_focus(_current_focus)

	if _sm.current_state == ArcheryStateMachine.State.AIMING:
		var progress := _sm.get_aiming_progress()
		_hud.update_timer(progress)
		AudioManager.update_charge(progress)
		_distractor_spawner.update_spawning(delta, _mode.combo)

		# 检查瞄准是否到期，触发射箭
		if _sm._state_timer <= 0.0 and _crosshair.active:
			_fire_arrow()


## 射箭：计算环数，记录分数，触发状态机
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

	# 调试：模拟专注度 (百分制)
	elif event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_1:
				_current_focus = 20
			KEY_2:
				_current_focus = 50
			KEY_3:
				_current_focus = 80


func _restart() -> void:
	for child in get_children():
		if child.name != "Background":
			child.queue_free()
	await get_tree().process_frame
	_on_paradigm_start()
