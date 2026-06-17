extends Node
class_name WhackMoleStateMachine
## StateMachine — 打地鼠状态机
##
## READY → SHOW → DECODE → HIT/MISS → SCORE → 循环 → FINISHED

enum State { READY, SHOW, DECODE, SCORE, FINISHED }

signal state_changed(old: State, new: State)
signal ready_started()
signal mole_shown(hole_index: int)
signal decode_started()
signal hit_detected(hole_index: int)
signal miss_detected()
@warning_ignore("unused_signal")
signal finished(final_score: int)

var current_state: State = State.READY
var _state_timer: float = 0.0

const READY_TIME := 2.0
const SHOW_TIME := 0.5      # 地鼠冒出动画
const DECODE_TIME := 1.0     # SSVEP 解码窗口
const SCORE_TIME := 1.5      # 结果显示


func _ready() -> void:
	_enter_ready()


func _process(delta: float) -> void:
	if current_state == State.FINISHED:
		return

	_state_timer -= delta

	match current_state:
		State.READY:
			if _state_timer <= 0.0:
				_enter_show()

		State.SHOW:
			if _state_timer <= 0.0:
				_enter_decode()

		State.DECODE:
			# 等待外部 trigger_hit / trigger_miss
			pass

		State.SCORE:
			if _state_timer <= 0.0:
				_next_round()


func _enter_ready() -> void:
	change_state(State.READY)
	_state_timer = READY_TIME
	ready_started.emit()


func _enter_show() -> void:
	change_state(State.SHOW)
	_state_timer = SHOW_TIME
	mole_shown.emit(0)  # hole_index 由外部设置


func _enter_decode() -> void:
	change_state(State.DECODE)
	_state_timer = DECODE_TIME
	decode_started.emit()


func trigger_hit(hole_index: int) -> void:
	if current_state != State.DECODE:
		return
	change_state(State.SCORE)
	_state_timer = SCORE_TIME
	hit_detected.emit(hole_index)


func trigger_miss() -> void:
	if current_state != State.DECODE:
		return
	change_state(State.SCORE)
	_state_timer = SCORE_TIME
	miss_detected.emit()


func _next_round() -> void:
	_enter_ready()


func change_state(new_state: State) -> void:
	var old := current_state
	current_state = new_state
	state_changed.emit(old, new_state)


func get_decode_progress() -> float:
	if current_state != State.DECODE:
		return 0.0
	return 1.0 - (_state_timer / DECODE_TIME)
