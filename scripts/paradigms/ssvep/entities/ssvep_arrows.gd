extends Node2D
class_name SSVEPArrows
## SSVEPArrows — 4方向 SSVEP 闪烁箭头 (使用 Label + modulate)

const FREQ_UP    := 8.0
const FREQ_RIGHT := 10.0
const FREQ_DOWN  := 12.0
const FREQ_LEFT  := 15.0

var _arrow_labels: Dictionary = {}  # name → Label
var _decoded_dir: String = ""


func _ready() -> void:
	var cx := GlobalConfig.GAME_WIDTH / 2.0
	var cy := GlobalConfig.GAME_HEIGHT / 2.0
	var gap := 150.0

	var specs := [
		{"name": "up",    "pos": Vector2(cx, cy - gap), "freq": FREQ_UP,    "char": "▲", "color": Color("D94040")},
		{"name": "right", "pos": Vector2(cx + gap, cy),  "freq": FREQ_RIGHT, "char": "▶", "color": Color("5A8A6A")},
		{"name": "down",  "pos": Vector2(cx, cy + gap),  "freq": FREQ_DOWN,  "char": "▼", "color": Color("4A90D9")},
		{"name": "left",  "pos": Vector2(cx - gap, cy),  "freq": FREQ_LEFT,  "char": "◀", "color": Color("F0C040")},
	]

	for s in specs:
		var lbl := Label.new()
		lbl.text = s.char
		lbl.position = s.pos - Vector2(24, 24)
		lbl.size = Vector2(48, 48)
		lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		lbl.add_theme_font_size_override("font_size", 36)
		lbl.add_theme_color_override("font_color", s.color)
		add_child(lbl)
		_arrow_labels[s.name] = {"label": lbl, "freq": s.freq, "color": s.color}


func _process(_delta: float) -> void:
	var t: float = Time.get_ticks_msec() / 1000.0
	for dir in _arrow_labels:
		var a: Dictionary = _arrow_labels[dir]
		var b: float = (sin(t * a.freq * TAU) + 1.0) / 2.0
		a.label.modulate = a.color.lerp(Color.WHITE, b)


func set_decoded(dir: String) -> void:
	_decoded_dir = dir


## 高亮解码方向 (闪烁后短暂高亮)
func flash_decoded() -> void:
	if _decoded_dir in _arrow_labels:
		var a: Dictionary = _arrow_labels[_decoded_dir]
		var tween := create_tween()
		tween.tween_property(a.label, "modulate", Color.WHITE, 0.1)
		tween.tween_property(a.label, "modulate", a.color, 0.3)
