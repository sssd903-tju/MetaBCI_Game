extends BaseParadigm
## DiveParadigm — 深海下潜

var _spotlight: Spotlight
var _mode: DiveMode
var _hud: Control
var _score_lbl: Label
var _o2_bar: ColorRect
var _o2_bg: ColorRect
var _state_lbl: Label
var _focus_bar: ColorRect
var _focus_bg: ColorRect
var _over: bool = false
var _key_focus: bool = false
var _spawn_timer: float = 0.0
var _specimens: Array = []

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
	_setup_scene()
	_mode.start()
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
	_hud.visible = true
	_spotlight.visible = true
	_state_lbl.text = "采集 5 个标本 | 高专注发现宝藏!"
	_spawn_initial()
	var _t := get_tree().create_timer(3.0); _t.timeout.connect(func(): _state_lbl.text = "")


func _on_paradigm_end() -> void:
	print("[深海] 得分: %d" % _mode.score)


func _on_bci_data(data: Dictionary) -> void:
	_spotlight.focus_ratio = data.get("ratio", 1.5)


# ============================================================
# 基线采集 — 独立全屏界面
# ============================================================

func _create_baseline_screen() -> void:
	_baseline_screen = Control.new()
	_baseline_screen.name = "BaselineScreen"
	_baseline_screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_baseline_screen)

	# 半透明暗色背景
	var overlay := ColorRect.new()
	overlay.color = Color("0A1620", 1.0)
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
	_baseline_title = _make_baseline_label("准备校准", 32, Color("8AC0D0"))
	_baseline_title.position = Vector2(0, 260)
	_baseline_title.size = Vector2(GlobalConfig.GAME_WIDTH, 42)
	_baseline_screen.add_child(_baseline_title)

	# 引导文字
	_baseline_instruction = _make_baseline_label("请放松，保持安静...", 20, Color("6A9AB0"))
	_baseline_instruction.position = Vector2(0, 320)
	_baseline_instruction.size = Vector2(GlobalConfig.GAME_WIDTH, 28)
	_baseline_screen.add_child(_baseline_instruction)

	# 进度条背景
	_baseline_bg = ColorRect.new()
	_baseline_bg.color = Color("1A3A4A", 0.6)
	_baseline_bg.size = Vector2(400, 12)
	_baseline_bg.position = Vector2((GlobalConfig.GAME_WIDTH - 400) / 2.0, 390)
	_baseline_bg.visible = false
	_baseline_screen.add_child(_baseline_bg)

	# 进度条
	_baseline_bar = ColorRect.new()
	_baseline_bar.color = Color("4AC0D0")
	_baseline_bar.size = Vector2(0, 12)
	_baseline_bar.position = _baseline_bg.position
	_baseline_bar.visible = false
	_baseline_screen.add_child(_baseline_bar)

	# 倒计时
	_baseline_countdown = _make_baseline_label("", 48, Color("8AC0D0"))
	_baseline_countdown.position = Vector2(0, 420)
	_baseline_countdown.size = Vector2(GlobalConfig.GAME_WIDTH, 56)
	_baseline_screen.add_child(_baseline_countdown)

	# 底部提示
	var hint := _make_baseline_label("脑电基线采集进行中，完成后自动开始游戏", 14, Color("4A6A7A"))
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
	_hud.visible = false
	_spotlight.visible = false
	# 隐藏所有可收集物
	for child in get_children():
		if child is DiveCollectible:
			child.visible = false


func _hide_baseline_screen() -> void:
	_baseline_screen.visible = false


# ============================================================
# 场景构建
# ============================================================

