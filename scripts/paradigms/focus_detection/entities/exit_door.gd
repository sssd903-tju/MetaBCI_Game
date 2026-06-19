extends Control
class_name ExitDoor
## ExitDoor — 出口门, 光照锁孔 + Enter 逃脱

var _spotlight: Spotlight = null
var _bg: ColorRect
var _lock_label: Label
var _active: bool = false
var _escaped: bool = false

signal door_escaped()


func _ready() -> void:
	size = Vector2(200, 300)
	position = Vector2(GlobalConfig.GAME_WIDTH - 220, (GlobalConfig.GAME_HEIGHT - 300) / 2.0)

	_bg = ColorRect.new()
	_bg.size = size
	_bg.color = Color("2A1A0A")
	add_child(_bg)

	# 门框
	var frame := ColorRect.new()
	frame.color = Color("4A3020")
	frame.size = Vector2(200, 10)
	frame.position = Vector2(0, 0)
	add_child(frame)
	var frame2 := frame.duplicate()
	frame2.position.y = 290
	add_child(frame2)

	_lock_label = Label.new()
	_lock_label.text = "🔒"
	_lock_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_lock_label.add_theme_font_size_override("font_size", 40)
	_lock_label.size = Vector2(200, 60)
	_lock_label.position = Vector2(0, 120)
	add_child(_lock_label)

	modulate.a = 0.0


func activate(s: Spotlight) -> void:
	_spotlight = s
	_active = true


func _process(delta: float) -> void:
	if not _active or _escaped:
		return

	if _spotlight:
		var center := global_position + size / 2.0
		var dist := center.distance_to(_spotlight.global_position)
		var radius := _spotlight.get_radius()
		modulate.a = lerpf(modulate.a, 1.0 if dist < radius * 1.2 else 0.1, 3.0 * delta)


func try_escape() -> bool:
	if not _active or _escaped:
		return false

	if _spotlight:
		var center := global_position + size / 2.0
		var dist := center.distance_to(_spotlight.global_position)
		if dist < _spotlight.get_radius() * 0.8:
			_escaped = true
			_lock_label.text = "🚪"
			door_escaped.emit()
			return true
	return false
