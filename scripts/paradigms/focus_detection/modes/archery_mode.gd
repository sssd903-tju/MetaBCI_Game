extends RefCounted
class_name ArcheryMode
## Mode — 凝神一矢规则与计分

var total_score := 0
var current_round := 0
var round_scores: Array[int] = []
var round_rings: Array[int] = []

const TOTAL_ROUNDS := 10

## 优秀分数阈值
const EXCELLENT_THRESHOLD := 80
const GOOD_THRESHOLD := 50


func start_new_game() -> void:
	total_score = 0
	current_round = 0
	round_scores.clear()
	round_rings.clear()


func record_shot(ring: int, focus_ratio: float) -> Dictionary:
	"""记录一次射箭结果
	Args:
	    ring: 命中环数 0-10, 0=脱靶
	    focus_ratio: 射箭时刻的专注度
	Returns:
	    {ring, base_points, focus_bonus, total_points}
	"""
	current_round += 1
	round_rings.append(ring)

	# 基础分 = 环数
	var base_points := ring

	# 专注度加成 (专注度高时额外加分)
	var focus_bonus := 0.0
	if ring > 0:
		if focus_ratio >= GlobalConfig.FOCUS_HIGH_THRESHOLD:
			focus_bonus = base_points * 0.5  # 高专注 +50%
		elif focus_ratio >= GlobalConfig.FOCUS_MEDIUM_THRESHOLD:
			focus_bonus = base_points * 0.2  # 中专注 +20%

	var total_points := int(round(base_points + focus_bonus))
	total_score += total_points
	round_scores.append(total_points)

	return {
		"ring": ring,
		"base_points": base_points,
		"focus_bonus": int(focus_bonus),
		"total_points": total_points,
	}


func is_game_over() -> bool:
	return current_round >= TOTAL_ROUNDS


func get_rating() -> String:
	var avg := float(total_score) / float(max(1, current_round))
	if avg >= 8.0:
		return "神射手 🏆"
	elif avg >= 6.0:
		return "优秀射手 ⭐"
	elif avg >= 4.0:
		return "合格射手 ✓"
	elif avg >= 2.0:
		return "需要练习 📘"
	else:
		return "继续加油 💪"


func get_summary() -> Dictionary:
	return {
		"total_score": total_score,
		"rounds": current_round,
		"rings": round_rings.duplicate(),
		"scores": round_scores.duplicate(),
		"rating": get_rating(),
		"avg_score": float(total_score) / float(max(1, current_round)),
	}
