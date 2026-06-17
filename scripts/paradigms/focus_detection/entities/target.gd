extends Node2D
class_name ArcheryTarget
## Target — 靶子实体，1-10 环同心圆

# 总半径 (像素)
@export var total_radius := 240.0

# 10 个环，每环宽度 = total_radius / 10
var ring_width: float:
	get: return total_radius / 10.0

# 环颜色 (从外到内 1→10)
const RING_COLORS := [
	Color("ECF0F2"),  #  1环 — 冷白
	Color("ECF0F2"),  #  2环
	Color("6E9DBF"),  #  3环 — 蓝
	Color("6E9DBF"),  #  4环
	Color("7B9DB5"),  #  5环 — 灰蓝
	Color("7B9DB5"),  #  6环
	Color("B8A87A"),  #  7环 — 冷金
	Color("B8A87A"),  #  8环
	Color("C45A5A"),  #  9环 — 冷红
	Color("C45A5A"),  # 10环 — 红心
]

# 环对应分数 1-10
const RING_SCORES := [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


func _ready() -> void:
	queue_redraw()


func _draw() -> void:
	for i in range(9, -1, -1):  # 从外到内画
		var radius := (i + 1) * ring_width
		draw_circle(Vector2.ZERO, radius, RING_COLORS[i])

	# 环线
	for i in range(1, 11):
		var radius := i * ring_width
		draw_arc(Vector2.ZERO, radius, 0, TAU, 32, Color.BLACK, 0.5)


## 计算命中环数 (1-10, 0=脱靶)
func get_ring(distance_from_center: float) -> int:
	if distance_from_center > total_radius:
		return 0  # 脱靶
	for i in range(1, 11):
		if distance_from_center <= i * ring_width:
			return 11 - i
	return 0


## 获取某环的半径
func get_ring_radius(ring: int) -> float:
	return (11 - ring) * ring_width


## 环心位置
func get_center() -> Vector2:
	return global_position
