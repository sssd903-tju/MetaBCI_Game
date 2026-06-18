extends RefCounted
class_name EscapeMode

var total_digits := 4
var found_count := 0
var elapsed_time: float = 0.0
var escaped: bool = false
var focus_sum: float = 0.0
var focus_samples: int = 0


func start_new(digit_count: int) -> void:
	total_digits = digit_count
	found_count = 0
	elapsed_time = 0.0
	escaped = false
	focus_sum = 0.0
	focus_samples = 0


func digit_found() -> bool:
	found_count += 1
	return found_count >= total_digits


func track_focus(ratio: float) -> void:
	if not escaped:
		focus_sum += ratio
		focus_samples += 1


func avg_focus() -> float:
	return focus_sum / max(1, focus_samples)


func get_score() -> int:
	# 基础 100, 时间惩罚 -1/s, 专注加成
	var base := 100
	var time_penalty := int(elapsed_time * 2)
	var focus_bonus := int(avg_focus() * 20)
	return max(10, base - time_penalty + focus_bonus)


func get_rating() -> String:
	var s := get_score()
	if s >= 120: return "逃脱大师 🏆"
	if s >= 80:  return "密室高手 ⭐"
	if s >= 50:  return "成功逃脱 ✓"
	return "差点成功 💪"
