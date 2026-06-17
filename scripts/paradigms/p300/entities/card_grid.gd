extends Control
class_name CardGrid
## CardGrid — 6 张卡牌 + P300 伪随机闪烁

const SYMBOLS := ["A♠", "K♥", "Q♦", "J♣", "10♠", "9♥"]
const CARD_W := 100.0
const CARD_H := 140.0
const GAP := 20.0
const FLASH_ON := 0.25   # 亮时间
const FLASH_OFF := 0.1   # 灭间隔

signal scan_finished()

var cards: Array[MindCard] = []
var _scanning: bool = false
var _scan_round: int = 0
var _scan_total_rounds := 5
var _flash_idx: int = -1
var _flash_timer: float = 0.0
var _flash_on_phase: bool = false
var _round_sequence: Array = []
var _seq_pos: int = 0
var _target_idx: int = -1
var _guessed_idx: int = -1


func _ready() -> void:
	position = Vector2(
		(GlobalConfig.GAME_WIDTH - 6 * (CARD_W + GAP) + GAP) / 2.0,
		(GlobalConfig.GAME_HEIGHT - CARD_H) / 2.0
	)
	size = Vector2(6 * (CARD_W + GAP), CARD_H)

	for i in range(6):
		var c := MindCard.new()
		c.symbol = SYMBOLS[i]
		c.card_index = i
		c.position = Vector2(i * (CARD_W + GAP), 0)
		add_child(c)
		cards.append(c)


func set_target(idx: int) -> void:
	_target_idx = idx


func start_scan(rounds: int = 5) -> void:
	_scanning = true
	_scan_round = 0
	_scan_total_rounds = rounds
	_new_round()


func _new_round() -> void:
	_round_sequence = range(6)
	_round_sequence.shuffle()
	_seq_pos = 0
	_flash_on_phase = false
	_flash_timer = FLASH_OFF
	# 熄掉所有
	for c in cards:
		c.set_flash(false)


func _process(delta: float) -> void:
	if not _scanning:
		return

	_flash_timer -= delta
	if _flash_timer > 0.0:
		return

	if _flash_on_phase:
		# 灭了当前, 下一个
		if _flash_idx >= 0:
			cards[_flash_idx].set_flash(false)
		_seq_pos += 1
		if _seq_pos >= 6:
			_scan_round += 1
			if _scan_round >= _scan_total_rounds:
				_scanning = false
				_flash_idx = -1
				# 模拟猜测 (70% 命中)
				_guessed_idx = _target_idx if randf() < 0.7 else randi() % 6
				scan_finished.emit()
				return
			_new_round()
			return
		_flash_idx = _round_sequence[_seq_pos]
		cards[_flash_idx].set_flash(true)
		_flash_timer = FLASH_ON
		_flash_on_phase = true
	else:
		_flash_idx = _round_sequence[_seq_pos]
		cards[_flash_idx].set_flash(true)
		_flash_timer = FLASH_ON
		_flash_on_phase = true


func get_guessed() -> int:
	return _guessed_idx


func reveal_card(idx: int) -> void:
	cards[idx].flip(true)


func reveal_all() -> void:
	for c in cards:
		c.flip(true)


func hide_all() -> void:
	for c in cards:
		c.flip(false)
