extends Control
class_name AsteroidField

const ORE_POOL := [
	{"name": "钻石", "icon": "💎", "value": 50},
	{"name": "水晶", "icon": "🔮", "value": 40},
	{"name": "金牌", "icon": "🥇", "value": 30},
	{"name": "银牌", "icon": "🥈", "value": 20},
	{"name": "铁矿", "icon": "⛏️", "value": 15},
	{"name": "陨石", "icon": "☄️", "value": 10},
]

const FLASH_ON := 0.25
const FLASH_OFF := 0.1

signal scan_finished()
signal collect_finished(idx: int)

var asteroids: Array[Asteroid] = []
var _scanning: bool = false
var _scan_round: int = 0
var _scan_total_rounds := 3
var _flash_idx: int = -1
var _flash_timer: float = 0.0
var _flash_on_phase: bool = false
var _round_sequence: Array = []
var _seq_pos: int = 0
var _guessed_idx: int = -1
var _ship: ColorRect
var _ship_target: Vector2


func _ready() -> void:
	size = Vector2(GlobalConfig.GAME_WIDTH, 400)
	position = Vector2(0, (GlobalConfig.GAME_HEIGHT - 400) / 2.0)

	# 布局6个小行星
	var positions := [
		Vector2(150, 100), Vector2(400, 60),  Vector2(650, 100),
		Vector2(250, 280), Vector2(500, 280), Vector2(750, 220),
	]

	for i in range(6):
		var a := Asteroid.new()
		a.setup(ORE_POOL[i].name, ORE_POOL[i].icon, ORE_POOL[i].value)
		a.index = i
		a.position = positions[i]
		add_child(a)
		asteroids.append(a)

	# 飞船
	_ship = ColorRect.new()
	_ship.color = Color("4A90D9")
	_ship.size = Vector2(24, 24)
	_ship.position = Vector2(-40, 200)
	add_child(_ship)


func start_scan(rounds: int = 3) -> void:
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
	for a in asteroids:
		a.set_flash(false)


func _process(delta: float) -> void:
	if not _scanning:
		return

	_flash_timer -= delta
	if _flash_timer > 0.0:
		return

	if _flash_on_phase:
		if _flash_idx >= 0:
			asteroids[_flash_idx].set_flash(false)
		_seq_pos += 1
		if _seq_pos >= 6:
			_scan_round += 1
			if _scan_round >= _scan_total_rounds:
				_scanning = false
				_flash_idx = -1
				_guessed_idx = randi() % 6
				scan_finished.emit()
				return
			_new_round()
			return
		_flash_idx = _round_sequence[_seq_pos]
		asteroids[_flash_idx].set_flash(true)
		_flash_timer = FLASH_ON
		_flash_on_phase = true
	else:
		_flash_idx = _round_sequence[_seq_pos]
		asteroids[_flash_idx].set_flash(true)
		_flash_timer = FLASH_ON
		_flash_on_phase = true


func get_guessed() -> int:
	return _guessed_idx


func fly_ship_to(idx: int) -> void:
	var target := asteroids[idx].position + Vector2(50, 50)
	var tween := create_tween()
	tween.tween_property(_ship, "position", target, 1.0)
	tween.tween_callback(func(): collect_finished.emit(idx))


func reset_ship() -> void:
	_ship.position = Vector2(-40, 200)


func collect_asteroid(idx: int) -> Dictionary:
	var a := asteroids[idx]
	var result := {"name": a.ore_name, "value": a.ore_value}
	# 更换新矿石
	var new_ore := ORE_POOL[randi() % ORE_POOL.size()]
	a.setup(new_ore.name, new_ore.icon, new_ore.value)
	return result
