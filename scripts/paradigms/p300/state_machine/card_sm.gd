extends Node
class_name CardStateMachine

enum State { THINK, SCAN, REVEAL, CONFIRM, GAME_OVER }

signal think_started()
signal scan_started()
signal reveal_started(idx: int)
signal confirm_started(idx: int)
signal answered_correct()
signal answered_wrong()
signal finished()

var current_state: State = State.THINK
var _state_timer: float = 0.0

const REVEAL_TIME := 1.5
const CONFIRM_TIME := 3.0


func enter_think() -> void:
	change_state(State.THINK)
	think_started.emit()


func enter_scan() -> void:
	change_state(State.SCAN)
	scan_started.emit()


func enter_confirm(guessed_idx: int) -> void:
	change_state(State.CONFIRM)
	_state_timer = CONFIRM_TIME
	confirm_started.emit(guessed_idx)


func answer(correct: bool) -> void:
	if current_state != State.CONFIRM:
		return
	if correct:
		answered_correct.emit()
	else:
		answered_wrong.emit()
	enter_think()


func go_game_over() -> void:
	change_state(State.GAME_OVER)
	finished.emit()


func _process(delta: float) -> void:
	if current_state == State.SCAN or current_state == State.THINK or current_state == State.GAME_OVER:
		return
	_state_timer -= delta
	if _state_timer <= 0.0:
		if current_state == State.REVEAL:
			enter_confirm(_guessed_idx)


var _guessed_idx: int = -1

func trigger_reveal(guessed_idx: int) -> void:
	_guessed_idx = guessed_idx
	change_state(State.REVEAL)
	_state_timer = REVEAL_TIME
	reveal_started.emit(guessed_idx)


func change_state(new_state: State) -> void:
	current_state = new_state
