extends Node2D
class_name ArcheryCrosshair
## Crosshair — 准星实体，专注度驱动移动

# 基础移动速度 (像素/秒)
@export var base_speed := 60.0

# 抖动强度
@export var jitter_strength := 8.0

# 当前专注度
var focus_ratio := 1.5

# 是否激活（AIMING 状态才移动）
var active := false

# 内部状态
var _target_center := Vector2.ZERO
var _velocity := Vector2.ZERO
var _jitter_offset := Vector2.ZERO
var _jitter_timer := 0.0


func _ready() -> void:
	queue_redraw()


func _draw() -> void:
	# 十字准星
	var size := 20.0
	var gap := 4.0
	var thickness := 2.0
	var color := Color.BLACK

	# 上
	draw_rect(Rect2(-thickness / 2.0, -size - gap, thickness, size), color)
	# 下
	draw_rect(Rect2(-thickness / 2.0, gap, thickness, size), color)
	# 左
	draw_rect(Rect2(-size - gap, -thickness / 2.0, size, thickness), color)
	# 右
	draw_rect(Rect2(gap, -thickness / 2.0, size, thickness), color)

	# 中心点
	draw_circle(Vector2.ZERO, 3.0, Color.RED)


func set_target(target_center: Vector2) -> void:
	_target_center = target_center


## 重置准星到随机位置
func reset_position() -> void:
	# 从靶面边缘随机位置开始
	var angle := randf() * TAU
	var dist := randf_range(120.0, 200.0)
	position = _target_center + Vector2.RIGHT.rotated(angle) * dist
	_velocity = Vector2.ZERO


func _process(delta: float) -> void:
	if not active or _target_center == Vector2.ZERO:
		return

	var to_center := _target_center - position
	var dist := to_center.length()

	# 专注度决定移动方向和速度
	var direction: Vector2
	var speed: float

	if focus_ratio >= GlobalConfig.FOCUS_HIGH_THRESHOLD:
		# 高专注：向靶心快速靠拢
		direction = to_center.normalized()
		speed = base_speed * (1.0 + (focus_ratio - 2.5) * 0.8)
		_jitter_offset = Vector2.ZERO  # 无抖动

	elif focus_ratio >= GlobalConfig.FOCUS_MEDIUM_THRESHOLD:
		# 中专注：缓慢靠近，轻微抖动
		direction = to_center.normalized()
		speed = base_speed * 0.4
		_update_jitter(delta, 0.3)

	else:
		# 低专注：向外漂移 + 强烈抖动
		direction = -to_center.normalized()
		speed = base_speed * (1.5 - focus_ratio) * 0.8
		_update_jitter(delta, 1.0)

	# 更新位置
	_velocity = direction * speed
	position += _velocity * delta + _jitter_offset


func _update_jitter(delta: float, intensity: float) -> void:
	_jitter_timer += delta
	if _jitter_timer > 0.1:
		_jitter_timer = 0.0
		_jitter_offset = Vector2(
			randf_range(-1.0, 1.0) * jitter_strength * intensity,
			randf_range(-1.0, 1.0) * jitter_strength * intensity
		)


## 计算当前命中环数
func get_hit_ring(target: ArcheryTarget) -> int:
	var dist := position.distance_to(target.get_center())
	return target.get_ring(dist)


## 是否脱靶
func is_miss(target: ArcheryTarget) -> bool:
	return position.distance_to(target.get_center()) > target.total_radius
