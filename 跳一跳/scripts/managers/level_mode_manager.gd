# LevelModeManager - continuous jump level mode (free rhythm, manual/MI)
extends RefCounted

const DataLoggerScript = preload("res://scripts/managers/data_logger.gd")

# Platform layout constants
const START_X: float = 800.0
const START_Y: float = 120.0
const CAMERA_FIXED_Y: float = 340.0
const LANDING_Y_SNAP: float = 14.0
const ARROW_HINT_DURATION: float = 2.0
const IDLE_TIMEOUT: float = 5.0

# Level definitions
const LEVELS: Array[Dictionary] = [
	{"name_cn": "简单", "name_en": "Easy",   "layers": 5,  "width": 200.0, "gap": 150.0, "mi_thresh": 0.60, "special": 0.0},
	{"name_cn": "普通", "name_en": "Normal", "layers": 8,  "width": 170.0, "gap": 220.0, "mi_thresh": 0.70, "special": 0.2},
	{"name_cn": "困难", "name_en": "Hard",   "layers": 10, "width": 140.0, "gap": 300.0, "mi_thresh": 0.75, "special": 0.4},
	{"name_cn": "专家", "name_en": "Expert", "layers": 12, "width": 110.0, "gap": 380.0, "mi_thresh": 0.80, "special": 0.6},
]

# State
var current_level: int = 0
var row_index: int = 0
var current_platform = null
var next_platform = null
var jump_locked: bool = false
var fail_pending: bool = false
var fail_timer: float = 0.0
var start_time: float = 0.0
var arrow_timer: float = 0.0
var _first_trial: bool = true
var arrow_shown: bool = false
var idle_timer: float = 0.0
var land_pending: bool = false
var status_text: String = ""
var _trial_sent: bool = false
var lives: int = 3
var invincible_timer: float = 0.0
var wrong_dir_timer: float = 0.0
var on_fragile: bool = false
var fragile_timer: float = 0.0
var airborne_timer: float = 0.0

# References
var game: Node2D = null
var data_logger = null

# UI nodes
var ui_container: Control = null
var info_label: Label = null
var status_label: Label = null
var session_started: bool = false


func init(p_game: Node2D) -> void:
	game = p_game
	data_logger = DataLoggerScript.new()
	_create_ui()


func is_active() -> bool:
	return game.game_state == 1 and game.current_mode == game.GameMode.VERTICAL_TRAIN


func level_config() -> Dictionary:
	return LEVELS[current_level]


func setup_level() -> void:
	var cfg: Dictionary = level_config()
	row_index = 0
	lives = 3
	invincible_timer = 0.0
	wrong_dir_timer = 0.0
	on_fragile = false
	fragile_timer = 0.0
	airborne_timer = 0.0
	jump_locked = false
	fail_pending = false
	fail_timer = 0.0
	start_time = Time.get_ticks_msec() / 1000.0
	arrow_timer = 0.0
	arrow_shown = false
	idle_timer = 0.0
	land_pending = false
	status_text = ""

	if next_platform != null and is_instance_valid(next_platform):
		next_platform.queue_free()
	next_platform = null

	current_platform = _create_platform(START_X, START_Y, 220.0, false)
	game.player.reset_to_platform(current_platform)
	game.player.always_show_charge_bar = false
	game.camera_2d.global_position = Vector2(current_platform.global_position.x, CAMERA_FIXED_Y)
	_spawn_next_platform()
	_show_arrow()
	if not session_started:
		session_started = true
		data_logger.start_session(cfg["layers"], 0, {"mode": "level", "level": cfg["name_cn"]})


