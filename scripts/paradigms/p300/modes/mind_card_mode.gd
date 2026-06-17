extends RefCounted
class_name MindCardMode

var total_score: int = 0
var correct: int = 0
var wrong: int = 0
var current_round: int = 0

const TOTAL_ROUNDS := 5
const CORRECT_SCORE := 20


func start_new() -> void:
	total_score = 0
	correct = 0
	wrong = 0
	current_round = 0


func record(result: bool) -> Dictionary:
	current_round += 1
	if result:
		correct += 1
		total_score += CORRECT_SCORE
	else:
		wrong += 1
	return {"correct": result, "score": total_score}


func is_game_over() -> bool:
	return current_round >= TOTAL_ROUNDS


func get_rating() -> String:
	var rate := float(correct) / float(max(1, current_round))
	if rate >= 0.8:  return "读心大师 🧠"
	if rate >= 0.6:  return "心灵感应 ⭐"
	if rate >= 0.4:  return "初学者 ✓"
	return "继续练习 💪"


func get_summary() -> Dictionary:
	return {
		"total_score": total_score,
		"correct": correct,
		"wrong": wrong,
		"rating": get_rating(),
	}
