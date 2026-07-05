# OfflineTrainManager - self-contained offline training logic, HUD, and data recording
extends RefCounted

# Timing constants
const CYCLE_DURATION: float = 10.0
const PHASE_START_END: float = 2.0
const PHASE_MI_TASK_END: float = 6.0
const PHASE_JUMP_END: float = 7.0
const PHASE_SCORE_END: float = 8.0
const PHASE_RELAX_END: float = 10.0
const ARROW_FLASH_HZ: float = 1.0

# Platform layout constants
const TOTAL_LAYERS: int = 10
const START_X: float = 800.0
const START_Y: float = 120.0
const EDGE_DISTANCE: float = 90.0
const LAYER_GAP: float = 220.0
const PLATFORM_WIDTH: float = 170.0
const CAMERA_FIXED_Y: float = 340.0
const LANDING_Y_SNAP: float = 14.0

# State
var cycle_timer: float = 0.0
var phase: int = -1
var jump_executed: bool = false
var cheerful_played: bool = false
var start_label_sent: bool = false

# Platform state
var row_index: int = 0
var current_platform = null
var next_platform = null
var expected_platform = null
var jump_locked: bool = false
var fail_pending: bool = false
var fail_timer: float = 0.0
var start_time: float = 0.0
var completion_time: float = 0.0
var is_final_layer: bool = false

# Trial data
var trial_start_ms: int = 0
var trial_ground_truth: String = ""
var trial_mi_decision: String = ""
var trial_correct: bool = false
var mi_task_sent: bool = false
var relax_sent: bool = false
var phase_start_ms: int = 0
var phase_mitask_ms: int = 0
var phase_jump_ms: int = 0
var phase_score_ms: int = 0
var phase_relax_ms: int = 0

# References
var game: Node2D = null
const DataLoggerScript = preload("res://scripts/managers/data_logger.gd")
var data_logger = null

# UI nodes
var ui_container: Control = null
var timer_label: Label = null
var cheerful_player: AudioStreamPlayer = null


func init(p_game: Node2D) -> void:
	game = p_game
	data_logger = DataLoggerScript.new()
	_create_cheerful_sfx()
	_create_ui()


func is_active() -> bool:
	return game.game_state == game.GameState.PLAYING and game.current_mode == game.GameMode.VERTICAL_TRAIN_OFFLINE


func setup_level() -> void:
	row_index = 0
	jump_locked = false
	expected_platform = null
	fail_pending = false
	fail_timer = 0.0
	start_time = Time.get_ticks_msec() / 1000.0
	completion_time = 0.0
	is_final_layer = false

	if next_platform != null and is_instance_valid(next_platform):
		next_platform.queue_free()
	next_platform = null

	current_platform = _create_platform(START_X, START_Y, 220.0)
	game.player.reset_to_platform(current_platform)
	game.player.always_show_charge_bar = false
	game.camera_2d.global_position = Vector2(current_platform.global_position.x, CAMERA_FIXED_Y)
	_spawn_next_platform()

	var session_name: String = game._session_name_input.text.strip_edges() if game._session_name_input != null else ""
	var save_path: String = game._save_path if game._save_path != "" else ""
	data_logger.start_session(TOTAL_LAYERS, CYCLE_DURATION, {
		"subject": session_name if session_name != "" else game.subject_id,
		"start_s": PHASE_START_END, "mi_task_s": PHASE_MI_TASK_END,
		"jump_s": PHASE_JUMP_END, "score_s": PHASE_SCORE_END, "relax_s": PHASE_RELAX_END
	}, session_name, save_path)
	reset_cycle()


func reset_cycle() -> void:
	cycle_timer = 0.0
	phase = -1
	jump_executed = false
	cheerful_played = false
	# start_label_sent 不重置 —— 同一层重试不重复发 trial_start
	mi_task_sent = false
	relax_sent = false
	phase_start_ms = 0
	phase_mitask_ms = 0
	phase_jump_ms = 0
	phase_score_ms = 0
	phase_relax_ms = 0
	# 清除上一轮残留的 MI 标签，等待新的分类结果
	game.mi_decision_label = "none"
	game.mi_raw_streak = 0


func compute_direction() -> int:
	if current_platform == null or not is_instance_valid(current_platform):
		return 0
	if next_platform == null or not is_instance_valid(next_platform):
		return 0
	var dx: float = next_platform.global_position.x - current_platform.global_position.x
	return -1 if dx < 0.0 else 1


