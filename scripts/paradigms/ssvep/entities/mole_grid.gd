extends Node2D
class_name MoleGrid
## MoleGrid — 动态洞口网格，随关数增加洞数

const FREQ_POOL := [8.0, 9.2, 10.4, 11.6, 13.0, 14.4, 15.6]
const COLOR_POOL := [
	Color("D94040"), Color("4A90D9"), Color("F0C040"),
	Color("5A8A6A"), Color("D97AB5"), Color("E0884A"), Color("6ABFBF"),
]

var holes: Array[MoleHole] = []
var active_hole_index: int = -1
var _hammer_node: Node2D = null


func _ready() -> void:
	_setup_hammer()


func _setup_hammer() -> void:
	_hammer_node = Node2D.new()
	_hammer_node.name = "Hammer"
	_hammer_node.visible = false
	_hammer_node.z_index = 10

	# 锤柄 (细长矩形)
	var handle := ColorRect.new()
	handle.color = Color("6B4226")
	handle.size = Vector2(6, 50)
	handle.position = Vector2(-3, -10)

	# 锤头 (粗矩形)
	var head := ColorRect.new()
	head.color = Color("4A4A4A")
	head.size = Vector2(40, 22)
	head.position = Vector2(-20, -32)

	_hammer_node.add_child(handle)
	_hammer_node.add_child(head)
	add_child(_hammer_node)



## 根据轮次重建网格
func setup_for_round(round_num: int) -> void:
	_clear_all()
	var count := _hole_count(round_num)
	var d := _spacing(count)
	var positions := _layout(count, d)
	var freqs := FREQ_POOL.slice(0, count)
	var colors := COLOR_POOL.slice(0, count)

	for i in range(count):
		var hole := MoleHole.new()
		hole.name = "Hole%d" % (i + 1)
		hole.position = positions[i]
		hole.frequency = freqs[i]
		hole.flicker_color = colors[i]
		add_child(hole)
		holes.append(hole)

	active_hole_index = -1


func _hole_count(round_num: int) -> int:
	if round_num <= 2:   return 2
	if round_num <= 4:   return 3
	if round_num <= 7:   return 4
	return 5


func _spacing(count: int) -> float:
	# 洞外径 72px, 间距预留 20px, 保证不重叠
	match count:
		2: return 300.0
		3: return 320.0
		4: return 300.0
		5: return 340.0
		_: return 300.0


func _layout(count: int, d: float) -> Array[Vector2]:
	var cx := GlobalConfig.GAME_WIDTH / 2.0
	var cy := GlobalConfig.GAME_HEIGHT / 2.0 - 20

	match count:
		2:
			return [Vector2(cx - d/2, cy), Vector2(cx + d/2, cy)]
		3:
			return [
				Vector2(cx, cy - d * 0.5),
				Vector2(cx - d/2, cy + d * 0.35),
				Vector2(cx + d/2, cy + d * 0.35),
			]
		4:
			var h := d / 2.0
			return [
				Vector2(cx - h, cy - h),
				Vector2(cx + h, cy - h),
				Vector2(cx - h, cy + h),
				Vector2(cx + h, cy + h),
			]
		5:
			var h := d / 2.0
			return [
				Vector2(cx, cy - h),
				Vector2(cx, cy + h),
				Vector2(cx - h, cy),
				Vector2(cx + h, cy),
				Vector2(cx, cy),
			]
		_:
			return _layout(4, d)


func spawn_mole() -> int:
	var new_idx := active_hole_index
	while new_idx == active_hole_index and holes.size() > 1:
		new_idx = randi() % holes.size()
	active_hole_index = new_idx
	holes[active_hole_index].show_mole()
	return active_hole_index


func hide_current_mole() -> void:
	if active_hole_index >= 0 and active_hole_index < holes.size():
		holes[active_hole_index].hide_mole()


## 锤子敲击动画
func play_hammer_hit() -> void:
	if active_hole_index < 0 or _hammer_node == null:
		return
	var target_pos := holes[active_hole_index].position
	_hammer_node.position = target_pos + Vector2(30, -40)
	_hammer_node.visible = true
	_hammer_node.rotation = -0.6

	var tween := create_tween()
	tween.set_ease(Tween.EASE_IN)
	tween.tween_property(_hammer_node, "rotation", 0.15, 0.12)
	tween.parallel().tween_property(_hammer_node, "position:y", target_pos.y - 20, 0.12)
	tween.tween_property(_hammer_node, "visible", false, 0.0).set_delay(0.25)


func get_active_frequency() -> float:
	if active_hole_index < 0 or active_hole_index >= holes.size():
		return 0.0
	return holes[active_hole_index].frequency


func match_frequency(detected_freq: float, tolerance: float = 0.6) -> int:
	var best_idx := -1
	var best_diff := tolerance + 0.1
	for i in range(holes.size()):
		var diff := absf(detected_freq - holes[i].frequency)
		if diff < best_diff:
			best_diff = diff
			best_idx = i
	return best_idx


func _clear_all() -> void:
	for hole in holes:
		hole.queue_free()
	holes.clear()
	active_hole_index = -1
