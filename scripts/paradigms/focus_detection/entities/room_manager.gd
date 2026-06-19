extends Node2D
class_name RoomManager
## RoomManager — 全屏房间 + 门洞过渡

enum Room { LIVING, STUDY, KITCHEN, BEDROOM }

signal room_changed(from: int, to: int)

var current_room: int = Room.LIVING
var _room_labels: Array[Label] = []

# 门洞区域 (相对于屏幕的矩形)
var _doors: Dictionary = {}


func _ready() -> void:
	_build_doors()
	_update_room_display()


func _build_doors() -> void:
	var dw := 80.0  # 门宽
	var dt := 8.0   # 门厚

	# 客厅: 右→书房, 下→厨房
	_doors[Room.LIVING] = [
		{"rect": Rect2(GlobalConfig.GAME_WIDTH - dt, GlobalConfig.GAME_HEIGHT/2 - dw/2, dt, dw), "target": Room.STUDY, "dir": "right"},
		{"rect": Rect2(GlobalConfig.GAME_WIDTH/2 - dw/2, GlobalConfig.GAME_HEIGHT - dt, dw, dt), "target": Room.KITCHEN, "dir": "down"},
	]
	# 书房: 左→客厅, 下→卧室
	_doors[Room.STUDY] = [
		{"rect": Rect2(0, GlobalConfig.GAME_HEIGHT/2 - dw/2, dt, dw), "target": Room.LIVING, "dir": "left"},
		{"rect": Rect2(GlobalConfig.GAME_WIDTH/2 - dw/2, GlobalConfig.GAME_HEIGHT - dt, dw, dt), "target": Room.BEDROOM, "dir": "down"},
	]
	# 厨房: 上→客厅, 右→卧室
	_doors[Room.KITCHEN] = [
		{"rect": Rect2(GlobalConfig.GAME_WIDTH/2 - dw/2, 0, dw, dt), "target": Room.LIVING, "dir": "up"},
		{"rect": Rect2(GlobalConfig.GAME_WIDTH - dt, GlobalConfig.GAME_HEIGHT/2 - dw/2, dt, dw), "target": Room.BEDROOM, "dir": "right"},
	]
	# 卧室: 上→书房, 左→厨房
	_doors[Room.BEDROOM] = [
		{"rect": Rect2(GlobalConfig.GAME_WIDTH/2 - dw/2, 0, dw, dt), "target": Room.STUDY, "dir": "up"},
		{"rect": Rect2(0, GlobalConfig.GAME_HEIGHT/2 - dw/2, dt, dw), "target": Room.KITCHEN, "dir": "left"},
	]


func get_room_name(room: int) -> String:
	match room:
		Room.LIVING:  return "客厅"
		Room.STUDY:   return "书房"
		Room.KITCHEN: return "厨房"
		Room.BEDROOM: return "卧室"
	return ""


func check_door_transition(light_pos: Vector2, light_radius: float) -> int:
	if not _doors.has(current_room):
		return -1
	for d in _doors[current_room]:
		var dr: Rect2 = d.rect
		var door_center := dr.position + dr.size / 2.0
		if light_pos.distance_to(door_center) < light_radius * 0.6:
			return d.target
	return -1


func transition_to(new_room: int) -> Vector2:
	var old := current_room
	current_room = new_room
	_update_room_display()
	room_changed.emit(old, new_room)

	# 返回新房间的光圈位置
	match new_room:
		Room.LIVING:  return Vector2(GlobalConfig.GAME_WIDTH * 0.3, GlobalConfig.GAME_HEIGHT * 0.5)
		Room.STUDY:   return Vector2(GlobalConfig.GAME_WIDTH * 0.7, GlobalConfig.GAME_HEIGHT * 0.5)
		Room.KITCHEN: return Vector2(GlobalConfig.GAME_WIDTH * 0.4, GlobalConfig.GAME_HEIGHT * 0.3)
		Room.BEDROOM: return Vector2(GlobalConfig.GAME_WIDTH * 0.6, GlobalConfig.GAME_HEIGHT * 0.7)
	return Vector2(400, 400)


func _update_room_display() -> void:
	queue_redraw()


func _draw() -> void:
	# 房间边界线
	var border_color := Color("2A2018")
	var border_w := 3.0

	# 四面墙
	draw_rect(Rect2(0, 0, GlobalConfig.GAME_WIDTH, border_w), border_color, true)
	draw_rect(Rect2(0, GlobalConfig.GAME_HEIGHT - border_w, GlobalConfig.GAME_WIDTH, border_w), border_color, true)
	draw_rect(Rect2(0, 0, border_w, GlobalConfig.GAME_HEIGHT), border_color, true)
	draw_rect(Rect2(GlobalConfig.GAME_WIDTH - border_w, 0, border_w, GlobalConfig.GAME_HEIGHT), border_color, true)

	# 门洞 (墙上缺口 — 用背景色覆盖)
	if _doors.has(current_room):
		for d in _doors[current_room]:
			var dr: Rect2 = d.rect
			draw_rect(dr, Color("0A0A0A"), true)  # 门洞 = 背景色
			# 门框亮边
			var glow := Color("4A3A2A")
			glow.a = 0.5
			draw_rect(dr.grow(2), glow, false, 1.0)