func update(delta: float) -> void:
	if not is_active():
		return

	if fail_pending:
		fail_timer = max(0.0, fail_timer - delta)
		if fail_timer <= 0.0:
			_finalize_fail()
		return

	cycle_timer += delta

	var prev_phase: int = phase
	if cycle_timer < PHASE_START_END:
		phase = 0
	elif cycle_timer < PHASE_MI_TASK_END:
		phase = 1
	elif cycle_timer < PHASE_JUMP_END:
		phase = 2
	elif cycle_timer < PHASE_SCORE_END:
		phase = 3
	else:
		phase = 4

	if phase != prev_phase:
		_on_phase_enter(phase)

	_update_phase(delta)

	# Camera follow: keep player centered (horizontal and vertical)
	var cam: Camera2D = game.camera_2d
	var target_x: float = game.player.global_position.x
	var target_y: float = game.player.global_position.y + 80.0
	var smooth: float = 1.0 - exp(-5.0 * delta)
	cam.global_position.x = lerp(cam.global_position.x, target_x, smooth)
	cam.global_position.y = lerp(cam.global_position.y, max(cam.global_position.y, target_y), smooth)

	if cycle_timer >= CYCLE_DURATION:
		_advance_layer()


func try_land(prev_feet_y: float, curr_feet_y: float) -> void:
	if not is_active():
		return
	var candidates: Array = []
	if current_platform != null and is_instance_valid(current_platform):
		candidates.append(current_platform)
	if next_platform != null and is_instance_valid(next_platform):
		candidates.append(next_platform)
	if candidates.is_empty():
		return

	var best = null
	var best_overlap: float = -1.0
	for p in candidates:
		var top_y: float = p.top_y()
		if not (prev_feet_y <= top_y + LANDING_Y_SNAP and curr_feet_y >= top_y - LANDING_Y_SNAP):
			continue
		var overlap: float = p.support_overlap_width(game.player.global_position.x, 18.0, 3.0)
		if overlap < 16.0:
			continue
		if overlap > best_overlap:
			best = p
			best_overlap = overlap

	if best == null:
		return

	var top_y: float = best.top_y()
	var landed_on_next: bool = best == next_platform
	game.player.land_on(top_y)
	game.player.global_position.x = clamp(game.player.global_position.x, best.left_edge() + 19.0, best.right_edge() - 19.0)
	game.standing_platform = best
	game.standing_platform_last_x = best.global_position.x
	expected_platform = null
	jump_locked = false
	fail_pending = false

	if landed_on_next:
		if current_platform != null and is_instance_valid(current_platform) and current_platform != best:
			current_platform.queue_free()
		current_platform = best
		next_platform = null
		row_index += 1
		game.score = row_index
		_play_land_sfx()
		game.mi_send_event("result", {"trial_id": data_logger.trial_id, "layer": row_index, "ground_truth": trial_ground_truth, "mi_decision": trial_mi_decision, "correct": true})
		save_trial(row_index, true)
		# 落地后清除标签，新试次需要新的分类结果
		game.mi_decision_label = "none"
		game.mi_raw_streak = 0
		if row_index >= TOTAL_LAYERS:
			is_final_layer = true
		else:
			_spawn_next_platform()
	else:
		game.score = row_index
		_play_land_sfx()
		start_label_sent = false  # 重试需要新的分类
		reset_cycle()


func update_hud() -> void:
	if ui_container == null:
		return
	var show: bool = is_active()
	ui_container.visible = show
	if not show:
		return

	var bar_x: float = ui_container.get_meta("bar_x", 400.0)
	var bar_total_w: float = ui_container.get_meta("bar_total_w", 560.0)
	var phase_widths: Array = ui_container.get_meta("phase_widths", [])
	var phase_names: Array = ui_container.get_meta("phase_names", [])

	for i: int in range(5):
		var block: ColorRect = ui_container.get_node_or_null("PhaseBlock" + str(i))
		if block != null:
			if i == phase: block.color.a = 0.9
			elif i < phase: block.color.a = 0.55
			else: block.color.a = 0.25

	var indicator: Polygon2D = ui_container.get_meta("indicator")
	if indicator != null and phase_widths.size() == 5:
		indicator.position.x = bar_x + (cycle_timer / CYCLE_DURATION) * bar_total_w

	if timer_label != null:
		var phase_end: float = CYCLE_DURATION
		match phase:
			0: phase_end = PHASE_START_END
			1: phase_end = PHASE_MI_TASK_END
			2: phase_end = PHASE_JUMP_END
			3: phase_end = PHASE_SCORE_END
			4: phase_end = PHASE_RELAX_END
		var remaining: float = max(0.0, phase_end - cycle_timer)
		var pname: String = phase_names[clampi(phase, 0, 4)]
		var total_elapsed: float = Time.get_ticks_msec() / 1000.0 - start_time
		timer_label.text = "%s | %.1fs | Layer %d/%d | %.1fs" % [pname, remaining, row_index + 1, TOTAL_LAYERS, total_elapsed]


