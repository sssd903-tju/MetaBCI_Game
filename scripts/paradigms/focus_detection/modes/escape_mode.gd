extends RefCounted
class_name EscapeMode

enum Layer { FIND_CODE, UNLOCK_SAFE, ESCAPE, DONE }

var current_layer: Layer = Layer.FIND_CODE
var found_digits: int = 0
var total_digits := 4
var code: String = ""
var elapsed_time: float = 0.0
var focus_sum: float = 0.0
var focus_samples: int = 0
var attempts: int = 0


func start_new(digit_count: int) -> void:
	current_layer = Layer.FIND_CODE
	found_digits = 0
	total_digits = digit_count
	code = _generate_code()
	elapsed_time = 0.0
	focus_sum = 0.0
	focus_samples = 0
	attempts = 0


func _generate_code() -> String:
	var c := ""
	for i in range(4):
		c += str(randi_range(1, 9))
	return c


func digit_found() -> bool:
	found_digits += 1
	if found_digits >= total_digits:
		current_layer = Layer.UNLOCK_SAFE
		return true  # all found
	return false


func get_code() -> String:
	return code


func try_unlock(input_code: String) -> bool:
	attempts += 1
	if input_code == code:
		current_layer = Layer.ESCAPE
		return true
	return false


func escape() -> void:
	current_layer = Layer.DONE


func track_focus(ratio: float) -> void:
	if current_layer == Layer.DONE:
		return
	focus_sum += ratio
	focus_samples += 1


func avg_focus() -> float:
	return focus_sum / max(1, focus_samples)


func get_score() -> int:
	var base := 100
	var time_penalty := int(elapsed_time * 2)
	var attempt_penalty := attempts * 5
	var focus_bonus := int(avg_focus() * 20)
	return max(10, base - time_penalty - attempt_penalty + focus_bonus)


func get_rating() -> String:
	var s := get_score()
	if s >= 120: return "逃脱大师 🏆"
	if s >= 80:  return "密室高手 ⭐"
	if s >= 50:  return "成功逃脱 ✓"
	return "继续努力 💪"
