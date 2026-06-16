extends CharacterBody2D
class_name FocusPlayer
## FocusPlayer — 专注度检测范式中的玩家角色
##
## 玩家是一个小方块，自动向右移动。
## 专注度影响：
##   - 跳跃高度（高专注 = 跳得更高）
##   - 移动速度（高专注 = 移动稍快）
##   - 视觉效果（光晕颜色随专注度变化）

@export var base_speed := 150.0
@export var base_jump_velocity := -400.0
@export var max_focus_jump_bonus := -200.0
@export var focus_speed_bonus := 80.0

var focus_ratio := 1.5
var is_on_platform := false
var _sprite: ColorRect
var _glow: ColorRect
var _auto_move := true


func _ready() -> void:
	_setup_appearance()
	# 初始位置
	position = Vector2(200, 500)


func _setup_appearance() -> void:
	# 玩家主体 — 小方块
	_sprite = ColorRect.new()
	_sprite.size = Vector2(GlobalConfig.PLAYER_SIZE, GlobalConfig.PLAYER_SIZE)
	_sprite.color = GlobalConfig.PLAYER_COLOR
	_sprite.position = -_sprite.size / 2.0
	add_child(_sprite)

	# 光晕效果
	_glow = ColorRect.new()
	_glow.size = Vector2(GlobalConfig.PLAYER_SIZE + 8, GlobalConfig.PLAYER_SIZE + 8)
	_glow.position = -_glow.size / 2.0
	_glow.color = Color.TRANSPARENT
	add_child(_glow)
	move_child(_glow, 0)  # 放在后面


func _physics_process(delta: float) -> void:
	# 重力
	if not is_on_floor():
		velocity.y += GlobalConfig.GRAVITY * delta
	else:
		velocity.y = 0

	# 自动向右移动（速度受专注度影响）
	if _auto_move:
		var speed_mod := 1.0 + (focus_ratio / GlobalConfig.FOCUS_HIGH_THRESHOLD) * 0.5
		velocity.x = base_speed * speed_mod

	move_and_slide()

	# 更新视觉效果
	_update_visuals(delta)

	# 检查是否掉出屏幕
	if position.y > GlobalConfig.GAME_HEIGHT + 100:
		_on_fell_off()


func _update_visuals(delta: float) -> void:
	# 光晕颜色随专注度变化
	var target_glow: Color = GlobalConfig.focus_to_color(focus_ratio)
	target_glow.a = clampf(focus_ratio / 3.0, 0.0, 0.6)
	_glow.color = _glow.color.lerp(target_glow, 5.0 * delta)

	# 呼吸效果
	var breath := 1.0 + sin(Time.get_ticks_msec() / 1000.0 * 3.0) * 0.05
	_glow.scale = Vector2(breath, breath)

	# 移动视觉反馈
	modulate.a = 1.0 - abs(velocity.y) / 800.0 * 0.3


func jump() -> void:
	"""执行跳跃，高度由专注度决定"""
	if not is_on_floor():
		return

	var focus_multiplier := clampf(focus_ratio / GlobalConfig.FOCUS_HIGH_THRESHOLD, 0.3, 1.0)
	var jump_vel := base_jump_velocity + max_focus_jump_bonus * focus_multiplier
	velocity.y = jump_vel


func apply_focus(ratio: float) -> void:
	"""应用专注度数据"""
	focus_ratio = ratio


func _on_fell_off() -> void:
	"""玩家掉落 — 通知游戏控制器"""
	get_parent()._on_player_died()


func set_auto_move(enabled: bool) -> void:
	_auto_move = enabled
