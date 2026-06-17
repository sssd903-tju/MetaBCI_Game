extends Node
class_name CardStateMachine

enum State { THINK, SCAN, REVEAL, FEEDBACK, GAME_OVER }

signal state_changed(old: State, new: State)
signal think_started()
signal scan_started()
signal reveal_started(idx: int)
signal correct()
signal wrong()
signal finished()

var current_state: State = State.THINK
var _state_timer: float = 0.0

const THINK_TIME := 3.0
const REVEAL_TIME := 1.5
const FEEDBACK_TIME := 1.5


func _ready() -> void:
	enter_think()


func _process(delta: float) -> void:
	if current_state == State.SCAN or current_state == State.GAME_OVER:
		return
	_state_timer -= delta
	if _state_timer <= 0.0:
		_tick()


func _tick() -> void:
	match current_state:
		State.THINK:
			enter_scan()
		State.REVEAL:
			enter_feedback(false)
		State.FEEDBACK:
			enter_think()


func enter_think() -> void:
	change_state(State.THINK)
	_state_timer = THINK_TIME
	think_started.emit()


func enter_scan() -> void:
	change_state(State.SCAN)
	scan_started.emit()


func trigger_reveal(guessed_idx: int) -> void:
	change_state(State.REVEAL)
	_state_timer = REVEAL_TIME
	reveal_started.emit(guessed_idx)


func enter_feedback(is_correct: bool) -> void:
	change_state(State.FEEDBACK)
	_state_timer = FEEDBACK_TIME
	if is_correct:
		correct.emit()
	else:
		wrong.emit()


func go_game_over() -> void:
	change_state(State.GAME_OVER)
	finished.emit()


func change_state(new_state: State) -> void:
	var old := current_state
	current_state = new_state
	state_changed.emit(old, new_state)
