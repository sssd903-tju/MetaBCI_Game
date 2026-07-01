extends Node2D
class_name SSVEPArrows
## SSVEPArrows — 4方向闪烁箭头, 慢速跟随蛇头

const FREQ_UP    := 8.0
const FREQ_RIGHT := 10.0
const FREQ_DOWN  := 12.0
const FREQ_LEFT  := 15.0
const GAP := 55.0

var _arrow_labels: Dictionary = {}
var _decoded_dir: String = ""


func _ready() -> void:
	var offsets := {
		"up":    Vector2(0, -GAP),
		"right": Vector2(GAP, 0),
		"down":  Vector2(0, GAP),
		"left":  Vector2(-GAP, 0),
	}
	var specs := [
		{"name": "up",    "freq": FREQ_UP,    "char": "▲", "color": Color("D94040")},
		{"name": "right", "freq": FREQ_RIGHT, "char": "▶", "color": Color("5A8A6A")},
		{"name": "down",  "freq": FREQ_DOWN,  "char": "▼", "color": Color("4A90D9")},
		{"name": "left",  "freq": FREQ_LEFT,  "char": "◀", "color": Color("F0C040")},
	]
	for s in specs:
		var lbl := Label.new()
		lbl.text = s.char
		lbl.size = Vector2(70, 70)
		lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		lbl.add_theme_font_size_override("font_size", 52)
		add_child(lbl)
		_arrow_labels[s.name] = {
			"label": lbl, "freq": s.freq, "color": s.color,
			"offset": offsets[s.name],
		}


func follow(target: Vector2) -> void:
	for dir in _arrow_labels:
		var a: Dictionary = _arrow_labels[dir]
		a.label.position = target + a.offset - Vector2(35, 35)


func _process(_delta: float) -> void:
	var t: float = Time.get_ticks_msec() / 1000.0
	for dir in _arrow_labels:
		var a: Dictionary = _arrow_labels[dir]
		var b: float = (sin(t * a.freq * TAU) + 1.0) / 2.0
		a.label.modulate = a.color
		a.label.modulate.a = 0.2 + b * 0.8


func set_decoded(dir: String) -> void: _decoded_dir = dir


func flash_decoded() -> void:
	if _decoded_dir in _arrow_labels:
		var a: Dictionary = _arrow_labels[_decoded_dir]
		var tw := create_tween()
		a.label.modulate = Color.WHITE
		tw.tween_property(a.label, "modulate", a.color, 0.3)
