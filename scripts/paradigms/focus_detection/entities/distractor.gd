extends Node2D
class_name Distractor
## Distractor — 单个干扰物实体，浮动彩色圆圈

var _radius: float
var _color: Color
var _velocity: Vector2
var _lifetime: float
var _age: float = 0.0
var _base_y: float
var _wave_amp: float
var _wave_freq: float
var _wave_offset: float

func setup(radius: float, color: Color, velocity: Vector2, lifetime: float) -> void:
	_radius = radius
	_color = color
	_velocity = velocity
	_lifetime = lifetime
	_base_y = position.y
	_wave_amp = randf_range(20.0, 60.0)
	_wave_freq = randf_range(1.5, 3.0)
	_wave_offset = randf() * TAU


func _process(delta: float) -> void:
	_age += delta
	if _age >= _lifetime:
		queue_free()
		return

	# 水平移动 + 正弦波浮动
	position.x += _velocity.x * delta
	position.y = _base_y + sin(_age * _wave_freq + _wave_offset) * _wave_amp

	# 渐入渐出
	var alpha: float = 1.0
	if _age < 0.3:
		alpha = _age / 0.3
	elif _age > _lifetime - 0.3:
		alpha = (_lifetime - _age) / 0.3
	modulate.a = clampf(alpha, 0.0, 1.0)


func _draw() -> void:
	draw_circle(Vector2.ZERO, _radius, _color)
