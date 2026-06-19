extends Node2D
class_name RoomManager

enum Room { LIVING, STUDY, KITCHEN, BEDROOM }

signal room_changed(from: int, to: int)

var current_room: int = Room.LIVING

# 门锁状态: false=锁, true=开
var _doors_unlocked: Dictionary = {}
var _doors_data: Dictionary = {}


func _ready() -> void:
	_init_doors()
	queue_redraw()


func _init_doors() -> void:
	var dw := 80.0
	var dt := 8.0
	var hw := GlobalConfig.GAME_WIDTH / 2.0 - dw / 2.0
	var vh := GlobalConfig.GAME_HEIGHT / 2.0 - dw / 2.0

	_doors_data = {
		Room.LIVING: [
			{"rect": Rect2(GlobalConfig.GAME_WIDTH - dt, vh, dt, dw), "target": Room.STUDY, "label": "书房", "key": "living_study"},
			{"rect": Rect2(hw, GlobalConfig.GAME_HEIGHT - dt, dw, dt), "target": Room.KITCHEN, "label": "厨房", "key": "living_kitchen"},
		],
		Room.STUDY: [
			{"rect": Rect2(0, vh, dt, dw), "target": Room.LIVING, "label": "客厅", "key": "living_study"},
			{"rect": Rect2(hw, GlobalConfig.GAME_HEIGHT - dt, dw, dt), "target": Room.BEDROOM, "label": "卧室", "key": "study_bedroom"},
		],
		Room.KITCHEN: [
			{"rect": Rect2(hw, 0, dw, dt), "target": Room.LIVING, "label": "客厅", "key": "living_kitchen"},
			{"rect": Rect2(GlobalConfig.GAME_WIDTH - dt, vh, dt, dw), "target": Room.BEDROOM, "label": "卧室", "key": "kitchen_bedroom"},
		],
		Room.BEDROOM: [
			{"rect": Rect2(hw, 0, dw, dt), "target": Room.STUDY, "label": "书房", "key": "study_bedroom"},
			{"rect": Rect2(0, vh, dt, dw), "target": Room.KITCHEN, "label": "厨房", "key": "kitchen_bedroom"},
		],
	}


func unlock_door(key: String) -> void:
	_doors_unlocked[key] = true
	queue_redraw()


func is_door_unlocked(key: String) -> bool:
	return _doors_unlocked.get(key, false)


func get_room_name(room: int) -> String:
	match room:
		Room.LIVING:  return "客厅"
		Room.STUDY:   return "书房"
		Room.KITCHEN: return "厨房"
		Room.BEDROOM: return "卧室"
	return ""


func check_door_transition(light_pos: Vector2, light_radius: float) -> int:
	if not _doors_data.has(current_room):
		return -1
	for d in _doors_data[current_room]:
		var dr: Rect2 = d.rect
		var center := dr.position + dr.size / 2.0
		if light_pos.distance_to(center) < light_radius * 0.6:
			if is_door_unlocked(d.key):
				return d.target
	return -1


func transition_to(new_room: int) -> Vector2:
	var old := current_room
	current_room = new_room
	queue_redraw()
	room_changed.emit(old, new_room)

	match new_room:
		Room.LIVING:  return Vector2(GlobalConfig.GAME_WIDTH * 0.3, GlobalConfig.GAME_HEIGHT * 0.5)
		Room.STUDY:   return Vector2(GlobalConfig.GAME_WIDTH * 0.6, GlobalConfig.GAME_HEIGHT * 0.5)
		Room.KITCHEN: return Vector2(GlobalConfig.GAME_WIDTH * 0.4, GlobalConfig.GAME_HEIGHT * 0.35)
		Room.BEDROOM: return Vector2(GlobalConfig.GAME_WIDTH * 0.7, GlobalConfig.GAME_HEIGHT * 0.7)
	return Vector2(400, 400)


func _draw() -> void:
	var bc := Color("2A2018")

	# 四面墙
	draw_rect(Rect2(0, 0, GlobalConfig.GAME_WIDTH, 3), bc, true)
	draw_rect(Rect2(0, GlobalConfig.GAME_HEIGHT - 3, GlobalConfig.GAME_WIDTH, 3), bc, true)
	draw_rect(Rect2(0, 0, 3, GlobalConfig.GAME_HEIGHT), bc, true)
	draw_rect(Rect2(GlobalConfig.GAME_WIDTH - 3, 0, 3, GlobalConfig.GAME_HEIGHT), bc, true)

	if not _doors_data.has(current_room):
		return

	for d in _doors_data[current_room]:
		var dr: Rect2 = d.rect
		if is_door_unlocked(d.key):
			# 开门 — 深色门洞
			draw_rect(dr, Color("0A0A0A"), true)
			var g := Color("3A3A2A")
			g.a = 0.5
			draw_rect(dr.grow(2), g, false, 1.0)
		else:
			# 锁门 — 暗红色
			draw_rect(dr, Color("3A2020"), true)
			var g := Color("5A3A3A")
			g.a = 0.6
			draw_rect(dr.grow(2), g, false, 1.0)
