extends Node2D
class_name MoleGrid
## MoleGrid — 洞口网格管理器，2×2 布局 4 个洞

# SSVEP 频率 (Hz) — 标准刺激频段
const FREQUENCIES := [8.0, 10.0, 12.0, 15.0]
const COLORS := [
	Color("D94040"),   # 红
	Color("4A90D9"),   # 蓝
	Color("F0C040"),   # 金
	Color("5A8A6A"),   # 绿
]

var holes: Array[MoleHole] = []
var active_hole_index: int = -1
var _grid_spacing := 240.0


func _ready() -> void:
	_setup_grid()


func _setup_grid() -> void:
	var cx := GlobalConfig.GAME_WIDTH / 2.0
	var cy := GlobalConfig.GAME_HEIGHT / 2.0 - 20
	var hs := _grid_spacing / 2.0

	var positions := [
		Vector2(cx - hs, cy - hs),
		Vector2(cx + hs, cy - hs),
		Vector2(cx - hs, cy + hs),
		Vector2(cx + hs, cy + hs),
	]

	for i in range(4):
		var hole := MoleHole.new()
		hole.name = "Hole%d" % (i + 1)
		hole.position = positions[i]
		hole.frequency = FREQUENCIES[i]
		hole.flicker_color = COLORS[i]
		add_child(hole)
		holes.append(hole)


## 随机洞口冒地鼠
func spawn_mole() -> int:
	# 避免连续同一个洞口
	var new_idx := active_hole_index
	while new_idx == active_hole_index:
		new_idx = randi() % holes.size()
	active_hole_index = new_idx
	holes[active_hole_index].show_mole()
	return active_hole_index


## 隐藏当前地鼠
func hide_current_mole() -> void:
	if active_hole_index >= 0:
		holes[active_hole_index].hide_mole()


## 获取当前激活洞口的频率
func get_active_frequency() -> float:
	if active_hole_index < 0:
		return 0.0
	return FREQUENCIES[active_hole_index]


## 根据检测到的频率匹配最近的洞 (返回 index, -1=未匹配)
func match_frequency(detected_freq: float, tolerance: float = 0.5) -> int:
	var best_idx := -1
	var best_diff := tolerance + 0.1
	for i in range(FREQUENCIES.size()):
		var diff := absf(detected_freq - FREQUENCIES[i])
		if diff < best_diff:
			best_diff = diff
			best_idx = i
	return best_idx


## 重置所有洞
func reset_all() -> void:
	for hole in holes:
		hole.hide_mole()
	active_hole_index = -1