# ── Internal: Platform ──

func _create_platform(x: float, y: float, w: float):
	var p = game.PLATFORM_SCENE.instantiate()
	p.global_position = Vector2(x, y)
	game.platforms_root.add_child(p)
	p.setup(0, w, 0.0, game.rng, 0.0)  # PlatformKind.NORMAL = 0
	return p


func _spawn_next_platform() -> void:
	if current_platform == null or not is_instance_valid(current_platform):
		return
	if next_platform != null and is_instance_valid(next_platform) and next_platform != current_platform:
		next_platform.queue_free()
		next_platform = null
	var next_y: float = current_platform.global_position.y + LAYER_GAP
	var side: int = -1 if game.rng.randf() < 0.5 else 1
	var next_x: float
	if side < 0:
		next_x = current_platform.left_edge() - EDGE_DISTANCE - PLATFORM_WIDTH * 0.5
	else:
		next_x = current_platform.right_edge() + EDGE_DISTANCE + PLATFORM_WIDTH * 0.5
	next_platform = _create_platform(next_x, next_y, PLATFORM_WIDTH)
	expected_platform = next_platform


# ── Internal: Jump ──

func _execute_jump(direction: int) -> void:
	if jump_locked or game.player.is_airborne or fail_pending:
		return
	if direction == 0 or current_platform == null or next_platform == null:
		return
	if not is_instance_valid(current_platform) or not is_instance_valid(next_platform):
		return

	var delta_x: float = next_platform.global_position.x - current_platform.global_position.x
	var expected_dir: int = -1 if delta_x < 0.0 else 1
	if direction != expected_dir:
		_fail()
		return

	var h_speed: float = abs(delta_x) / 1.0
	var v_speed: float = max(120.0, (game.player.gravity * 0.5) - LAYER_GAP)
	if game.player.launch_fixed_jump(float(direction), h_speed, v_speed):
		expected_platform = next_platform
		jump_locked = true


func _fail() -> void:
	if fail_pending:
		return
	save_trial(row_index, false)
	fail_pending = true
	fail_timer = 0.55
	game.player.fail_vertical_lr_fall()
	expected_platform = null
	jump_locked = true
	game.standing_platform = null
	game.standing_platform_last_x = 0.0
	_play_fail_sfx()


func _finalize_fail() -> void:
	fail_pending = false
	jump_locked = false
	if current_platform != null and is_instance_valid(current_platform):
		game.player.reset_to_platform(current_platform)
		game.standing_platform = current_platform
		game.standing_platform_last_x = current_platform.global_position.x
		game.score = row_index
		_play_land_sfx()
		reset_cycle()
	else:
		_send_session_summary()
		game.end_game(str(row_index))
	game._refresh_ui()


func _send_session_summary() -> void:
	if data_logger == null:
		return
	var summary: Dictionary = data_logger.get_session_summary()
	game.mi_send_event("session_end", summary)
	print("OfflineTrain session summary sent: %d trials" % summary.get("total_trials", 0))

func _complete() -> void:
	_send_session_summary()
	completion_time = (Time.get_ticks_msec() / 1000.0) - start_time
	fail_pending = false
	jump_locked = false
	game.score = row_index
	game.end_game("%.1fs" % completion_time)



# ── Internal: Phase Handlers ──

func _on_phase_enter(p: int) -> void:
	match p:
		0: _phase_start()
		1: _phase_mitask()
		2: _phase_jump()
		3: _phase_score()
		4: _phase_relax()


func _phase_start() -> void:
	if not start_label_sent:
		start_label_sent = true
		trial_start_ms = int(Time.get_unix_time_from_system() * 1000.0)
		trial_ground_truth = "left" if compute_direction() < 0 else "right"
		trial_mi_decision = "rest"
		trial_correct = false
		phase_start_ms = trial_start_ms
		game.mi_send_event("trial_start", {"layer": row_index + 1, "ground_truth": trial_ground_truth})


