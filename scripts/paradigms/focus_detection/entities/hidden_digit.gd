extends Node2D
class_name HiddenDigit
## HiddenDigit — 隐藏数字, 光照到才可见

@export var digit: int = 1
@export var index: int = 0

var found: bool = false
var _label: Label
var _spotlight: Spotlight = null

const DIGIT_COLOR := Color("F0C040")  # 金色


func _ready() -> void:
	_label = Label.new()
	_label.text = str(digit)
	_label.add_theme_font_size_override("font_size", 48)
	_label.add_theme_color_override("font_color", DIGIT_COLOR)
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_label.size = Vector2(60, 60)
	_label.position = -_label.size / 2.0
	_label.modulate.a = 0.0
	add_child(_label)


func set_spotlight(s: Spotlight) -> void:
	_spotlight = s


func _process(_delta: float) -> void:
	if found or _spotlight == null or _label == null:
		return

	var dist := global_position.distance_to(_spotlight.global_position)
	var radius := _spotlight.get_radius()

	# 光照到 → 显示, 越近越亮
	if dist < radius:
		var alpha := 1.0 - (dist / radius)
		alpha = clampf(alpha * 2.0, 0.0, 1.0)  # 加强对比
		_label.modulate.a = alpha

		# 在光中心附近 → 被发现
		if dist < radius * 0.3:
			found = true
			_label.modulate.a = 1.0
			# 闪烁提示
			var tween := create_tween()
			tween.tween_property(_label, "modulate:a", 0.5, 0.2)
			tween.tween_property(_label, "modulate:a", 1.0, 0.2)
			# 通知父节点
			get_parent().on_digit_found(index)
	else:
		_label.modulate.a = maxf(0.0, _label.modulate.a - 2.0 * _delta)
