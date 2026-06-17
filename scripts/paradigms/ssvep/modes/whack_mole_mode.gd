extends RefCounted
class_name WhackMoleMode
## Mode — 打地鼠规则与计分

var total_score: int = 0
var hits: int = 0
var misses: int = 0
var combo: int = 0
var best_combo: int = 0
var current_round: int = 0

const TOTAL_ROUNDS := 10
const HIT_SCORE := 10
const COMBO_BONUS := 5   # 连击额外加分


func start_new_game() -> void:
	total_score = 0
	hits = 0
	misses = 0
	combo = 0
	best_combo = 0
	current_round = 0


func record_hit() -> Dictionary:
	combo += 1
	hits += 1
	current_round += 1
	if combo > best_combo:
		best_combo = combo

	var points := HIT_SCORE + (combo - 1) * COMBO_BONUS
	total_score += points

	return {
		"hit": true,
		"points": points,
		"combo": combo,
	}


func record_miss() -> Dictionary:
	combo = 0
	misses += 1
	current_round += 1

	return {
		"hit": false,
		"points": 0,
		"combo": 0,
	}


func is_game_over() -> bool:
	return current_round >= TOTAL_ROUNDS


func get_rating() -> String:
	var hit_rate := float(hits) / float(max(1, current_round))
	if hit_rate >= 0.9:
		return "地鼠终结者 🏆"
	elif hit_rate >= 0.7:
		return "快枪手 ⭐"
	elif hit_rate >= 0.5:
		return "初出茅庐 ✓"
	else:
		return "继续练习 💪"


func get_summary() -> Dictionary:
	return {
		"total_score": total_score,
		"hits": hits,
		"misses": misses,
		"best_combo": best_combo,
		"hit_rate": float(hits) / float(max(1, current_round)),
		"rating": get_rating(),
	}
