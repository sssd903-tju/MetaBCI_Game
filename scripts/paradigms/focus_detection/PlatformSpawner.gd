extends Node
class_name PlatformSpawner
## PlatformSpawner — 平台生成器
##
## 在玩家前方持续生成平台，包含三种类型按比例混合

@export var spawn_distance := 500.0   # 在玩家前方多少距离生成
@export var despawn_distance := 400.0 # 在玩家后方多少距离回收
@export var min_gap := 80.0           # 平台间最小间距
@export var max_gap := 180.0          # 平台间最大间距
@export var normal_ratio := 0.5       # 正常平台比例
@export var fragile_ratio := 0.3      # 脆弱平台比例
@export var moving_ratio := 0.2       # 移动平台比例

var _platforms: Array[FocusPlatform] = []
var _last_spawn_x := 0.0
var _player_ref: FocusPlayer = null
var _platform_scene: PackedScene = null

# 平台样式缓存
var _platform_scenes := {
	FocusPlatform.PlatformType.NORMAL: null,
	FocusPlatform.PlatformType.FRAGILE: null,
	FocusPlatform.PlatformType.MOVING: null,
}


func _ready() -> void:
	_player_ref = get_parent().get_node_or_null("Player") as FocusPlayer


func _process(_delta: float) -> void:
	if _player_ref == null:
		return

	var player_x := _player_ref.position.x

	# 在玩家前方生成平台
	while _last_spawn_x < player_x + spawn_distance:
		_spawn_platform()

	# 回收后方平台
	_cleanup_platforms(player_x - despawn_distance)


func _spawn_platform() -> void:
	var platform := FocusPlatform.new()

	# 随机选择类型
	var roll := randf()
	if roll < normal_ratio:
		platform.platform_type = FocusPlatform.PlatformType.NORMAL
	elif roll < normal_ratio + fragile_ratio:
		platform.platform_type = FocusPlatform.PlatformType.FRAGILE
	else:
		platform.platform_type = FocusPlatform.PlatformType.MOVING

	# 随机 X 间距
	_last_spawn_x += randf_range(min_gap, max_gap)

	# Y 位置：在屏幕中间区域随机
	var base_y := GlobalConfig.GAME_HEIGHT * 0.5
	var y_variation := randf_range(-150, 150)
	platform.position = Vector2(_last_spawn_x, base_y + y_variation)

	add_child(platform)
	_platforms.append(platform)


func _cleanup_platforms(despawn_x: float) -> void:
	var to_remove: Array[FocusPlatform] = []
	for p in _platforms:
		if p.position.x < despawn_x:
			to_remove.append(p)

	for p in to_remove:
		_platforms.erase(p)
		p.queue_free()


func apply_focus_to_platforms(ratio: float) -> void:
	"""将专注度值应用到所有活跃平台"""
	for p in _platforms:
		p.apply_focus(ratio)


func get_active_platforms() -> Array[FocusPlatform]:
	return _platforms


func clear_all() -> void:
	for p in _platforms:
		p.queue_free()
	_platforms.clear()
	_last_spawn_x = 0.0