func update(delta: float) -> void:
	if not is_active():
		return

	# Airborne timeout: fall if missed platform
	if game.player.is_airborne and jump_locked and not fail_pending:
		airborne_timer += delta
		if airborne_timer > 3.0:
			_fail()
			return
	else:
		airborne_timer = 0.0

	# Fragile platform break countdown
	if on_fragile and not game.player.is_airborne:
		fragile_timer = max(0.0, fragile_timer - delta)
		if fragile_timer <= 0.0:
			_fall_from_broken_platform()
			return

	# Wrong direction: short flight then trigger fall
	if wrong_dir_timer > 0.0:
		wrong_dir_timer = max(0.0, wrong_dir_timer - delta)
		if wrong_dir_timer <= 0.0:
			_fail()
			return

	if fail_pending:
		fail_timer = max(0.0, fail_timer - delta)
		if fail_timer <= 0.0:
			_finalize_fail()
			return
		# Follow camera during fall animation
		_follow_camera(delta)
		return

	# Invincible flash after respawn
	if invincible_timer > 0.0:
		invincible_timer = max(0.0, invincible_timer - delta)
		var bt: Color = Color(game.brightness, game.brightness, game.brightness, 1.0)
		var blink: float = 0.5 + 0.5 * sin(invincible_timer * 20.0)
		game.player.modulate = bt.lerp(Color(1.0, 1.0, 1.0, 0.4), blink)
		if invincible_timer <= 0.0:
			game.player.modulate = bt

	if land_pending:
		return

	# Arrow hint timer
	if arrow_shown:
		arrow_timer -= delta
		if arrow_timer <= 0.0:
			_hide_arrow()
			idle_timer = 0.0
			status_text = "选择方向" if game.current_control_mode == game.ControlMode.MANUAL else "MI采集中..."
			# 箭头隐藏 → 发 trial_start, 服务器4s后分类
			if not _trial_sent:
				_trial_sent = true
				var _dx: float = next_platform.global_position.x - current_platform.global_position.x
				game.mi_send_event("trial_start", {"layer": row_index + 1, "ground_truth": "left" if _dx < 0 else "right"})

	# Idle timeout
	if not arrow_shown and not jump_locked:
		idle_timer += delta
		if idle_timer >= IDLE_TIMEOUT:
			_timeout_jump()

	# Player follows moving platform
	if not game.player.is_airborne and current_platform != null and is_instance_valid(current_platform):
		if current_platform.platform_kind == 2:  # MOVING
			var dx: float = current_platform.global_position.x - game.standing_platform_last_x
			game.player.global_position.x += dx
			game.standing_platform_last_x = current_platform.global_position.x

	# Camera follow
	_follow_camera(delta)


func try_jump(direction: int) -> void:
	if not is_active() or land_pending:
		return
	if jump_locked or game.player.is_airborne or fail_pending:
		return
	if arrow_shown:
		return
	if direction == 0:
		return
	if current_platform == null or next_platform == null:
		return
	if not is_instance_valid(current_platform) or not is_instance_valid(next_platform):
		return

	var delta_x: float = next_platform.global_position.x - current_platform.global_position.x
	var expected_dir: int = -1 if delta_x < 0.0 else 1

	var cfg: Dictionary = level_config()
	if direction != expected_dir:
		# Wrong direction: small stumble hop, then fall
		var h_speed: float = abs(delta_x) * 0.3
		var v_speed: float = 150.0
		if game.player.launch_fixed_jump(float(direction), h_speed, v_speed):
			jump_locked = true
			idle_timer = 0.0
			wrong_dir_timer = 0.25
			status_text = "方向错误!"
			game.mi_send_event("response", {"direction": "left" if direction < 0 else "right", "correct": false})
	else:
		# Correct direction: full jump
		var h_speed: float = abs(delta_x) / 1.0
		var v_speed: float = max(120.0, (game.player.gravity * 0.5) - cfg["gap"])
		if game.player.launch_fixed_jump(float(direction), h_speed, v_speed):
			jump_locked = true
			idle_timer = 0.0
			status_text = "跳跃中..."
			game.mi_send_event("response", {"direction": "left" if direction < 0 else "right", "correct": true})


