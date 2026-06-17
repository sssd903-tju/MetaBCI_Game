extends Node
class_name MinerStateMachine

enum State { SCAN, FLYING, COLLECT, GAME_OVER }

signal scan_started()
signal flying_started(idx: int)
signal collected(ore_name: String, value: int)
signal finished()

var current_state: State = State.SCAN


func _ready() -> void:
	pass


func enter_scan() -> void:
	change_state(State.SCAN)
	scan_started.emit()


func trigger_fly(idx: int) -> void:
	change_state(State.FLYING)
	flying_started.emit(idx)


func trigger_collect(ore_name: String, value: int) -> void:
	change_state(State.COLLECT)
	collected.emit(ore_name, value)


func go_game_over() -> void:
	change_state(State.GAME_OVER)
	finished.emit()


func change_state(new_state: State) -> void:
	current_state = new_state
