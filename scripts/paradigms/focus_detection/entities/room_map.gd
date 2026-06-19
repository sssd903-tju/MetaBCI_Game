extends Node2D
class_name RoomMap
## RoomMap — 4室1厅俯视图: 客厅/书房/厨房/卧室 + 走廊

var rooms: Array[Dictionary] = []


func _ready() -> void:
	_build_map()


func _build_map() -> void:
	var ox := 80.0
	var oy := 80.0
	var rw := 620.0
	var rh := 300.0
	var cw := 140.0   # 走廊宽
	var door_w := 60.0

	var specs := [
		{"name": "客厅", "icon": "🛋", "x": ox, "y": oy},
		{"name": "书房", "icon": "📚", "x": ox + rw + cw, "y": oy},
		{"name": "厨房", "icon": "🍳", "x": ox, "y": oy + rh + cw},
		{"name": "卧室", "icon": "🛏", "x": ox + rw + cw, "y": oy + rh + cw},
	]

	for s in specs:
		_add_room(s.name, s.icon, Rect2(s.x, s.y, rw, rh), door_w)
		rooms.append({"name": s.name, "rect": Rect2(s.x + 10, s.y + 10, rw - 20, rh - 20)})

	# 走廊地板
	var hall_h := ColorRect.new()
	hall_h.color = Color("1E1A16")
	hall_h.position = Vector2(ox + rw, oy + rh/2 - 30)
	hall_h.size = Vector2(cw, 60)
	add_child(hall_h)

	var hall_v := ColorRect.new()
	hall_v.color = Color("1E1A16")
	hall_v.position = Vector2(ox + rw/2 - 30, oy + rh)
	hall_v.size = Vector2(60, cw)
	add_child(hall_v)

	var hall_v2 := ColorRect.new()
	hall_v2.color = Color("1E1A16")
	hall_v2.position = Vector2(ox + rw + cw + rw/2 - 30, oy + rh)
	hall_v2.size = Vector2(60, cw)
	add_child(hall_v2)


func _add_room(name: String, icon: String, rect: Rect2, door_w: float) -> void:
	# 地板
	var floor := ColorRect.new()
	floor.color = Color("1A1612")
	floor.position = rect.position
	floor.size = rect.size
	add_child(floor)

	# 墙壁 (4条边, 门洞处断开)
	var wall_thick := 4.0
	var wall_color := Color("3A3028")

	# 上墙: 中部门洞
	_add_wall(Vector2(rect.position.x, rect.position.y),
		Vector2(rect.size.x, wall_thick), wall_color,
		rect.position.x + rect.size.x/2 - door_w/2, door_w, true)

	# 下墙: 中部门洞 (所有房间下方都有走廊连接)
	_add_wall(Vector2(rect.position.x, rect.position.y + rect.size.y),
		Vector2(rect.size.x, wall_thick), wall_color,
		rect.position.x + rect.size.x/2 - door_w/2, door_w, true)

	# 左墙: 中部门洞 (仅右侧两个房间)
	_add_wall(Vector2(rect.position.x, rect.position.y),
		Vector2(wall_thick, rect.size.y), wall_color,
		rect.position.y + rect.size.y/2 - door_w/2, door_w, false)

	# 右墙
	_add_wall(Vector2(rect.position.x + rect.size.x, rect.position.y),
		Vector2(wall_thick, rect.size.y), wall_color,
		rect.position.y + rect.size.y/2 - door_w/2, door_w, false)

	# 标签
	var lbl := Label.new()
	lbl.text = icon + " " + name
	lbl.position = rect.position + Vector2(12, 8)
	lbl.add_theme_font_size_override("font_size", 16)
	lbl.add_theme_color_override("font_color", Color("3A3A3A"))
	add_child(lbl)


func _add_wall(pos: Vector2, sz: Vector2, color: Color, gap_start: float, gap_w: float, horizontal: bool) -> void:
	if horizontal:
		# 左段
		if gap_start > pos.x:
			var left := ColorRect.new()
			left.color = color
			left.position = pos
			left.size = Vector2(gap_start - pos.x, sz.y)
			add_child(left)
		# 右段
		var gap_end := gap_start + gap_w
		var right_start := gap_end
		if right_start < pos.x + sz.x:
			var right := ColorRect.new()
			right.color = color
			right.position = Vector2(right_start, pos.y)
			right.size = Vector2(pos.x + sz.x - right_start, sz.y)
			add_child(right)
	else:
		if gap_start > pos.y:
			var top := ColorRect.new()
			top.color = color
			top.position = pos
			top.size = Vector2(sz.x, gap_start - pos.y)
			add_child(top)
		var gap_end := gap_start + gap_w
		if gap_end < pos.y + sz.y:
			var bottom := ColorRect.new()
			bottom.color = color
			bottom.position = Vector2(pos.x, gap_end)
			bottom.size = Vector2(sz.x, pos.y + sz.y - gap_end)
			add_child(bottom)


func get_room_center(room_idx: int) -> Vector2:
	if room_idx < 0 or room_idx >= rooms.size():
		return Vector2.ZERO
	var r: Rect2 = rooms[room_idx].rect
	return r.position + r.size / 2.0


func get_random_pos_in_room(room_idx: int, margin: float = 60.0) -> Vector2:
	var r: Rect2 = rooms[room_idx].rect
	return Vector2(
		randf_range(r.position.x + margin, r.end.x - margin),
		randf_range(r.position.y + margin, r.end.y - margin)
	)