func try_land(prev_feet_y: float, curr_feet_y: float) -> void:
	if not is_active():
		return
	if fail_pending:
		return  # Don't catch player during fall animation
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

	var landed_on_next: bool = best == next_platform
	game.player.land_on(best.top_y())
	game.player.global_position.x = clamp(game.player.global_position.x, best.left_edge() + 19.0, best.right_edge() - 19.0)
	game.standing_platform = best
	game.standing_platform_last_x = best.global_position.x
	jump_locked = false
	fail_pending = false
	land_pending = false
	airborne_timer = 0.0

	if landed_on_next:
		if current_platform != null and is_instance_valid(current_platform) and current_platform != best:
			current_platform.queue_free()
		current_platform = best
		next_platform = null
		row_index += 1
		game.score = row_index
		game._play_land_sfx()
		game.mi_send_event("result", {"correct": true})
		current_platform.on_landed()
		data_logger.save_trial(row_index + 1, "correct", game.mi_decision_label, true, int(Time.get_unix_time_from_system() * 1000.0))
		status_text = "着陆成功!"
		var cfg: Dictionary = level_config()
		if row_index >= cfg["layers"]:
			_complete()
			return
		_spawn_next_platform()
		on_fragile = (current_platform.platform_kind == 3)
		fragile_timer = 2.0 if on_fragile else 0.0
		_show_arrow()
	else:
		game.score = row_index
		game._play_land_sfx()
		status_text = "返回平台"
		_show_arrow()


func update_hud() -> void:
	if ui_container == null:
		return
	var show: bool = is_active()
	ui_container.visible = show
	if not show:
		return
	if info_label != null:
		var cfg: Dictionary = level_config()
		var elapsed: float = Time.get_ticks_msec() / 1000.0 - start_time
		var hearts: String = ""
		for _i in range(lives):
			hearts += "❤️ "
		info_label.text = "%s | %s| Layer %d/%d | %.1fs" % [cfg["name_cn"], hearts, row_index + 1, cfg["layers"], elapsed]
	if status_label != null:
		status_label.text = status_text


# ── Internal: Platform ──

func _follow_camera(delta: float) -> void:
	var cam: Camera2D = game.camera_2d
	var smooth: float = 1.0 - exp(-5.0 * delta)
	cam.global_position.x = lerp(cam.global_position.x, game.player.global_position.x, smooth)
	cam.global_position.y = lerp(cam.global_position.y, max(cam.global_position.y, game.player.global_position.y + 80.0), smooth)

func _create_platform(x: float, y: float, w: float, can_special: bool):
	var kind: int = 0  # NORMAL
	if can_special:
		var cfg: Dictionary = level_config()
		if game.rng.randf() < cfg["special"]:
			kind = 2 if game.rng.randf() < 0.5 else 3  # MOVING or FRAGILE
	var p = game.PLATFORM_SCENE.instantiate()
	p.global_position = Vector2(x, y)
	game.platforms_root.add_child(p)
	var ms: float = 0.86 if kind == 2 else 0.0
	p.setup(kind, w, 0.3, game.rng, ms)
	return p


func _spawn_next_platform() -> void:
	if current_platform == null or not is_instance_valid(current_platform):
		return
	var cfg: Dictionary = level_config()
	var next_y: float = current_platform.global_position.y + cfg["gap"]
	var side: int = -1 if game.rng.randf() < 0.5 else 1
	var next_x: float
	var w: float = cfg["width"]
	if side < 0:
		next_x = current_platform.left_edge() - cfg["gap"] * 0.9 - w * 0.5
	else:
		next_x = current_platform.right_edge() + cfg["gap"] * 0.9 + w * 0.5
	next_platform = _create_platform(next_x, next_y, w, true)


func _show_arrow() -> void:
	if next_platform == null or not is_instance_valid(next_platform):
		return
	var dx: float = next_platform.global_position.x - current_platform.global_position.x
	var dir: int = -1 if dx < 0.0 else 1
	next_platform.show_direction_arrow(dir)
	arrow_shown = true
	arrow_timer = 0.5 if _first_trial else ARROW_HINT_DURATION
	_first_trial = false
	status_text = "观察方向..."
	_trial_sent = false
	game.mi_decision_label = "none"


