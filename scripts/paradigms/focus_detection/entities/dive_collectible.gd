extends Control
class_name DiveCollectible

enum Type { SPECIMEN, O2_CANISTER, TREASURE }

var item_type: int = Type.SPECIMEN
var item_icon: String = ""
var item_value: int = 10
var collected: bool = false
var _spotlight: Spotlight = null
var _label: Label
var _pulse_offset: float
var _near_time: float = 0.0  # 光照累计时间
var _require_high_focus: bool = false

signal collected_signal(item: DiveCollectible)
var _pending_icon: String = ""


func _ready() -> void:
	size = Vector2(50, 50)
	_pulse_offset = randf() * TAU
	_label = Label.new()
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_label.size = size
	_label.add_theme_font_size_override("font_size", 28)
	add_child(_label)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	if _pending_icon != "":
		_label.text = _pending_icon; _pending_icon = ""


func setup(tp: int, icon: String, val: int, spot: Spotlight, high_focus_only: bool = false) -> void:
	item_type = tp; item_icon = icon; item_value = val
	_spotlight = spot; _require_high_focus = high_focus_only
	if _label: _label.text = icon
	else: _pending_icon = icon


func _process(delta: float) -> void:
	if collected:
		modulate.a = maxf(0.0, modulate.a - 4.0 * delta)
		if modulate.a <= 0.0: queue_free()
		return

	if _spotlight == null: return

	var d := global_position.distance_to(_spotlight.global_position)
	var r := _spotlight.get_radius()
	var ratio := _spotlight.focus_ratio

	# 宝藏: 只有高专注可见
	if _require_high_focus:
		if ratio >= GlobalConfig.FOCUS_HIGH_THRESHOLD:
			modulate.a = lerpf(modulate.a, 1.0, 5.0 * delta)
		else:
			modulate.a = lerpf(modulate.a, 0.0, 5.0 * delta)
			_near_time = 0.0
			return
	else:
		modulate.a = 1.0

	# 脉冲发光
	var p := (sin(Time.get_ticks_msec() / 1000.0 * 3.0 + _pulse_offset) + 1.0) / 2.0
	match item_type:
		Type.SPECIMEN:   _label.modulate = Color.GOLD; _label.modulate.a = 0.3 + p * 0.7
		Type.O2_CANISTER: _label.modulate = Color.GREEN; _label.modulate.a = 0.3 + p * 0.7
		Type.TREASURE:    _label.modulate = Color.ORANGE; _label.modulate.a = 0.5 + p * 0.5
	position.y += sin(Time.get_ticks_msec() / 1000.0 * 2.0 + _pulse_offset) * 0.5

	# 自动收集: 光照到 + 范围内
	if d < r * 0.7:
		_near_time += delta
		if _near_time > 0.5:
			collected = true
			collected_signal.emit(self)
			AudioManager.play_combo(1)
	else:
		_near_time = maxf(0.0, _near_time - delta * 2.0)
