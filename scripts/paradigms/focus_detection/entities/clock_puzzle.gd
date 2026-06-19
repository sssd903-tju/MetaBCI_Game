extends Control
class_name ClockPuzzle
## ClockPuzzle — 挂钟: 光照3秒读取时间 → 2位数字

var hour_digit: int = 0
var min_digit: int = 0   # 分钟÷10
var solved: bool = false
var _spotlight: Spotlight = null
var _focus_time: float = 0.0
var _label: Label
var _bg: ColorRect
var _progress: ColorRect


func _ready() -> void:
	size = Vector2(180, 200)
	_bg = ColorRect.new()
	_bg.size = size
	_bg.color = Color("1A1612")
	add_child(_bg)

	# 钟面
	var clock_face := ColorRect.new()
	clock_face.color = Color("2A2218")
	clock_face.size = Vector2(140, 140)
	clock_face.position = Vector2(20, 10)
	add_child(clock_face)

	_label = Label.new()
	_label.text = "🕐"
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_label.add_theme_font_size_override("font_size", 60)
	_label.size = Vector2(140, 140)
	_label.position = Vector2(20, 10)
	add_child(_label)

	_progress = ColorRect.new()
	_progress.color = Color.GOLD
	_progress.size = Vector2(0, 6)
	_progress.position = Vector2(20, 160)
	add_child(_progress)

	var hint := Label.new()
	hint.text = "光照3秒读取时间"
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint.add_theme_font_size_override("font_size", 11)
	hint.add_theme_color_override("font_color", Color("5A5A5A"))
	hint.size = Vector2(180, 20)
	hint.position = Vector2(0, 172)
	add_child(hint)

	modulate.a = 0.0


func setup(hour: int, minute_tens: int, s: Spotlight) -> void:
	hour_digit = hour
	min_digit = minute_tens
	_spotlight = s


func get_digits() -> Array:
	return [hour_digit, min_digit]


func _process(delta: float) -> void:
	if solved:
		return
	if _spotlight:
		var center := global_position + size / 2.0
		var dist := center.distance_to(_spotlight.global_position)
		var radius := _spotlight.get_radius()
		modulate.a = lerpf(modulate.a, 1.0 if dist < radius else 0.0, 3.0 * delta)

		if dist < radius * 0.6:
			_focus_time += delta
		else:
			_focus_time = maxf(0.0, _focus_time - delta * 2.0)
	else:
		_focus_time = 0.0

	_progress.size.x = (_focus_time / 3.0) * 140.0

	if _focus_time >= 3.0 and not solved:
		solved = true
		_label.text = "%d:%d0" % [hour_digit, min_digit]
		_progress.color = Color.GREEN
		AudioManager.play_hit(8)
		get_parent().on_clock_solved()
