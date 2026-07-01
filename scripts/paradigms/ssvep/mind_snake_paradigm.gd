extends BaseParadigm
## MindSnakeParadigm — 脑控贪吃蛇

enum State { READY, PLAYING, GAME_OVER }

var _state: State = State.READY
var _snake: MindSnake
var _arrows: SSVEPArrows
var _food: SnakeFood
var _mode: MindSnakeMode
var _hud: MindSnakeHUD
var _state_timer: float = 0.0
var _decode_timer: float = 0.0
var _decoded_dir: String = ""


func _ready() -> void:
	paradigm_type = GlobalConfig.ParadigmType.SSVEP
	super._ready()


func _on_paradigm_start() -> void:
	_setup_background()
	_setup_game()
	_enter_ready()


func _on_paradigm_end() -> void:
	print("[贪吃蛇] 结束, 分数: %d" % _mode.score)


func _on_bci_data(_data: Dictionary) -> void:
	pass


func _on_ssvep_result(_freq: float, target_index: int) -> void:
	var dirs := ["up", "right", "down", "left"]
	if target_index >= 0 and target_index < dirs.size():
		_decoded_dir = dirs[target_index]


# --- 场景 ---

func _setup_background() -> void:
	var bg := ColorRect.new()
	bg.name = "Background"
	bg.color = GlobalConfig.BG_WARM_CREAM
	bg.size = Vector2(GlobalConfig.GAME_WIDTH, GlobalConfig.GAME_HEIGHT)
	bg.position = Vector2.ZERO
	add_child(bg)
	move_child(bg, 0)


func _setup_game() -> void:
	_snake = MindSnake.new()
	_snake.name = "Snake"
	_snake.reset()
	add_child(_snake)

	_arrows = SSVEPArrows.new()
	_arrows.name = "SSVEPArrows"
	add_child(_arrows)

	_food = SnakeFood.new()
	_food.name = "Food"
	add_child(_food)

	_mode = MindSnakeMode.new()
	_mode.start_new()

	_hud = MindSnakeHUD.new()
	_hud.name = "HUD"
	_hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_hud)

	BCIConnector.ssvep_result_received.connect(_on_ssvep_result)


func _exit_tree() -> void:
	if BCIConnector.ssvep_result_received.is_connected(_on_ssvep_result):
		BCIConnector.ssvep_result_received.disconnect(_on_ssvep_result)


# --- 状态 ---

func _enter_ready() -> void:
	_state = State.READY
	_state_timer = 2.0
	_arrows.visible = false
	_hud.update_state("准备...")


func _enter_playing() -> void:
	_state = State.PLAYING
	_snake.paused = false
	_arrows.visible = true
	_hud.update_state("")
	_hud.update_score(0)
	_food.spawn(_snake.body)


func _enter_game_over() -> void:
	_state = State.GAME_OVER
	_hud.show_game_over(_mode.score, _mode.get_rating())


# --- 主循环 ---

func _process(delta: float) -> void:
	match _state:
		State.READY:
			_state_timer -= delta
			if _state_timer <= 0.0:
				_enter_playing()

		State.PLAYING:
			_arrows.follow(_snake.get_head_screen_pos())
			if not _snake.alive:
				_enter_game_over()
				return

			# SSVEP 解码 (每 1s 检查一次方向)
			_decode_timer += delta
			if _decode_timer >= 1.0:
				_decode_timer = 0.0
				if _decoded_dir != "":
					_snake.set_direction(_decoded_dir)
					_arrows.flash_decoded()
					_decoded_dir = ""

			# 检查吃食物
			var h: Vector2i = _snake.get_head()
			var f: Vector2i = _food.get_cell()
			if absi(h.x - f.x) <= 1 and absi(h.y - f.y) <= 1:
				_snake.grow()
				_snake.score += MindSnakeMode.FOOD_SCORE
				_mode.ate_food()
				_food.spawn(_snake.body)
				_hud.update_score(_mode.score)
				AudioManager.play_combo(1)

		State.GAME_OVER:
			pass


# --- 键盘 ---

func _input(event: InputEvent) -> void:
	if _state == State.GAME_OVER:
		if event.is_action_pressed("ui_accept"):
			_restart()
		elif event.is_action_pressed("ui_cancel"):
			ParadigmManager.go_to_main_menu()
		return

	if event.is_action_pressed("ui_cancel"):
		ParadigmManager.go_to_main_menu()

	# 方向键 → 立即改变方向
	if event is InputEventKey and event.pressed and _state == State.PLAYING:
		match event.keycode:
			KEY_UP, KEY_W:     _snake.set_direction("up"); _decoded_dir = "up"
			KEY_DOWN, KEY_S:   _snake.set_direction("down"); _decoded_dir = "down"
			KEY_LEFT, KEY_A:   _snake.set_direction("left"); _decoded_dir = "left"
			KEY_RIGHT, KEY_D:  _snake.set_direction("right"); _decoded_dir = "right"


func _restart() -> void:
	for child in get_children():
		if child.name != "Background":
			child.queue_free()
	await get_tree().process_frame
	_on_paradigm_start()
