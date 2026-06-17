extends Control
class_name SpaceMinerHUD

var state_label: Label
var score_label: Label
var round_label: Label
var hint_label: Label


func _ready() -> void:
	score_label = _lbl("💰 0", 18, GlobalConfig.UI_TEXT_PRIMARY)
	score_label.position = Vector2(24, 24)
	score_label.size = Vector2(300, 24)
	add_child(score_label)

	round_label = _lbl("第 1 / 6 轮", 14, GlobalConfig.UI_TEXT_SECONDARY)
	round_label.position = Vector2(24, 50)
	round_label.size = Vector2(200, 20)
	add_child(round_label)

	state_label = _lbl("", 24, GlobalConfig.UI_TEXT_PRIMARY)
	state_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	state_label.position = Vector2(0, 80)
	state_label.size = Vector2(GlobalConfig.GAME_WIDTH, 36)
	add_child(state_label)

	hint_label = _lbl("数字键 1-6 选择目标矿石 | ESC 返回", 12, GlobalConfig.UI_TEXT_SECONDARY)
	hint_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint_label.position = Vector2(0, GlobalConfig.GAME_HEIGHT - 36)
	hint_label.size = Vector2(GlobalConfig.GAME_WIDTH, 20)
	add_child(hint_label)


func _lbl(text: String, font_size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", font_size)
	l.add_theme_color_override("font_color", color)
	return l


func update_state(text: String) -> void:
	state_label.text = text


func update_score(s: int) -> void:
	score_label.text = "💰 %d" % s


func update_round(r: int) -> void:
	round_label.text = "第 %d / 6 轮" % r


func show_final(score: int, collected: int, rating: String) -> void:
	state_label.text = "任务结束 — %s" % rating
	hint_label.text = "总分: %d  采集: %d 个 | Enter 重新开始 | ESC 返回" % [score, collected]