func _phase_mitask() -> void:
	if not mi_task_sent:
		mi_task_sent = true
		phase_mitask_ms = int(Time.get_unix_time_from_system() * 1000.0)
		game.mi_send_event("mi_task", {"layer": row_index + 1, "ground_truth": trial_ground_truth})
	if next_platform != null and is_instance_valid(next_platform):
		next_platform.hide_direction_arrow()


func _phase_jump() -> void:
	if jump_executed:
		return
	jump_executed = true
	phase_jump_ms = int(Time.get_unix_time_from_system() * 1000.0)
	trial_mi_decision = game.mi_decision_label if game.mi_decision_label != "none" else "rest"
	game.mi_send_event("trial_jump", {"direction": trial_mi_decision, "ground_truth": trial_ground_truth})
	var direction: int = compute_direction()
	if direction != 0:
		_execute_jump(direction)


func _phase_score() -> void:
	if not cheerful_played:
		cheerful_played = true
		phase_score_ms = int(Time.get_unix_time_from_system() * 1000.0)
		game.mi_send_event("trial_score", {"layer": row_index + 1, "correct": trial_correct})


func _phase_relax() -> void:
	if not relax_sent:
		relax_sent = true
		phase_relax_ms = int(Time.get_unix_time_from_system() * 1000.0)
		game.mi_send_event("trial_relax", {"layer": row_index + 1})
	if next_platform != null and is_instance_valid(next_platform):
		next_platform.hide_direction_arrow()


func _update_phase(_delta: float) -> void:
	match phase:
		0:
			_update_player_flash()
			_update_arrow_flash()
		1:
			if next_platform != null and is_instance_valid(next_platform):
				next_platform.hide_direction_arrow()
			game.player.modulate = Color(game.brightness, game.brightness, game.brightness, 1.0)
		_:
			pass


func _update_player_flash() -> void:
	var bt: Color = Color(game.brightness, game.brightness, game.brightness, 1.0)
	var blink: float = 0.5 + (0.5 * sin(cycle_timer * 16.0))
	var ft: Color = Color(1.0, 0.96, 0.58, 1.0)
	game.player.modulate = bt.lerp(ft, clamp(blink, 0.0, 1.0))


func _update_arrow_flash() -> void:
	if cycle_timer >= PHASE_START_END:
		return
	if next_platform == null or not is_instance_valid(next_platform):
		return
	var dir: int = compute_direction()
	next_platform.show_direction_arrow(dir)
	var half: float = 0.5 / ARROW_FLASH_HZ
	next_platform.set_arrow_visible(fmod(cycle_timer, half * 2.0) < half)


func _advance_layer() -> void:
	start_label_sent = false  # 新层需要发新的 trial_start
	reset_cycle()
	if is_final_layer:
		_complete()
		return
	if next_platform == null or not is_instance_valid(next_platform):
		_spawn_next_platform()


# ── Internal: Data ──

func save_trial(layer: int, correct: bool) -> void:
	var now_ms: int = int(Time.get_unix_time_from_system() * 1000.0)
	var trial_data: Dictionary = {
		"type": "trial",
		"trial_id": data_logger.trial_id + 1,
		"layer": layer + 1,
		"ground_truth": trial_ground_truth,
		"mi_decision": trial_mi_decision,
		"correct": correct,
		"timestamp_trial_start_ms": trial_start_ms,
		"timestamp_mi_task_ms": phase_mitask_ms,
		"timestamp_jump_ms": phase_jump_ms,
		"timestamp_score_ms": phase_score_ms,
		"timestamp_relax_ms": phase_relax_ms,
		"timestamp_trial_end_ms": now_ms,
	}
	data_logger.save_trial_full(trial_data)


# ── Internal: SFX ──

func _create_cheerful_sfx() -> void:
	cheerful_player = AudioStreamPlayer.new()
	cheerful_player.name = "SfxCheerful"
	var gen: AudioStreamGenerator = AudioStreamGenerator.new()
	gen.mix_rate = 44100.0
	gen.buffer_length = 0.2
	cheerful_player.stream = gen
	game.add_child(cheerful_player)