func _setup_scene() -> void:
	var bg := ColorRect.new(); bg.name = "Background"
	bg.color = Color("020C16"); bg.size = Vector2(GlobalConfig.GAME_WIDTH, GlobalConfig.GAME_HEIGHT)
	bg.position = Vector2.ZERO; add_child(bg); move_child(bg, 0)

	# 海水渐变 — 上层稍亮
	for i in range(5):
		var layer := ColorRect.new()
		var alpha := 0.08 * (5 - i)
		layer.color = Color("1A4A6A", alpha)
		layer.size = Vector2(GlobalConfig.GAME_WIDTH, 60)
		layer.position = Vector2(0, i * 80 + 20)
		add_child(layer)

	# 海底沙床 — 多层
	var sand := ColorRect.new(); sand.color = Color("1A2A30")
	sand.size = Vector2(GlobalConfig.GAME_WIDTH, 70); sand.position = Vector2(0, GlobalConfig.GAME_HEIGHT - 70)
	add_child(sand)
	var sand2 := ColorRect.new(); sand2.color = Color("223A38")
	sand2.size = Vector2(GlobalConfig.GAME_WIDTH, 15); sand2.position = Vector2(0, GlobalConfig.GAME_HEIGHT - 15)
	add_child(sand2)

	# 大岩石
	var rock_colors := ["0A1620", "0C1824", "08131C", "0D1A28"]
	for i in range(8):
		var r := ColorRect.new()
		r.color = Color(rock_colors[i % rock_colors.size()])
		r.size = Vector2(randf_range(50, 160), randf_range(30, 90))
		r.position = Vector2(randf_range(0, GlobalConfig.GAME_WIDTH - 100), randf_range(GlobalConfig.GAME_HEIGHT - 130, GlobalConfig.GAME_HEIGHT - 50))
		add_child(r)

	# 珊瑚
	var coral_colors := ["1A3030", "1E2A2A", "152520", "1A2A2A"]
	for i in range(4):
		var c := ColorRect.new()
		c.color = Color(coral_colors[i])
		c.size = Vector2(randf_range(15, 40), randf_range(40, 90))
		c.position = Vector2(randf_range(0, GlobalConfig.GAME_WIDTH - 40), randf_range(GlobalConfig.GAME_HEIGHT - 140, GlobalConfig.GAME_HEIGHT - 40))
		add_child(c)

	# 海藻 — 细长
	for i in range(8):
		var w := ColorRect.new()
		w.color = Color("1A3A2A" if i % 2 == 0 else "1A2A20")
		w.size = Vector2(randf_range(4, 10), randf_range(50, 120))
		w.position = Vector2(randf_range(0, GlobalConfig.GAME_WIDTH), GlobalConfig.GAME_HEIGHT - 70 - w.size.y)
		add_child(w)

	# 远处气泡
	for i in range(20):
		var b := ColorRect.new()
		b.color = Color("8AC0D0", randf_range(0.05, 0.15))
		var sz := randf_range(2, 5); b.size = Vector2(sz, sz)
		b.position = Vector2(randf_range(0, GlobalConfig.GAME_WIDTH), randf_range(60, GlobalConfig.GAME_HEIGHT - 100))
		add_child(b)

	# 海底散落贝壳
	for i in range(6):
		var sh := ColorRect.new()
		sh.color = Color("3A3A2A", randf_range(0.3, 0.5))
		sh.size = Vector2(randf_range(4, 10), randf_range(3, 6))
		sh.position = Vector2(randf_range(0, GlobalConfig.GAME_WIDTH), randf_range(GlobalConfig.GAME_HEIGHT - 70, GlobalConfig.GAME_HEIGHT - 15))
		add_child(sh)

	_spotlight = Spotlight.new(); _spotlight.z_index = 5
	_spotlight.position = Vector2(GlobalConfig.GAME_WIDTH / 2.0, GlobalConfig.GAME_HEIGHT / 2.0)
	_spotlight.focus_ratio = 50.0
	add_child(_spotlight)

	_mode = DiveMode.new()

	_hud = Control.new(); _hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_hud)

	_score_lbl = _lbl("标本: 0/5  |  💰 0", 16, Color.GOLD)
	_score_lbl.position = Vector2(24, 20); _score_lbl.size = Vector2(300, 24); _hud.add_child(_score_lbl)

	_o2_bg = ColorRect.new(); _o2_bg.color = Color("1A3A4A")
	_o2_bg.size = Vector2(150, 14); _o2_bg.position = Vector2(24, 52); _hud.add_child(_o2_bg)
	_o2_bar = ColorRect.new(); _o2_bar.color = Color("4AC0D0")
	_o2_bar.size = Vector2(150, 14); _o2_bar.position = _o2_bg.position; _hud.add_child(_o2_bar)

	_focus_bg = ColorRect.new(); _focus_bg.color = GlobalConfig.PANEL_BORDER
	_focus_bg.size = Vector2(80, 6); _focus_bg.position = Vector2(GlobalConfig.GAME_WIDTH - 110, 24)
	_hud.add_child(_focus_bg)
	_focus_bar = ColorRect.new(); _focus_bar.color = GlobalConfig.UI_SUCCESS
	_focus_bar.size = Vector2(40, 6); _focus_bar.position = _focus_bg.position; _hud.add_child(_focus_bar)

	_state_lbl = _lbl("", 20, Color("8AC0D0"))
	_state_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_state_lbl.position = Vector2(0, GlobalConfig.GAME_HEIGHT / 2.0 - 40)
	_state_lbl.size = Vector2(GlobalConfig.GAME_WIDTH, 28); _hud.add_child(_state_lbl)

	# 独立基线界面 (最上层)
	_create_baseline_screen()


