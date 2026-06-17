extends Node
class_name DistractorSpawner
## DistractorSpawner — 干扰物生成器
##
## 瞄准阶段生成浮动干扰，专注度越低/轮次越高 → 干扰越多

# 干扰物颜色 (暖色系，易分散注意力)
const DISTRACT_COLORS := [
	Color("C4665A", 0.4),  # 红
	Color("D4A84B", 0.4),  # 金
	Color("E8774B", 0.35), # 橙
	Color("C4665A", 0.3),  # 浅红
]

var active: bool = false
var _spawn_timer: float = 0.0
var _spawn_interval: float = 1.0
var _max_distractors: int = 4
var _spawn_area: Rect2


func _ready() -> void:
	_spawn_area = Rect2(0, 0, GlobalConfig.GAME_WIDTH, GlobalConfig.GAME_HEIGHT)


func _process(_delta: float) -> void:
	if not active:
		return


## 每帧更新干扰物生成 (由外部调用，传入专注度和轮次)
func update_spawning(delta: float, focus_ratio: float, round_num: int) -> void:
	_spawn_timer += delta

	# 专注度越低 → 生成越快
	var focus_factor: float
	if focus_ratio >= GlobalConfig.FOCUS_HIGH_THRESHOLD:
		focus_factor = 0.3   # 高专注：很少干扰
	elif focus_ratio >= GlobalConfig.FOCUS_MEDIUM_THRESHOLD:
		focus_factor = 0.7   # 中专注：中等干扰
	else:
		focus_factor = 1.2   # 低专注：大量干扰

	# 轮次越高 → 干扰越多
	var round_factor := 1.0 + (round_num - 1) * 0.25

	_spawn_interval = 1.0 / (focus_factor * round_factor)
	_max_distractors = int(clampf(3.0 + round_num * 1.5, 3, 12))

	if _spawn_timer >= _spawn_interval:
		_spawn_timer = 0.0
		if get_child_count() < _max_distractors:
			_spawn_one()


func _spawn_one() -> void:
	var d := Distractor.new()

	# 随机大小
	var radius := randf_range(8.0, 22.0)

	# 从屏幕边缘生成
	var side := randi() % 4
	var start_pos: Vector2
	match side:
		0: start_pos = Vector2(-30, randf_range(0, GlobalConfig.GAME_HEIGHT))
		1: start_pos = Vector2(GlobalConfig.GAME_WIDTH + 30, randf_range(0, GlobalConfig.GAME_HEIGHT))
		2: start_pos = Vector2(randf_range(0, GlobalConfig.GAME_WIDTH), -30)
		_: start_pos = Vector2(randf_range(0, GlobalConfig.GAME_WIDTH), GlobalConfig.GAME_HEIGHT + 30)

	d.position = start_pos

	# 穿过屏幕的随机速度
	var target := Vector2(randf_range(200, GlobalConfig.GAME_WIDTH - 200), randf_range(200, GlobalConfig.GAME_HEIGHT - 200))
	var dir := (target - start_pos).normalized()
	var speed := randf_range(40.0, 100.0)
	var velocity := dir * speed

	var color := DISTRACT_COLORS[randi() % DISTRACT_COLORS.size()]
	var lifetime := randf_range(2.0, 5.0)

	d.setup(radius, color, velocity, lifetime)
	add_child(d)


func clear_all() -> void:
	for child in get_children():
		child.queue_free()
