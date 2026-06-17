extends Node2D
class_name MoleHole
## MoleHole — 闪烁环 + 地鼠 + 洞口

@export var frequency: float = 10.0
@export var flicker_color := Color.WHITE
@export var hole_radius := 60.0
@export var ring_width := 12.0

var mole_visible: bool = false
var _mole_progress: float = 0.0  # 0=隐藏, 1=完全冒出
var _flicker_brightness: float = 0.5
var _label: Label
var _mole_sprite: Sprite2D
var _base_scale: float = 1.0
var _hidden_y: float       # 藏在地下时的 Y
var _shown_y: float        # 完全冒出时的 Y


func _ready() -> void:
	_setup_mole_sprite()
	_setup_label()
	queue_redraw()


func _setup_mole_sprite() -> void:
	_mole_sprite = Sprite2D.new()
	_mole_sprite.name = "MoleSprite"
	var tex: Texture2D = load("res://assets/textures/mole.png")
	if tex:
		_mole_sprite.texture = tex
		var target_w := hole_radius * 3.5
		_base_scale = target_w / maxf(tex.get_width(), 1.0)
		_mole_sprite.scale = Vector2.ONE * _base_scale
		_shown_y = -tex.get_height() * _base_scale / 2.0 + hole_radius * 0.42
		_hidden_y = hole_radius * 0.3
	_mole_sprite.position = Vector2(0, _hidden_y)
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

	# 垂直滑动动画
	if mole_visible and _mole_progress < 1.0:
		_mole_progress = minf(1.0, _mole_progress + delta * 5.0)
	elif not mole_visible and _mole_progress > 0.0:
		_mole_progress = maxf(0.0, _mole_progress - delta * 6.0)

	# ease-out 冒出, ease-in 缩回
	var eased: float
	if mole_visible:
		eased = 1.0 - pow(1.0 - _mole_progress, 3.0)
	else:
		eased = pow(_mole_progress, 2.0)

	_mole_sprite.visible = _mole_progress > 0.01
	_mole_sprite.position.y = lerpf(_hidden_y, _shown_y, eased)
	_mole_sprite.modulate.a = clampf(eased * 1.3, 0.0, 1.0)

	queue_redraw()


func _draw() -> void:
	# 闪烁环
	var flicker_c := flicker_color
	flicker_c.a = 0.3 + _flicker_brightness * 0.5
	var ring_outer := hole_radius + ring_width
	draw_circle(Vector2.ZERO, ring_outer, flicker_c)
	draw_circle(Vector2.ZERO, hole_radius, GlobalConfig.BG_WARM_CREAM)
	draw_arc(Vector2.ZERO, hole_radius, 0, TAU, 32, Color.BLACK, 1.0)
	draw_arc(Vector2.ZERO, ring_outer, 0, TAU, 32, Color.BLACK, 1.0)
	draw_circle(Vector2.ZERO, hole_radius - 4, Color("3A3028"))


func show_mole() -> void:
	mole_visible = true


func hide_mole() -> void:
	mole_visible = false
