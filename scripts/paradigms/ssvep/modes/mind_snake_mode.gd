extends RefCounted
class_name MindSnakeMode
## Mode — 贪吃蛇计分

var score: int = 0
var length: int = 0
var food_eaten: int = 0

const FOOD_SCORE := 10


func start_new() -> void:
	score = 0
	length = 0
	food_eaten = 0


func ate_food() -> void:
	food_eaten += 1
	score += FOOD_SCORE


func get_rating() -> String:
	if score >= 200:  return "蛇王 🏆"
	if score >= 100:  return "大蛇 ⭐"
	if score >= 50:   return "小蛇 ✓"
	return "蚯蚓 💪"


func get_summary() -> Dictionary:
	return {
		"score": score,
		"food_eaten": food_eaten,
		"rating": get_rating(),
	}
