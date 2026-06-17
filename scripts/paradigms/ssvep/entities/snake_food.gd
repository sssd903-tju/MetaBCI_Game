extends Node2D
class_name SnakeFood
## Food — 随机位置食物

var _position: Vector2i = Vector2i.ZERO
var _grid_offset: Vector2


func _ready() -> void:
	_grid_offset = Vector2(
		(GlobalConfig.GAME_WIDTH - MindSnake.GRID_W * MindSnake.CELL) / 2.0,
		(GlobalConfig.GAME_HEIGHT - MindSnake.GRID_H * MindSnake.CELL) / 2.0
	)


func spawn(snake_body: Array[Vector2i]) -> void:
	var candidates: Array[Vector2i] = []
	for x in range(MindSnake.GRID_W):
		for y in range(MindSnake.GRID_H):
			var p := Vector2i(x, y)
			if p not in snake_body:
				candidates.append(p)
	if candidates.is_empty():
		return
	_position = candidates[randi() % candidates.size()]
	queue_redraw()


func get_position() -> Vector2i:
	return _position


func _draw() -> void:
	if _position == Vector2i.ZERO:
		return
	var pos := Vector2(_position) * MindSnake.CELL + _grid_offset + Vector2.ONE * MindSnake.CELL / 2.0
	draw_circle(pos, MindSnake.CELL / 2.0 - 2, Color("E04040"))