func _hide_arrow() -> void:
	if next_platform != null and is_instance_valid(next_platform):
		next_platform.hide_direction_arrow()
	arrow_shown = false
	idle_timer = 0.0


func _timeout_jump() -> void:
	var dir: int = -1 if game.rng.randf() < 0.5 else 1
	try_jump(dir)


func _fall_from_broken_platform() -> void:
	if fail_pending:
		return
	fail_pending = true
	fail_timer = 1.0
	lives -= 1
	# Push below and start falling
	game.player.global_position.y += 50.0
	game.player.fail_vertical_lr_fall()
	jump_locked = true
	game.standing_platform = null
	game.standing_platform_last_x = 0.0
	current_platform = null
	on_fragile = false
	fragile_timer = 0.0
	game._play_fail_sfx()
	status_text = "平台碎裂! ❤️x%d" % lives

func _fail() -> void:
	if fail_pending:
		return
	fail_pending = true
	fail_timer = 1.0
	lives -= 1
	game.player.fail_vertical_lr_fall()
	game.player.velocity.y = max(game.player.velocity.y, 600.0)
	jump_locked = true
	game.standing_platform = null
	game.standing_platform_last_x = 0.0
	data_logger.save_trial(row_index + 1, "wrong", game.mi_decision_label, false, int(Time.get_unix_time_from_system() * 1000.0))
	game._play_fail_sfx()
	status_text = "失败! ❤️x%d" % lives


func _finalize_fail() -> void:
	fail_pending = false
	jump_locked = false
	land_pending = false
	wrong_dir_timer = 0.0
	airborne_timer = 0.0
	if lives <= 0:
		game.end_game(str(row_index))
		return
	invincible_timer = 1.0
	if current_platform != null and is_instance_valid(current_platform):
		game.player.reset_to_platform(current_platform)
		game.standing_platform = current_platform
		game.standing_platform_last_x = current_platform.global_position.x
		game.score = row_index
		game._play_land_sfx()
		_show_arrow()
	elif next_platform != null and is_instance_valid(next_platform):
		current_platform = next_platform
		next_platform = null
		game.player.reset_to_platform(current_platform)
		game.standing_platform = current_platform
		game.standing_platform_last_x = current_platform.global_position.x
		game.score = row_index
		game._play_land_sfx()
		_spawn_next_platform()
		_show_arrow()
	else:
		game.end_game(str(row_index))
		return
	# Snap camera after respawn
	game.camera_2d.global_position = game.player.global_position + Vector2(0, 80)
	game._refresh_ui()


func _send_session_summary() -> void:
	if data_logger == null:
		return
	var summary: Dictionary = data_logger.get_session_summary()
	# Send via game's MI WebSocket
	game.mi_send_event("session_end", summary)
	print("Session summary sent: %d trials" % summary.get("total_trials", 0))

func _complete() -> void:
	_send_session_summary()
	game.score = row_index
	game.end_game("%.1fs" % (Time.get_ticks_msec() / 1000.0 - start_time))


# ── UI ──

func _create_ui() -> void:
	ui_container = Control.new()
	ui_container.name = "LevelModeUI"
	ui_container.visible = false
	game.get_node("HUD").add_child(ui_container)

	info_label = Label.new()
	info_label.name = "LevelInfo"
	info_label.position = Vector2(20, 16)
	info_label.size = Vector2(400, 24)
	info_label.add_theme_color_override("font_color", Color(0.25, 0.50, 0.30, 1.0))
	info_label.add_theme_font_size_override("font_size", 16)
	ui_container.add_child(info_label)

	var sid_label: Label = Label.new()
	sid_label.name = "SubjectID"
	sid_label.position = Vector2(20, 0)
	sid_label.size = Vector2(200, 18)
	sid_label.add_theme_color_override("font_color", Color(0.5, 0.6, 0.5, 0.8))
	sid_label.add_theme_font_size_override("font_size", 11)
	ui_container.add_child(sid_label)

	status_label = Label.new()
	status_label.name = "StatusText"
	status_label.position = Vector2(20, 42)
	status_label.size = Vector2(400, 20)
	status_label.add_theme_color_override("font_color", Color(0.40, 0.60, 0.45, 1.0))
	status_label.add_theme_font_size_override("font_size", 14)
	ui_container.add_child(status_label)


