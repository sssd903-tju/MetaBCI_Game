extends BaseParadigm
## FocusGame — 专注度检测范式主控制器
##
## 游戏规则:
##   - 玩家自动向右移动，需要在平台上跳跃前进
##   - 专注度高 → 跳跃更高、平台更稳定
##   - 专注度低 → 脆弱平台碎裂、移动平台加速
##   - 掉出屏幕 → 游戏结束
##
## 计分: 生存时间 × 专注度系数

# ============================================================
# 动态节点引用
# ============================================================

var _player: FocusPlayer = null
var _spawner: PlatformSpawner = null
var _camera: Camera2D = null
var _hud: Control = null

# ============================================================
# 游戏状态
# ============================================================

var _score := 0.0
var _survival_time := 0.0
var _is_game_over := false
var _platforms_broken := 0
var _current_focus := 1.5

# ============================================================
# 颜色引用
# ============================================================

var bg_color := GlobalConfig.BG_WARM_CREAM


func _ready() -> void:
	paradigm_type = GlobalConfig.ParadigmType.FOCUS_DETECTION
	super._ready()


func _on_paradigm_start() -> void:
	print("[FocusGame] 🎯 专注度检测范式启动")
	_setup_background()
	_setup_camera()
	_create_game_nodes()
	_setup_hud()

	_is_game_over = false
	_score = 0.0
	_survival_time = 0.0
	_platforms_broken = 0


func _on_paradigm_end() -> void:
	print("[FocusGame] 专注度检测范式结束，最终分数: %.1f" % _score)


func _on_bci_data(data: Dictionary) -> void:
	"""接收 BCI 专注度数据"""
	_current_focus = data.get("ratio", 1.5)

	# 应用到玩家
	if _player:
		_player.apply_focus(_current_focus)

	# 应用到平台
	if _spawner:
		_spawner.apply_focus_to_platforms(_current_focus)


# ============================================================
# 场景构建
# ============================================================

func _setup_background() -> void:
	var bg := ColorRect.new()
	bg.name = "Background"
	bg.color = bg_color
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	move_child(bg, 0)


func _setup_camera() -> void:
	_camera = Camera2D.new()
	_camera.name = "Camera2D"
	_camera.position = Vector2(400, GlobalConfig.GAME_HEIGHT / 2.0)
	_camera.zoom = Vector2(1.0, 1.0)
	_camera.make_current()
	add_child(_camera)


func _setup_hud() -> void:
	_hud = Control.new()
	_hud.name = "HUD"
	_hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_hud)

	# 专注度指示条
	var focus_bar := FocusBar.new()
	focus_bar.name = "FocusBar"
	_hud.add_child(focus_bar)

	# 分数显示
	var score_label := Label.new()
	score_label.name = "ScoreLabel"
	score_label.text = "分数: 0"
	score_label.position = Vector2(GlobalConfig.GAME_WIDTH - 200, 24)
	score_label.size = Vector2(180, 30)
	score_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	score_label.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_PRIMARY)
	score_label.add_theme_font_size_override("font_size", 20)
	_hud.add_child(score_label)

	# 提示信息
	var hint := Label.new()
	hint.name = "HintLabel"
	hint.text = "保持专注以稳定平台 | 按 ESC 返回"
	hint.position = Vector2(20, GlobalConfig.GAME_HEIGHT - 40)
	hint.size = Vector2(400, 30)
	hint.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_SECONDARY)
	hint.add_theme_font_size_override("font_size", 12)
	_hud.add_child(hint)


# ============================================================
# 游戏循环
# ============================================================

func _process(delta: float) -> void:
	if _is_game_over:
		return

	_survival_time += delta

	# 计分（生存时间 × 专注度系数）
	var focus_multiplier := clampf(_current_focus / 2.0, 0.5, 2.0)
	_score += delta * 10.0 * focus_multiplier

	# 更新 HUD
	_update_hud()

	# 背景色微调（专注度高时背景更明亮）
	var bg_target := bg_color
	if _current_focus >= GlobalConfig.FOCUS_HIGH_THRESHOLD:
		bg_target = bg_color.lightened(0.03)
	var bg_rect := get_node_or_null("Background") as ColorRect
	if bg_rect:
		bg_rect.color = bg_rect.color.lerp(bg_target, 1.0 * delta)

	# 摄像机跟随玩家
	if _player and _camera:
		_camera.position.x = _player.position.x + 200


func _update_hud() -> void:
	var score_label := _hud.get_node_or_null("ScoreLabel") as Label
	if score_label:
		score_label.text = "分数: %.0f" % _score


# ============================================================
# 游戏事件
# ============================================================

