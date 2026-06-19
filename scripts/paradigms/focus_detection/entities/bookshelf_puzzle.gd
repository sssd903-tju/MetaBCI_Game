extends Control
class_name BookshelfPuzzle
## BookshelfPuzzle — 书架谜题: 5本书找缺失编号

var missing_digit: int = 0
var solved: bool = false
var _spotlight: Spotlight = null
var _books: Array[Label] = []
var _answer_label: Label
const BOOK_NUMBERS := [1, 2, 3, 4, 5, 6, 7, 8, 9]


func _ready() -> void:
	size = Vector2(400, 120)

	var bg := ColorRect.new()
	bg.size = size
	bg.color = Color("1A1612")
	add_child(bg)

	var hint := Label.new()
	hint.text = "从1到9, 缺了哪一本?"
	hint.add_theme_font_size_override("font_size", 13)
	hint.add_theme_color_override("font_color", Color("8A8A6A"))
	hint.position = Vector2(10, 2)
	hint.size = Vector2(200, 20)
	add_child(hint)

	_answer_label = Label.new()
	_answer_label.text = "?"
	_answer_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_answer_label.add_theme_font_size_override("font_size", 36)
	_answer_label.add_theme_color_override("font_color", Color.GOLD)
	_answer_label.size = Vector2(60, 60)
	_answer_label.position = Vector2(size.x - 70, 40)
	add_child(_answer_label)

	modulate.a = 0.0


func setup(spot: Spotlight) -> void:
	_spotlight = spot
	# 随机选缺失数字
	var missing_idx := randi_range(1, 7)  # 避开头尾
	missing_digit = BOOK_NUMBERS[missing_idx]

	# 显示除缺失外的5本连续书
	var start := maxi(1, missing_idx - 2)
	if start + 4 > 9:
		start = 5
	var shown := BOOK_NUMBERS.slice(start, start + 5)

	var gap := 55.0
	for i in range(5):
		var lbl := Label.new()
		lbl.text = "📕 %d" % shown[i]
		lbl.add_theme_font_size_override("font_size", 16)
		lbl.add_theme_color_override("font_color", Color("C0B090"))
		lbl.position = Vector2(10 + i * gap, 30)
		lbl.size = Vector2(50, 60)
		add_child(lbl)
		_books.append(lbl)


func get_digit() -> int:
	return missing_digit


func _process(delta: float) -> void:
	if solved:
		return
	if _spotlight:
		var center := global_position + size / 2.0
		var dist := center.distance_to(_spotlight.global_position)
		modulate.a = lerpf(modulate.a, 1.0 if dist < _spotlight.get_radius() else 0.0, 3.0 * delta)


func try_answer(digit: int) -> bool:
	if solved:
		return false
	if digit == missing_digit:
		solved = true
		_answer_label.text = str(digit)
		_answer_label.add_theme_color_override("font_color", Color.GREEN)
		AudioManager.play_hit(8)
		get_parent().on_bookshelf_solved()
		return true
	return false
