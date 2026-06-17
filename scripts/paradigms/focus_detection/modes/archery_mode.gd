extends RefCounted
class_name ArcheryMode
## Mode — 凝神一矢规则与计分

var total_score := 0
var current_round := 0
var round_scores: Array[int] = []
var round_rings: Array[int] = []

# 激励机制
var combo := 0
var best_combo := 0
var bullseyes := 0  # 十环次数

const TOTAL_ROUNDS := 5
const COMBO_THRESHOLD := 7   # ≥7 环才计入 combo
const BULLSEYE_BONUS := 2    # 十环额外加分
const COMBO_BONUS := 1       # 每层 combo 额外加分


func start_new_game() -> void:
	total_score = 0
	current_round = 0
	combo = 0
	best_combo = 0
	bullseyes = 0
	round_scores.clear()
	round_rings.clear()


func record_shot(ring: int, focus_ratio: float) -> Dictionary:
	"""记录一次射箭结果
	Returns:
	    {ring, base_points, focus_bonus, combo_count, combo_bonus, bullseye_bonus, total_points, is_bullseye}
	"""
	current_round += 1
	round_rings.append(ring)

	var base_points := ring

	# --- 专注度加成 ---
	var focus_bonus := 0.0
	if ring > 0:
		if focus_ratio >= GlobalConfig.FOCUS_HIGH_THRESHOLD:
			focus_bonus = base_points * 0.5
		elif focus_ratio >= GlobalConfig.FOCUS_MEDIUM_THRESHOLD:
			focus_bonus = base_points * 0.2

	# --- Combo 连击 ---
	var combo_bonus_val := 0
	var is_bullseye := (ring == 10)
	var bullseye_bonus_val := 0

	if ring >= COMBO_THRESHOLD:
		combo += 1
		combo_bonus_val = combo * COMBO_BONUS
		if combo > best_combo:
			best_combo = combo
	else:
		combo = 0  # 低环或脱靶打断 combo

	# --- 十环奖励 ---
	if is_bullseye:
		bullseyes += 1
		bullseye_bonus_val = BULLSEYE_BONUS

	var total_points := int(round(base_points + focus_bonus + combo_bonus_val + bullseye_bonus_val))
	total_score += total_points
	round_scores.append(total_points)

	return {
		"ring": ring,
		"base_points": base_points,
		"focus_bonus": int(focus_bonus),
		"combo_count": combo,
		"combo_bonus": combo_bonus_val,
		"bullseye_bonus": bullseye_bonus_val,
		"total_points": total_points,
		"is_bullseye": is_bullseye,
	}


func is_game_over() -> bool:
	return current_round >= TOTAL_ROUNDS


func get_rating() -> String:
	var avg := float(total_score) / float(max(1, current_round))
	if avg >= 10.0:
		return "神射手 🏆"
	elif avg >= 7.0:
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
		"best_combo": best_combo,
		"bullseyes": bullseyes,
	}
