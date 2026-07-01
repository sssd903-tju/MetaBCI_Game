extends Control
class_name ArcheryHUD
## HUD — 凝神一矢 界面

var _state_label: Label
var _round_label: Label
var _score_label: Label
var _timer_bar: ColorRect
var _timer_bg: ColorRect
var _result_label: Label
var _focus_bar: ColorRect
var _focus_bg: ColorRect
var _focus_label: Label


func _ready() -> void:
	_setup()


func _setup() -> void:
	# 轮次 + 分数 — 左上
	var info_panel := VBoxContainer.new()
	info_panel.position = Vector2(24, 24)
	info_panel.add_theme_constant_override("separation", 4)
	add_child(info_panel)

	_round_label = _make_label("第 1 / 10 轮", 18, GlobalConfig.UI_TEXT_PRIMARY)
	info_panel.add_child(_round_label)

	_score_label = _make_label("总分: 0", 16, GlobalConfig.UI_TEXT_SECONDARY)
	info_panel.add_child(_score_label)

	# 状态文字 — 居中靠上
	_state_label = _make_label("", 24, GlobalConfig.UI_TEXT_PRIMARY)
	_state_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_state_label.position = Vector2(0, 100)
	_state_label.size = Vector2(GlobalConfig.GAME_WIDTH, 36)
	add_child(_state_label)

	# 计时条 — 靶子上方
	_timer_bg = ColorRect.new()
	_timer_bg.color = GlobalConfig.PANEL_BORDER
	_timer_bg.size = Vector2(300, 8)
	_timer_bg.position = Vector2((GlobalConfig.GAME_WIDTH - 300) / 2.0, 145)
	add_child(_timer_bg)

	_timer_bar = ColorRect.new()
	_timer_bar.color = GlobalConfig.PLATFORM_NORMAL
	_timer_bar.size = Vector2(300, 8)
	_timer_bar.position = _timer_bg.position
	add_child(_timer_bar)

	# 专注度条 — 右侧
	_focus_label = _make_label("专注度: --", 13, GlobalConfig.UI_TEXT_SECONDARY)
	_focus_label.position = Vector2(GlobalConfig.GAME_WIDTH - 180, 24)
	_focus_label.size = Vector2(160, 18)
	add_child(_focus_label)

	_focus_bg = ColorRect.new()
	_focus_bg.color = GlobalConfig.PANEL_BORDER
	_focus_bg.size = Vector2(160, 10)
	_focus_bg.position = Vector2(GlobalConfig.GAME_WIDTH - 180, 46)
	add_child(_focus_bg)

	_focus_bar = ColorRect.new()
	_focus_bar.color = GlobalConfig.UI_SUCCESS
	_focus_bar.size = Vector2(0, 10)
	_focus_bar.position = _focus_bg.position
	add_child(_focus_bar)

	# 结果弹窗 — 先隐藏
	_result_label = _make_label("", 22, GlobalConfig.UI_ACCENT)
	_result_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_result_label.position = Vector2(0, GlobalConfig.GAME_HEIGHT / 2.0 - 230)
	_result_label.size = Vector2(GlobalConfig.GAME_WIDTH, 30)
	add_child(_result_label)


func _make_label(text: String, size: int, color: Color) -> Label:
	var lbl := Label.new()
	lbl.text = text
	lbl.add_theme_font_size_override("font_size", size)
	lbl.add_theme_color_override("font_color", color)
	return lbl


# --- 更新接口 ---

func update_state(text: String) -> void:
	_state_label.text = text


func update_round(round_num: int) -> void:
	_round_label.text = "第 %d / %d 轮" % [round_num, ArcheryMode.TOTAL_ROUNDS]


func update_score(total: int) -> void:
	_score_label.text = "总分: %d" % total


func update_timer(progress: float) -> void:
	_timer_bar.size.x = _timer_bg.size.x * clampf(progress, 0.0, 1.0)


func show_timer(visible: bool) -> void:
	_timer_bg.visible = visible
	_timer_bar.visible = visible


func update_focus(ratio: float) -> void:
	var pct := clampf(ratio / 100.0, 0.0, 1.0)
	_focus_bar.size.x = _focus_bg.size.x * pct
	_focus_bar.color = GlobalConfig.focus_to_color(ratio)
	_focus_label.text = "专注度: %d%%" % int(ratio)


func show_result(result: Dictionary) -> void:
	var ring: int = result.get("ring", 0)
	var points: int = result.get("total_points", 0)
	var combo_count: int = result.get("combo_count", 0)
	var is_bullseye: bool = result.get("is_bullseye", false)

	if ring == 0:
		_result_label.text = "脱靶！  +0  连击中断"
		_result_label.add_theme_color_override("font_color", GlobalConfig.UI_DANGER)
	else:
		var text := "%d 环！  +%d" % [ring, points]
		if is_bullseye:
			text = "🎯 " + text + "  十环！"
		if combo_count >= 2:
			text += "  ×%d 连击！" % combo_count
		_result_label.text = text
		_result_label.add_theme_color_override("font_color", GlobalConfig.focus_to_color(float(ring) * 0.4))


func hide_result() -> void:
	_result_label.text = ""


func show_final(total: int, rating: String, best_combo: int, bullseyes: int) -> void:
	_state_label.position = Vector2(0, 50)
	_state_label.text = "游戏结束"
	_state_label.add_theme_font_size_override("font_size", 28)
	_result_label.position = Vector2(0, 95)
	var text := "总分: %d  —  %s" % [total, rating]
	if best_combo >= 2:
		text += "\n最佳连击: ×%d" % best_combo
	if bullseyes > 0:
		text += "  |  🎯 ×%d" % bullseyes
	_result_label.text = text
	_result_label.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_PRIMARY)

	var hint := Label.new()
	hint.name = "FinalHint"
	hint.text = "按 Enter 重新开始 | ESC 返回"
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint.position = Vector2(0, 190)
	hint.size = Vector2(GlobalConfig.GAME_WIDTH, 24)
	hint.add_theme_font_size_override("font_size", 14)
	hint.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_SECONDARY)
	add_child(hint)
