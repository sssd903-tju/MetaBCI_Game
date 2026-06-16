extends StaticBody2D
class_name FocusPlatform
## FocusPlatform — 专注度检测范式中的平台
##
## 三种类型:
##   NORMAL  — 莫兰迪绿，始终稳定
##   FRAGILE — 暖棕色，低专注时会碎裂
##   MOVING  — 灰蓝色，上下移动

enum PlatformType {
	NORMAL = 0,
	FRAGILE = 1,
	MOVING = 2,
}

@export var platform_type := PlatformType.NORMAL
@export var break_threshold := 1.5  # 低于此专注度时脆弱平台开始碎裂
@export var move_amplitude := 60.0
@export var move_speed := 2.0

var _rect: ColorRect
var _crack_overlay: ColorRect
var _crack_level := 0.0  # 0.0 = 完好, 1.0 = 完全碎裂
var _initial_y := 0.0
var _move_time := 0.0
var _is_broken := false


func _ready() -> void:
	_initial_y = position.y
	_move_time = randf() * TAU
	_setup_appearance()


func _setup_appearance() -> void:
	# 平台主体
	_rect = ColorRect.new()
	_rect.size = Vector2(GlobalConfig.PLATFORM_WIDTH, GlobalConfig.PLATFORM_HEIGHT)
	_rect.position = -_rect.size / 2.0
	add_child(_rect)

	# 碎裂叠加层
	_crack_overlay = ColorRect.new()
	_crack_overlay.size = _rect.size
	_crack_overlay.position = -_rect.size / 2.0
	_crack_overlay.color = Color.BLACK
	_crack_overlay.color.a = 0.0
	add_child(_crack_overlay)

	# 碰撞体
	var collision := CollisionShape2D.new()
	var shape := RectangleShape2D.new()
	shape.size = Vector2(GlobalConfig.PLATFORM_WIDTH, GlobalConfig.PLATFORM_HEIGHT)
	collision.shape = shape
	add_child(collision)

	_update_color()


func _update_color() -> void:
	match platform_type:
		PlatformType.NORMAL:
			_rect.color = GlobalConfig.PLATFORM_NORMAL
		PlatformType.FRAGILE:
			_rect.color = GlobalConfig.PLATFORM_FRAGILE
		PlatformType.MOVING:
			_rect.color = GlobalConfig.PLATFORM_MOVING


func _process(delta: float) -> void:
	if _is_broken:
		return

	# 移动平台：上下浮动
	if platform_type == PlatformType.MOVING:
		_move_time += delta * move_speed
		position.y = _initial_y + sin(_move_time) * move_amplitude

	# 更新碎裂叠加层
	_crack_overlay.color.a = _crack_level * 0.7


func apply_focus(ratio: float) -> void:
	"""根据专注度更新平台状态"""
	if _is_broken:
		return

	match platform_type:
		PlatformType.NORMAL:
			# 正常平台不受影响
			pass

		PlatformType.FRAGILE:
			# 低专注 → 碎裂加剧
			if ratio < break_threshold:
				_crack_level += (break_threshold - ratio) * 0.3 * get_process_delta_time()
				_crack_level = clampf(_crack_level, 0.0, 1.0)
				if _crack_level >= 1.0:
					_break()
			else:
				# 高专注 → 缓慢恢复
				_crack_level -= 0.1 * get_process_delta_time()
				_crack_level = clampf(_crack_level, 0.0, 1.0)

		PlatformType.MOVING:
			# 低专注 → 移动幅度变大（更难踩）
			if ratio < GlobalConfig.FOCUS_MEDIUM_THRESHOLD:
				move_amplitude = lerpf(move_amplitude, 120.0, 2.0 * get_process_delta_time())
				move_speed = lerpf(move_speed, 4.0, 2.0 * get_process_delta_time())
			else:
				move_amplitude = lerpf(move_amplitude, 60.0, 2.0 * get_process_delta_time())
				move_speed = lerpf(move_speed, 2.0, 2.0 * get_process_delta_time())


func _break() -> void:
	"""平台碎裂"""
	_is_broken = true
	_crack_overlay.color.a = 0.9

	# 碎裂动画效果
	var tween := create_tween()
	tween.tween_property(_rect, "scale", Vector2(1.0, 0.1), 0.3)
	tween.parallel().tween_property(_rect, "color:a", 0.0, 0.3)
	tween.tween_callback(_on_break_complete)


func _on_break_complete() -> void:
	# 禁用碰撞
	set_deferred("collision_layer", 0)
	set_deferred("collision_mask", 0)
	visible = false

	# 通知游戏控制器
	if has_node("/root/FocusGame"):
		get_node("/root/FocusGame")._on_platform_broken()
