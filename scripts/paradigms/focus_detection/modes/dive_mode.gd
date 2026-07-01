extends RefCounted
class_name DiveMode

var score: int = 0
var specimens_found: int = 0
var photos_taken: int = 0
var oxygen: float = 90.0
var elapsed: float = 0.0
const MAX_O2 := 90.0
const SPECIMEN_TARGET := 5


func start() -> void:
	score = 0; specimens_found = 0; photos_taken = 0
	oxygen = MAX_O2; elapsed = 0.0


func collect_specimen() -> void:
	specimens_found += 1


func take_photo() -> void:
	photos_taken += 1; score += 30


func refill_o2() -> void:
	oxygen = minf(MAX_O2, oxygen + 25.0)


func is_complete() -> bool:
	return specimens_found >= SPECIMEN_TARGET


func is_dead() -> bool:
	return oxygen <= 0.0


func get_rating() -> String:
	if score >= 100: return "海洋守护者 🌊"
	if score >= 60:  return "深海探险家 ⭐"
	return "见习潜水员 ✓"
