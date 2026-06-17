extends Control
class_name Asteroid

var ore_name: String = ""
var ore_value: int = 0
var ore_icon: String = ""
var flash_on: bool = false
var index: int = 0

var _glow: float = 0.0
var _label: Label
var _value_label: Label
var _glow_rect: ColorRect

const SIZE := 100.0


func _ready() -> void:
	size = Vector2(SIZE, SIZE)
	pivot_offset = size / 2.0

	_glow_rect = ColorRect.new()
	_glow_rect.size = Vector2.ZERO
	_glow_rect.color = Color.GOLD
	add_child(_glow_rect)

	_label = Label.new()
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_label.size = Vector2(SIZE, SIZE * 0.6)
	_label.position = Vector2(0, -10)
	_label.add_theme_font_size_override("font_size", 40)
	add_child(_label)

	_value_label = Label.new()
	_value_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_value_label.size = Vector2(SIZE, 24)
	_value_label.position = Vector2(0, SIZE - 30)
	_value_label.add_theme_font_size_override("font_size", 14)
	_value_label.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_PRIMARY)
	add_child(_value_label)


func setup(nm: String, icon: String, val: int) -> void:
	ore_name = nm
	ore_icon = icon
	ore_value = val
	_label.text = icon
	_value_label.text = "%d pts" % val


func set_flash(on: bool) -> void:
	flash_on = on


func _process(delta: float) -> void:
	if flash_on:
		_glow = minf(1.0, _glow + delta * 10.0)
	else:
		_glow = maxf(0.0, _glow - delta * 8.0)

	_glow_rect.size = Vector2(SIZE, SIZE) + Vector2.ONE * 16.0 * _glow
	_glow_rect.position = -Vector2.ONE * 8.0 * _glow
	_glow_rect.color.a = _glow * 0.4