func _play_cheerful() -> void:
	if cheerful_player == null:
		return
	cheerful_player.stop()
	cheerful_player.play()
	var playback = cheerful_player.get_stream_playback()
	if playback == null:
		return
	var notes = [Vector2(523.0, 0.09), Vector2(659.0, 0.09), Vector2(784.0, 0.12)]
	for note in notes:
		var freq: float = note.x
		var dur: float = note.y
		var frames: int = max(1, int(dur * 44100.0))
		for i: int in range(frames):
			var t: float = float(i) / 44100.0
			var progress: float = float(i) / float(frames)
			var env: float = pow(1.0 - progress, 1.9) * sin(PI * progress)
			var sample: float = (sin(TAU * freq * t) + 0.18 * sin(TAU * freq * 2.0 * t)) * env * 0.26
			playback.push_frame(Vector2(sample, sample))


func _play_land_sfx() -> void:
	game._play_land_sfx()


func _play_fail_sfx() -> void:
	game._play_fail_sfx()


# ── Internal: UI ──

func _create_ui() -> void:
	ui_container = Control.new()
	ui_container.name = "OfflineTrainUI"
	ui_container.visible = false
	game.get_node("HUD").add_child(ui_container)

	var vp_size: Vector2 = game.get_viewport_rect().size
	var bar_y: float = 16.0
	var bar_total_w: float = min(560.0, vp_size.x - 40.0)
	var bar_h: float = 28.0
	var bar_x: float = (vp_size.x - bar_total_w) * 0.5

	var phase_widths: Array[float] = [
		bar_total_w * 0.20, bar_total_w * 0.40, bar_total_w * 0.10, bar_total_w * 0.10, bar_total_w * 0.20
	]
	var phase_colors: Array[Color] = [
		Color(0.25, 0.55, 0.90, 0.85), Color(0.30, 0.68, 0.32, 0.85),
		Color(0.94, 0.58, 0.18, 0.85), Color(0.96, 0.78, 0.12, 0.85), Color(0.45, 0.45, 0.48, 0.85)
	]
	var pnames: Array[String] = ["START", "MI TASK", "JUMP", "SCORE", "RELAX"]
	var ptimes: Array[String] = ["0-2s", "2-6s", "6-7s", "7-8s", "8-10s"]

	var cursor_x: float = bar_x
	for i: int in range(5):
		var block: ColorRect = ColorRect.new()
		block.name = "PhaseBlock" + str(i)
		block.color = phase_colors[i]
		block.color.a = 0.35
		block.size = Vector2(phase_widths[i] - 2.0, bar_h)
		block.position = Vector2(cursor_x, bar_y)
		ui_container.add_child(block)

		var nl: Label = Label.new()
		nl.text = pnames[i]
		nl.position = Vector2(cursor_x, bar_y + bar_h + 4.0)
		nl.size = Vector2(phase_widths[i], 18)
		nl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		nl.add_theme_color_override("font_color", Color(0.25, 0.50, 0.30, 1.0))
		nl.add_theme_font_size_override("font_size", 12)
		ui_container.add_child(nl)

		var tl: Label = Label.new()
		tl.text = ptimes[i]
		tl.position = Vector2(cursor_x, bar_y + bar_h + 22.0)
		tl.size = Vector2(phase_widths[i], 16)
		tl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		tl.add_theme_color_override("font_color", Color(0.35, 0.55, 0.38, 1.0))
		tl.add_theme_font_size_override("font_size", 11)
		ui_container.add_child(tl)

		cursor_x += phase_widths[i]

	var indicator: Polygon2D = Polygon2D.new()
	indicator.name = "ProgressIndicator"
	indicator.color = Color(0.25, 0.50, 0.30, 0.95)
	indicator.polygon = PackedVector2Array([
		Vector2(-8.0, 12.0), Vector2(8.0, 12.0), Vector2(0.0, 0.0)
	])
	indicator.position = Vector2(bar_x, bar_y + bar_h + 2.0)
	ui_container.add_child(indicator)

	ui_container.set_meta("indicator", indicator)
	ui_container.set_meta("bar_x", bar_x)
	ui_container.set_meta("bar_total_w", bar_total_w)
	ui_container.set_meta("bar_y", bar_y)
	ui_container.set_meta("bar_h", bar_h)
	ui_container.set_meta("phase_widths", phase_widths)
	ui_container.set_meta("phase_colors", phase_colors)
	ui_container.set_meta("phase_names", pnames)

	timer_label = Label.new()
	timer_label.name = "TimerLabel"
	timer_label.position = Vector2(20, 16)
	timer_label.size = Vector2(400, 24)
	timer_label.add_theme_color_override("font_color", Color(0.25, 0.50, 0.30, 1.0))
	timer_label.add_theme_font_size_override("font_size", 16)
	ui_container.add_child(timer_label)