func _on_player_died() -> void:
	"""玩家掉落死亡"""
	if _is_game_over:
		return
	_is_game_over = true
	print("[FocusGame] 玩家掉落！最终分数: %.0f" % _score)

	# 发送游戏结束事件
	BCIConnector.send_game_event("game_over", {
		"score": _score,
		"survival_time": _survival_time,
		"platforms_broken": _platforms_broken,
	})

	_show_game_over_screen()


func _on_platform_broken() -> void:
	"""平台碎裂计数"""
	_platforms_broken += 1
	BCIConnector.send_game_event("platform_break", {
		"total_broken": _platforms_broken,
	})


func _show_game_over_screen() -> void:
	"""显示游戏结束画面"""
	var overlay := ColorRect.new()
	overlay.name = "GameOverOverlay"
	overlay.color = Color(0, 0, 0, 0.5)
	overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_hud.add_child(overlay)

	var panel := Panel.new()
	panel.name = "GameOverPanel"
	panel.size = Vector2(400, 250)
	panel.position = Vector2(
		(GlobalConfig.GAME_WIDTH - 400) / 2.0,
		(GlobalConfig.GAME_HEIGHT - 250) / 2.0
	)
	var panel_style := StyleBoxFlat.new()
	panel_style.bg_color = GlobalConfig.PANEL_BG
	panel_style.border_color = GlobalConfig.UI_ACCENT
	panel_style.border_width_left = 2
	panel_style.border_width_right = 2
	panel_style.border_width_top = 2
	panel_style.border_width_bottom = 2
	panel_style.corner_radius_top_left = 16
	panel_style.corner_radius_top_right = 16
	panel_style.corner_radius_bottom_right = 16
	panel_style.corner_radius_bottom_left = 16
	panel.add_theme_stylebox_override("panel", panel_style)
	_hud.add_child(panel)

	var title := Label.new()
	title.text = "游戏结束"
	title.position = Vector2(0, 30)
	title.size = Vector2(400, 40)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_PRIMARY)
	title.add_theme_font_size_override("font_size", 28)
	panel.add_child(title)

	var score_text := Label.new()
	score_text.text = "最终分数: %.0f\n生存时间: %.1f 秒\n碎裂平台: %d" % [_score, _survival_time, _platforms_broken]
	score_text.position = Vector2(0, 80)
	score_text.size = Vector2(400, 70)
	score_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	score_text.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_SECONDARY)
	score_text.add_theme_font_size_override("font_size", 16)
	panel.add_child(score_text)

	var restart_btn := Button.new()
	restart_btn.text = "重新开始 (R)"
	restart_btn.position = Vector2(100, 170)
	restart_btn.size = Vector2(200, 40)
	restart_btn.pressed.connect(_restart_game)
	panel.add_child(restart_btn)

	var menu_btn := Button.new()
	menu_btn.text = "返回菜单 (ESC)"
	menu_btn.position = Vector2(100, 215)
	menu_btn.size = Vector2(200, 30)
	menu_btn.flat = true
	menu_btn.pressed.connect(ParadigmManager.go_to_main_menu)
	panel.add_child(menu_btn)


func _restart_game() -> void:
	"""重新开始游戏"""
	# 清理旧节点
	for child in get_children():
		if child.name not in ["Background"]:
			child.queue_free()

	# 等待一帧后重建
	await get_tree().process_frame
	_on_paradigm_start()
	_create_game_nodes()


func _create_game_nodes() -> void:
	"""创建游戏节点"""
	# 玩家
	_player = FocusPlayer.new()
	_player.name = "Player"
	_player.position = Vector2(200, 500)
	add_child(_player)

	# 平台生成器
	_spawner = PlatformSpawner.new()
	_spawner.name = "PlatformSpawner"
	add_child(_spawner)

	# 初始地面平台
	var ground := FocusPlatform.new()
	ground.name = "GroundPlatform"
	ground.platform_type = FocusPlatform.PlatformType.NORMAL
	ground.position = Vector2(200, 580)
	add_child(ground)


# ============================================================
# 键盘输入
# ============================================================

func _input(event: InputEvent) -> void:
	if _is_game_over:
		if event.is_action_pressed("ui_accept"):
			_restart_game()
			get_viewport().set_input_as_handled()
		elif event.is_action_pressed("ui_cancel"):
			ParadigmManager.go_to_main_menu()
			get_viewport().set_input_as_handled()
		return

	if event.is_action_pressed("ui_accept"):
		# 空格键跳跃
		if _player:
			_player.jump()
		get_viewport().set_input_as_handled()

	elif event.is_action_pressed("ui_cancel"):
		# ESC 返回主菜单
		ParadigmManager.go_to_main_menu()
		get_viewport().set_input_as_handled()

	# 调试：模拟专注度
	elif event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_1:
				BCIConnector.simulate_focus(0.8)
			KEY_2:
				BCIConnector.simulate_focus(2.0)
			KEY_3:
				BCIConnector.simulate_focus(3.2)
