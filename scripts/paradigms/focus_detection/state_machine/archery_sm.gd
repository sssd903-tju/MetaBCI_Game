extends Node
class_name ArcheryStateMachine
## StateMachine — 凝神一矢状态机
##
## READY → AIMING → FIRED → SCORING → (循环) → FINISHED

enum State { READY, AIMING, FIRED, SCORING, FINISHED }

signal state_changed(old: State, new: State)
signal ready_started()
signal aiming_started()
signal fired()
signal scoring_started(ring: int, points: int)
signal finished(final_score: int)

var current_state := State.READY
var _state_timer := 0.0

# 各阶段时长
const READY_TIME := 2.0
const AIMING_TIME := 5.0
const FIRED_TIME := 1.0
const SCORING_TIME := 2.0

# 总轮数
const TOTAL_ROUNDS := 10
var current_round := 0
var total_score := 0
var _pending_ring := 0
var _pending_points := 0


func _ready() -> void:
	_enter_ready()


func _process(delta: float) -> void:
	if current_state == State.FINISHED:
		return

	_state_timer -= delta

	match current_state:
		State.READY:
			if _state_timer <= 0.0:
				_enter_aiming()

		State.AIMING:
			if _state_timer <= 0.0:
				# 时间到，自动射箭 — 调用者负责传入命中的环数和分数
				pass  # 由外部 trigger_fire() 触发

		State.FIRED:
			if _state_timer <= 0.0:
				_enter_scoring()

		State.SCORING:
			if _state_timer <= 0.0:
				_next_round()


## 外部调用：AIMING 计时到期后触发射箭
func trigger_fire(ring: int, points: int) -> void:
	if current_state != State.AIMING:
		return

	_pending_ring = ring
	_pending_points = points
	current_round += 1
	total_score += points

	_change_state(State.FIRED)
	_state_timer = FIRED_TIME
	fired.emit()


func _enter_ready() -> void:
	_change_state(State.READY)
	_state_timer = READY_TIME
	ready_started.emit()


func _enter_aiming() -> void:
	_change_state(State.AIMING)
	_state_timer = AIMING_TIME
	aiming_started.emit()


func _enter_scoring() -> void:
	if _pending_ring > 0:
		_change_state(State.SCORING)
	else:
		# 脱靶
		_change_state(State.SCORING)

	_state_timer = SCORING_TIME
	scoring_started.emit(_pending_ring, _pending_points)


func _next_round() -> void:
	if current_round >= TOTAL_ROUNDS:
		_change_state(State.FINISHED)
		finished.emit(total_score)
	else:
		_enter_ready()


func _change_state(new_state: State) -> void:
	var old := current_state
	current_state = new_state
	state_changed.emit(old, new_state)


func get_aiming_progress() -> float:
	"""返回瞄准进度 0.0~1.0"""
	if current_state != State.AIMING:
		return 0.0
	return 1.0 - (_state_timer / AIMING_TIME)
