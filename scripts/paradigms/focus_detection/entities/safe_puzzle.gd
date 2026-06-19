extends Control
class_name SafePuzzle
## SafePuzzle — 保险箱转盘: 光照看到划痕→两个数字

var digit1: int = 0
var digit2: int = 0
var solved: bool = false
var _spotlight: Spotlight = null
var _reveal: float = 0.0   # 0→1 逐渐显现
var _label: Label
var _bg: ColorRect


func _ready() -> void:
	size = Vector2(200, 200)

	_bg = ColorRect.new()
	_bg.size = size
	_bg.color = Color("1A1612")
	add_child(_bg)

	_label = Label.new()
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_label.size = size
	_label.add_theme_font_size_override("font_size", 14)
	_label.add_theme_color_override("font_color", Color("5A5A5A"))
	_label.text = "🔒\n保险箱"
	add_child(_label)

	var hint := Label.new()
	hint.text = "光照查看划痕"
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint.add_theme_font_size_override("font_size", 11)
	hint.add_theme_color_override("font_color", Color("3A3A3A"))
	hint.size = Vector2(200, 16)
	hint.position = Vector2(0, size.y + 4)
	add_child(hint)

	modulate.a = 0.0


func setup(d1: int, d2: int, spot: Spotlight) -> void:
	digit1 = d1
	digit2 = d2
	_spotlight = spot


func get_digits() -> Array:
	return [digit1, digit2]


func _process(delta: float) -> void:
	if solved:
		return
	if _spotlight:
		var center := global_position + size / 2.0
		var dist := center.distance_to(_spotlight.global_position)
		modulate.a = lerpf(modulate.a, 1.0 if dist < _spotlight.get_radius() else 0.0, 3.0 * delta)

		if dist < _spotlight.get_radius() * 0.6:
			_reveal = minf(1.0, _reveal + delta * 0.5)
		else:
			_reveal = maxf(0.0, _reveal - delta)

	_update_display()


func _update_display() -> void:
	if _reveal > 0.8:
		_label.text = "🔓\n%d  %d" % [digit1, digit2]
		_label.add_theme_color_override("font_color", Color.GOLD)
		if not solved:
			solved = true
			AudioManager.play_hit(8)
			get_parent().on_safe_solved()
	elif _reveal > 0.4:
		_label.text = "🔒\n?  ?"
		_label.add_theme_color_override("font_color", Color("8A8A6A"))
	else:
		_label.text = "🔒\n保险箱"
		_label.add_theme_color_override("font_color", Color("5A5A5A"))
