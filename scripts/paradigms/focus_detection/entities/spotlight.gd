extends Node2D
class_name Spotlight
## Spotlight — 专注度驱动光圈, 键盘移动

var focus_ratio: float = 1.5
var _radius: float = 150.0

const BASE_RADIUS := 120.0
const FOCUS_SCALE := 80.0   # 满专注额外 80px 半径


func _ready() -> void:
	position = Vector2(GlobalConfig.GAME_WIDTH / 2.0, GlobalConfig.GAME_HEIGHT / 2.0)
	queue_redraw()


func _process(delta: float) -> void:
	# 目标半径: 专注度越高光越大
	var target_r := BASE_RADIUS + focus_ratio * FOCUS_SCALE
	_radius = lerpf(_radius, target_r, 5.0 * delta)

	# 键盘移动
	var speed := 300.0
	var move := Vector2.ZERO
	if Input.is_key_pressed(KEY_UP) or Input.is_key_pressed(KEY_W):
		move.y -= 1
	if Input.is_key_pressed(KEY_DOWN) or Input.is_key_pressed(KEY_S):
		move.y += 1
	if Input.is_key_pressed(KEY_LEFT) or Input.is_key_pressed(KEY_A):
		move.x -= 1
	if Input.is_key_pressed(KEY_RIGHT) or Input.is_key_pressed(KEY_D):
		move.x += 1
	if move.length() > 0:
		position += move.normalized() * speed * delta

	# 限制在屏幕内
	position.x = clampf(position.x, 50, GlobalConfig.GAME_WIDTH - 50)
	position.y = clampf(position.y, 50, GlobalConfig.GAME_HEIGHT - 50)

	queue_redraw()


func get_radius() -> float:
	return _radius


func _draw() -> void:
	# 径向渐变光圈: 中心亮, 边缘暗
	var steps := 20
	for i in range(steps, 0, -1):
		var t := float(i) / float(steps)
		var r := _radius * t
		var c := Color.WHITE
		c.a = t * t * 0.03  # 中心亮, 边缘透明
		draw_circle(Vector2.ZERO, r, c)