# ── Level Select UI ──

var select_ui: Control = null

func show_level_select() -> void:
	if select_ui != null:
		select_ui.visible = true
		return
	select_ui = Control.new()
	select_ui.name = "LevelSelect"
	game.get_node("HUD").add_child(select_ui)

	var vp: Vector2 = game.get_viewport_rect().size
	var panel: ColorRect = ColorRect.new()
	panel.color = Color(0.92, 0.94, 0.88, 0.95)
	panel.size = Vector2(420, 80 + LEVELS.size() * 50)
	panel.position = Vector2((vp.x - 420) * 0.5, (vp.y - panel.size.y) * 0.5)
	select_ui.add_child(panel)

	var title: Label = Label.new()
	title.text = "选择关卡 / Select Level"
	title.position = Vector2(panel.position.x, panel.position.y + 12)
	title.size = Vector2(420, 30)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_color_override("font_color", Color(0.15, 0.25, 0.15, 1.0))
	title.add_theme_font_size_override("font_size", 18)
	select_ui.add_child(title)

	for i: int in range(LEVELS.size()):
		var cfg: Dictionary = LEVELS[i]
		var btn: Button = Button.new()
		var special_text: String = ""
		if cfg["special"] > 0.0:
			special_text = ", 特殊平台%.0f%%" % (cfg["special"] * 100)
		btn.text = "%s / %s  (%d层, %.0fpx%s)" % [cfg["name_cn"], cfg["name_en"], cfg["layers"], cfg["width"], special_text]
		btn.position = Vector2(panel.position.x + 20, panel.position.y + 50 + i * 44)
		btn.size = Vector2(380, 36)
		btn.flat = false
		var sfb: StyleBoxFlat = StyleBoxFlat.new()
		sfb.bg_color = Color(0.30, 0.58, 0.35, 0.9)
		sfb.corner_radius_top_left = 8; sfb.corner_radius_top_right = 8
		sfb.corner_radius_bottom_right = 8; sfb.corner_radius_bottom_left = 8
		btn.add_theme_stylebox_override("normal", sfb)
		var sfh: StyleBoxFlat = sfb.duplicate()
		sfh.bg_color = Color(0.40, 0.70, 0.45, 1.0)
		btn.add_theme_stylebox_override("hover", sfh)
		btn.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0, 1.0))
		btn.add_theme_font_size_override("font_size", 14)
		btn.pressed.connect(_on_level_selected.bind(i))
		select_ui.add_child(btn)

	var close_btn: Button = Button.new()
	close_btn.text = "关闭 / Close"
	close_btn.position = Vector2(panel.position.x + 20, panel.position.y + 50 + LEVELS.size() * 44 + 8)
	close_btn.size = Vector2(380, 36)
	var sfc: StyleBoxFlat = StyleBoxFlat.new()
	sfc.bg_color = Color(0.7, 0.7, 0.7, 0.9)
	sfc.corner_radius_top_left = 8; sfc.corner_radius_top_right = 8
	sfc.corner_radius_bottom_right = 8; sfc.corner_radius_bottom_left = 8
	close_btn.add_theme_stylebox_override("normal", sfc)
	close_btn.add_theme_color_override("font_color", Color(0.2, 0.2, 0.2, 1.0))
	close_btn.add_theme_font_size_override("font_size", 14)
	close_btn.pressed.connect(hide_level_select)
	select_ui.add_child(close_btn)

	select_ui.visible = false


func hide_level_select() -> void:
	if select_ui != null:
		select_ui.visible = false


func _on_level_selected(index: int) -> void:
	current_level = index
	hide_level_select()
	for child in game.platforms_root.get_children():
		child.free()
	game.score = 0
	setup_level()
	game.game_state = 1  # PLAYING
	game.wait_for_accept_release = true
