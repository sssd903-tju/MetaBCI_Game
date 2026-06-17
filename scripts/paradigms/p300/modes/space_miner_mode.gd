extends RefCounted
class_name SpaceMinerMode

var total_score: int = 0
var total_collected: int = 0
var current_round: int = 0

const TOTAL_ROUNDS := 6


func start_new() -> void:
	total_score = 0
	total_collected = 0
	current_round = 0


func collect(value: int) -> Dictionary:
	current_round += 1
	total_collected += 1
	total_score += value
	return {"value": value, "total": total_score}


func is_game_over() -> bool:
	return current_round >= TOTAL_ROUNDS


func get_rating() -> String:
	if total_score >= 200:  return "星际矿王 👑"
	if total_score >= 120:  return "资深矿工 ⭐"
	if total_score >= 60:   return "初级矿工 ✓"
	return "采矿学徒 💪"


func get_summary() -> Dictionary:
	return {
		"total_score": total_score,
		"collected": total_collected,
		"rating": get_rating(),
	}
