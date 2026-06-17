extends Node2D
class_name MoleHole
## MoleHole — 单个洞口：闪烁环 + 地鼠 + 洞口

# SSVEP 闪烁频率 (Hz)
@export var frequency: float = 10.0

# 闪烁颜色
@export var flicker_color := Color.WHITE

# 洞口尺寸
@export var hole_radius := 60.0
@export var ring_width := 12.0

var mole_visible: bool = false
var _mole_scale: float = 0.0  # 0=隐藏, 1=完全冒出
var _flicker_brightness: float = 0.5
var _label: Label


func _ready() -> void:
	_setup_label()
	queue_redraw()


func _setup_label() -> void:
	_label = Label.new()
	_label.text = "%.1f Hz" % frequency
	_label.add_theme_font_size_override("font_size", 12)
	_label.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_SECONDARY)
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_label.position = Vector2(-30, hole_radius + ring_width + 8)
	_label.size = Vector2(60, 18)
	add_child(_label)


func _process(delta: float) -> void:
	# 正弦波闪烁
	var t: float = Time.get_ticks_msec() / 1000.0
	_flicker_brightness = (sin(t * frequency * TAU) + 1.0) / 2.0

	# 地鼠动画
	if mole_visible and _mole_scale < 1.0:
		_mole_scale = minf(1.0, _mole_scale + delta * 4.0)
	elif not mole_visible and _mole_scale > 0.0:
		_mole_scale = maxf(0.0, _mole_scale - delta * 6.0)

	queue_redraw()


func _draw() -> void:
	# 闪烁环
	var flicker_c := flicker_color
	flicker_c.a = 0.3 + _flicker_brightness * 0.5
	var ring_outer := hole_radius + ring_width
	draw_circle(Vector2.ZERO, ring_outer, flicker_c)
	# 环内侧挖空
	draw_circle(Vector2.ZERO, hole_radius, GlobalConfig.BG_WARM_CREAM)

	# 环线
	draw_arc(Vector2.ZERO, hole_radius, 0, TAU, 32, Color.BLACK, 1.0)
	draw_arc(Vector2.ZERO, ring_outer, 0, TAU, 32, Color.BLACK, 1.0)

	# 洞口 (深色椭圆)
	draw_circle(Vector2.ZERO, hole_radius - 4, Color("3A3028"))

	# 地鼠 (棕色圆，随 _mole_scale 冒出)
	if _mole_scale > 0.01:
		var mr := hole_radius * 0.55 * _mole_scale
		draw_circle(Vector2(0, -hole_radius * 0.3 * _mole_scale), mr, Color("8B6914"))
		# 眼睛
		if _mole_scale > 0.5:
			var eye_y := -hole_radius * 0.3 * _mole_scale - mr * 0.2
			draw_circle(Vector2(-mr * 0.3, eye_y), mr * 0.2, Color.WHITE)
			draw_circle(Vector2(mr * 0.3, eye_y), mr * 0.2, Color.WHITE)
			draw_circle(Vector2(-mr * 0.3, eye_y), mr * 0.1, Color.BLACK)
			draw_circle(Vector2(mr * 0.3, eye_y), mr * 0.1, Color.BLACK)


## 显示地鼠
func show_mole() -> void:
	mole_visible = true


## 隐藏地鼠
func hide_mole() -> void:
	mole_visible = false
