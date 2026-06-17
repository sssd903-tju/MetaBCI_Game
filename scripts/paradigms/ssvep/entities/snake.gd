extends Node2D
class_name MindSnake
## Snake — 网格贪吃蛇

const CELL := 35
const GRID_W := 40
const GRID_H := 22
var dirs := {
	"up":    Vector2i(0, -1),
	"down":  Vector2i(0, 1),
	"left":  Vector2i(-1, 0),
	"right": Vector2i(1, 0),
}

var body: Array[Vector2i] = []
var direction: Vector2i = dirs["right"]
var next_direction: Vector2i = dirs["right"]
var _tick_timer: float = 0.0
var _tick_interval: float = 0.3
var _grow_pending: int = 0
var alive: bool = true
var paused: bool = true
var score: int = 0
var grid_offset: Vector2


func _ready() -> void:
	grid_offset = Vector2(
		(GlobalConfig.GAME_WIDTH - GRID_W * CELL) / 2.0,
		(GlobalConfig.GAME_HEIGHT - GRID_H * CELL) / 2.0
	)
	reset()


func reset() -> void:
	var cx := GRID_W / 2
	var cy := GRID_H / 2
	body = [Vector2i(cx, cy), Vector2i(cx - 1, cy), Vector2i(cx - 2, cy)]
	direction = dirs["right"]
	next_direction = dirs["right"]
	_tick_interval = 0.3
	_grow_pending = 0
	alive = true
	paused = true
	score = 0
	queue_redraw()


func set_direction(dir_name: String) -> void:
	if not dirs.has(dir_name):
		return
	var nd: Vector2i = dirs[dir_name]
	# 禁止反向
	if nd == -direction:
		return
	next_direction = nd


func _process(delta: float) -> void:
	if not alive or paused:
		return
	_tick_timer += delta
	if _tick_timer >= _tick_interval:
		_tick_timer = 0.0
		_tick()


func _tick() -> void:
	direction = next_direction
	var head := body[0] + direction

	# 撞墙
	if head.x < 0 or head.x >= GRID_W or head.y < 0 or head.y >= GRID_H:
		alive = false
		queue_redraw()
		return

	# 撞自己
	if head in body:
		alive = false
		queue_redraw()
		return

	body.insert(0, head)
	if _grow_pending > 0:
		_grow_pending -= 1
	else:
		body.pop_back()

	queue_redraw()


func grow(n: int = 1) -> void:
	_grow_pending += n
	# 加速
	_tick_interval = maxf(0.12, _tick_interval - 0.008)


func get_head() -> Vector2i:
	return body[0]


func get_head_screen_pos() -> Vector2:
	return Vector2(body[0]) * CELL + grid_offset + Vector2.ONE * CELL / 2.0


func _draw() -> void:
	# 网格边框
	var border_rect := Rect2(grid_offset, Vector2(GRID_W * CELL, GRID_H * CELL))
	draw_rect(border_rect, Color("3F6850"), false, 3.0)

	if body.is_empty():
		return

	for i in range(body.size()):
		var seg := body[i]
		var pos := Vector2(seg) * CELL + Vector2.ONE * CELL / 2.0 + grid_offset
		var color: Color
		if i == 0:
			color = Color("4A90D9")
			draw_circle(pos, CELL / 2.0 + 2, color)  # 圆头更大
		else:
			var t := float(i) / float(body.size())
			color = Color("4A90D9").darkened(t * 0.6)
		draw_rect(Rect2(pos - Vector2.ONE * CELL / 2.0 + Vector2.ONE, Vector2.ONE * CELL - Vector2.ONE * 2), color, true)

	# 眼睛
	if body.size() > 0:
		var hp := Vector2(body[0]) * CELL + grid_offset + Vector2.ONE * CELL / 2.0
		var ed := direction * CELL * 0.25
		draw_circle(hp + ed - Vector2(0, CELL * 0.12), 3, Color.WHITE)
		draw_circle(hp + ed + Vector2(0, CELL * 0.12), 3, Color.WHITE)
		draw_circle(hp + ed - Vector2(0, CELL * 0.12), 1.5, Color.BLACK)
		draw_circle(hp + ed + Vector2(0, CELL * 0.12), 1.5, Color.BLACK)