func _spawn_initial() -> void:
	_spawn_one(DiveCollectible.Type.SPECIMEN, "🐠", 10)
	_spawn_one(DiveCollectible.Type.SPECIMEN, "🐙", 15)
	_spawn_one(DiveCollectible.Type.SPECIMEN, "🦀", 10)
	_spawn_one(DiveCollectible.Type.SPECIMEN, "🐡", 20)
	_spawn_one(DiveCollectible.Type.SPECIMEN, "🦈", 30)
	for i in range(4):
		_spawn_one(DiveCollectible.Type.O2_CANISTER, "🫧", 0)
	# 高专注宝藏
	for i in range(2):
		_spawn_one(DiveCollectible.Type.TREASURE, "💎", 50, true)


func _spawn_one(tp: int, icon: String, val: int, high_focus: bool = false) -> void:
	var f := DiveCollectible.new()
	f.setup(tp, icon, val, _spotlight, high_focus)
	f.position = Vector2(randf_range(60, GlobalConfig.GAME_WIDTH - 60), randf_range(150, GlobalConfig.GAME_HEIGHT - 80))
	f.collected_signal.connect(_on_collect)
	add_child(f)


func _on_collect(item: DiveCollectible) -> void:
	match item.item_type:
		DiveCollectible.Type.SPECIMEN:
			_mode.collect_specimen()
		DiveCollectible.Type.O2_CANISTER:
			_mode.refill_o2()
			_spawn_one(DiveCollectible.Type.O2_CANISTER, "🫧", 0)
		DiveCollectible.Type.TREASURE:
			pass  # 宝藏不重生
	_mode.score += item.item_value
	_score_lbl.text = "标本: %d/5  |  💰 %d" % [_mode.specimens_found, _mode.score]
	_o2_bar.size.x = _o2_bg.size.x * (_mode.oxygen / DiveMode.MAX_O2)


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

	if not _key_focus:
		_spotlight.focus_ratio = float(BCIConnector.latest_focus_pct)

	_mode.elapsed += delta
	var o2_drain := 4.0 if _spotlight.focus_ratio < 35 else 2.0
	_mode.oxygen -= o2_drain * delta
	_o2_bar.size.x = _o2_bg.size.x * clampf(_mode.oxygen / DiveMode.MAX_O2, 0.0, 1.0)
	_o2_bar.color = Color.RED if _mode.oxygen < 25 else Color("4AC0D0")

	_focus_bar.size.x = _focus_bg.size.x * clampf(_spotlight.focus_ratio / 100.0, 0.0, 1.0)
	_focus_bar.color = GlobalConfig.focus_to_color(_spotlight.focus_ratio)

	if _mode.is_complete():
		_over = true
		_state_lbl.text = "%s  得分: %d  |  Enter 再来" % [_mode.get_rating(), _mode.score]
	elif _mode.is_dead():
		_over = true
		_state_lbl.text = "氧气耗尽... 得分: %d  |  Enter 再来" % _mode.score
		_spotlight.focus_ratio = 0


func _lbl(text: String, font_size: int, color: Color) -> Label:
	var lbl := Label.new()
	lbl.text = text
	lbl.add_theme_font_size_override("font_size", font_size)
	lbl.add_theme_color_override("font_color", color)
	return lbl
