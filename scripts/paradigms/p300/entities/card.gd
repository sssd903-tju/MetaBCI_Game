extends Control
class_name MindCard

var symbol: String = "A♠"
var card_index: int = 0
var face_down: bool = false
var flash_on: bool = false

var _glow: float = 0.0
var _card_bg: ColorRect
var _card_label: Label
var _glow_rect: ColorRect

const CARD_SIZE := Vector2(100, 140)


func _ready() -> void:
	size = CARD_SIZE
	pivot_offset = CARD_SIZE / 2.0

	_card_bg = ColorRect.new()
	_card_bg.size = CARD_SIZE
	add_child(_card_bg)

	_glow_rect = ColorRect.new()
	_glow_rect.size = Vector2.ZERO
	add_child(_glow_rect)

	_card_label = Label.new()
	_card_label.size = CARD_SIZE
	_card_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_card_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_card_label.add_theme_font_size_override("font_size", 26)
	add_child(_card_label)

	_update_appearance()


func set_flash(on: bool) -> void:
	flash_on = on


func flip(reveal: bool) -> void:
	face_down = not reveal
	_update_appearance()


func _update_appearance() -> void:
	if face_down:
		_card_bg.color = Color("3F6850")
		_card_label.visible = false
	else:
		_card_bg.color = Color.WHITE
		_card_label.visible = true
		_card_label.text = symbol
		_card_label.add_theme_color_override("font_color",
			Color.RED if ("♥" in symbol or "♦" in symbol) else Color.BLACK)


func _process(delta: float) -> void:
	if flash_on:
		_glow = minf(1.0, _glow + delta * 12.0)
	else:
		_glow = maxf(0.0, _glow - delta * 10.0)

	_glow_rect.size = CARD_SIZE + Vector2.ONE * 12.0 * _glow
	_glow_rect.position = -Vector2.ONE * 6.0 * _glow
	_glow_rect.color = Color.GOLD
	_glow_rect.color.a = _glow * 0.5
