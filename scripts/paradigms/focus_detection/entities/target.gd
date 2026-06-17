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
	Color("F5F5F5"),  #  1环 — 白
	Color("F5F5F5"),  #  2环
	Color("3A3A3A"),  #  3环 — 黑
	Color("3A3A3A"),  #  4环
	Color("4A90D9"),  #  5环 — 蓝
	Color("4A90D9"),  #  6环
	Color("D94040"),  #  7环 — 红
	Color("D94040"),  #  8环
	Color("F0C040"),  #  9环 — 金
	Color("F0C040"),  # 10环 — 金心
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
