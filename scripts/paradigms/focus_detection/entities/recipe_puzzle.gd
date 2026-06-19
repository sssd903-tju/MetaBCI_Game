extends Control
class_name RecipePuzzle
## RecipePuzzle — 食谱解密: 食材克数→密码数字

var digit1: int = 0
var digit2: int = 0
var solved: bool = false
var _focus_time: float = 0.0
var _spotlight: Spotlight = null
var _label: Label


func _ready() -> void:
	size = Vector2(320, 160)

	var bg := ColorRect.new()
	bg.size = size
	bg.color = Color("1A1612")
	add_child(bg)

	# 随机密码
	digit1 = randi_range(1, 8)
	var d := randi_range(1, 9)
	while d == digit1:
		d = randi_range(1, 9)
	digit2 = d

	_label = Label.new()
	_label.text = "📋 今日菜单\n\n· 盐       %dg\n· 糖       —\n· 面粉    %dg\n· 水       —" % [digit1, digit2]
	_label.add_theme_font_size_override("font_size", 15)
	_label.add_theme_color_override("font_color", Color("C0B090"))
	_label.position = Vector2(16, 8)
	_label.size = Vector2(290, 140)
	add_child(_label)

	var hint := Label.new()
	hint.text = "两道主料的克数即是密码"
	hint.add_theme_font_size_override("font_size", 11)
	hint.add_theme_color_override("font_color", Color("5A5A5A"))
	hint.size = Vector2(200, 16)
	hint.position = Vector2(60, 140)
	add_child(hint)

	modulate.a = 0.0


func setup(spot: Spotlight) -> void:
	_spotlight = spot


func get_digits() -> Array:
	return [digit1, digit2]


func _process(delta: float) -> void:
	if solved:
		return
	if _spotlight:
		var center := global_position + size / 2.0
		var dist := center.distance_to(_spotlight.global_position)
		modulate.a = lerpf(modulate.a, 1.0 if dist < _spotlight.get_radius() else 0.0, 3.0 * delta)


func mark_solved() -> void:
	solved = true
	_label.add_theme_color_override("font_color", Color.GREEN)
