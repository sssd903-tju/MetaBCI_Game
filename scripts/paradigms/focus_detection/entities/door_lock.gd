extends Control
class_name DoorLock
## DoorLock — 门锁小谜题: 光照3秒解锁

var door_key: String = ""
var door_label: String = ""
var unlocked: bool = false
var _spotlight: Spotlight = null
var _focus_time: float = 0.0
var _label: Label
var _progress: ColorRect
var _bg: ColorRect
var _lock_icon: Label


func _ready() -> void:
	size = Vector2(140, 60)

	_bg = ColorRect.new()
	_bg.size = size
	_bg.color = Color("1A1212")
	add_child(_bg)

	_lock_icon = Label.new()
	_lock_icon.text = "🔒"
	_lock_icon.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_lock_icon.add_theme_font_size_override("font_size", 24)
	_lock_icon.size = Vector2(40, 40)
	_lock_icon.position = Vector2(8, 10)
	add_child(_lock_icon)

	_label = Label.new()
	_label.text = ""
	_label.add_theme_font_size_override("font_size", 11)
	_label.add_theme_color_override("font_color", Color("8A6A6A"))
	_label.size = Vector2(90, 50)
	_label.position = Vector2(48, 8)
	add_child(_label)

	_progress = ColorRect.new()
	_progress.color = Color.GOLD
	_progress.size = Vector2(0, 4)
	_progress.position = Vector2(0, size.y - 4)
	add_child(_progress)

	modulate.a = 0.0


func setup(label: String, key: String, spot: Spotlight) -> void:
	door_label = label
	door_key = key
	_spotlight = spot
	_label.text = "通往\n" + label


func _process(delta: float) -> void:
	if unlocked: return

	if _spotlight:
		var center := global_position + size / 2.0
		var dist := center.distance_to(_spotlight.global_position)
		modulate.a = lerpf(modulate.a, 1.0 if dist < _spotlight.get_radius() * 1.5 else 0.0, 3.0 * delta)

		if dist < _spotlight.get_radius() * 0.7:
			_focus_time += delta
		else:
			_focus_time = maxf(0.0, _focus_time - delta * 1.5)
	else:
		_focus_time = maxf(0.0, _focus_time - delta)

	_progress.size.x = (_focus_time / 3.0) * size.x
	_label.add_theme_color_override("font_color",
		Color.GOLD if _focus_time > 1.0 else Color("8A6A6A"))

	if _focus_time >= 3.0:
		_unlock()


func is_unlocked() -> bool:
	return unlocked


func _unlock() -> void:
	unlocked = true
	_lock_icon.text = "🔓"
	_label.text = door_label + "\n已开启"
	_label.add_theme_color_override("font_color", Color.GREEN)
	_progress.color = Color.GREEN
	AudioManager.play_hit(8)
	get_parent().on_door_unlocked(door_key)
