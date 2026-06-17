extends Node2D
class_name MoleHole
## MoleHole — 单个洞口：闪烁环 + 贴图地鼠 + 洞口

@export var frequency: float = 10.0
@export var flicker_color := Color.WHITE
@export var hole_radius := 60.0
@export var ring_width := 12.0

var mole_visible: bool = false
var _mole_scale: float = 0.0
var _flicker_brightness: float = 0.5
var _label: Label
var _mole_sprite: Sprite2D


func _ready() -> void:
	_setup_mole_sprite()
	_setup_label()
	queue_redraw()


func _setup_mole_sprite() -> void:
	_mole_sprite = Sprite2D.new()
	_mole_sprite.name = "MoleSprite"
	var tex := load("res://assets/textures/mole.png") as Texture2D
	if tex:
		_mole_sprite.texture = tex
		# 缩放适配洞口
		var target_w := hole_radius * 2.0
		_mole_sprite.scale = Vector2.ONE * (target_w / maxf(tex.get_width(), 1.0))
		# 锚点底部居中
		_mole_sprite.offset = Vector2(0, -tex.get_height() * _mole_sprite.scale.y / 2.0)
	_mole_sprite.position = Vector2(0, -hole_radius * 0.5)
	_mole_sprite.visible = false
	add_child(_mole_sprite)


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
	var t: float = Time.get_ticks_msec() / 1000.0
	_flicker_brightness = (sin(t * frequency * TAU) + 1.0) / 2.0

	if mole_visible and _mole_scale < 1.0:
		_mole_scale = minf(1.0, _mole_scale + delta * 4.0)
	elif not mole_visible and _mole_scale > 0.0:
		_mole_scale = maxf(0.0, _mole_scale - delta * 6.0)

	# 更新地鼠贴图
	_mole_sprite.visible = _mole_scale > 0.01
	_mole_sprite.scale.y = absf(_mole_sprite.scale.x) * _mole_scale  # Y 方向弹出

	queue_redraw()


func _draw() -> void:
	# 闪烁环
	var flicker_c := flicker_color
	flicker_c.a = 0.3 + _flicker_brightness * 0.5
	var ring_outer := hole_radius + ring_width
	draw_circle(Vector2.ZERO, ring_outer, flicker_c)
	draw_circle(Vector2.ZERO, hole_radius, GlobalConfig.BG_WARM_CREAM)

	# 环线
	draw_arc(Vector2.ZERO, hole_radius, 0, TAU, 32, Color.BLACK, 1.0)
	draw_arc(Vector2.ZERO, ring_outer, 0, TAU, 32, Color.BLACK, 1.0)

	# 洞口 (覆盖地鼠底部)
	draw_circle(Vector2.ZERO, hole_radius - 4, Color("3A3028"))


func show_mole() -> void:
	mole_visible = true


func hide_mole() -> void:
	mole_visible = false
