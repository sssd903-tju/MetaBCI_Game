extends Control
## MainMenu — 主菜单界面
##
## 显示所有可用范式，支持键盘选择与进入

var _paradigm_buttons: Array[Button] = []
var _selected_index := 0
var _title_label: Label
var _status_label: Label
var _bci_indicator: Panel


func _ready() -> void:
	_setup_background()
	_setup_title()
	_setup_paradigm_list()
	_setup_status()

	# 监听 BCI 连接状态
	BCIConnector.bci_connected.connect(_on_bci_connected)
	BCIConnector.bci_disconnected.connect(_on_bci_disconnected)

	_update_selection()
	_update_bci_status()


func _exit_tree() -> void:
	if BCIConnector.bci_connected.is_connected(_on_bci_connected):
		BCIConnector.bci_connected.disconnect(_on_bci_connected)
	if BCIConnector.bci_disconnected.is_connected(_on_bci_disconnected):
		BCIConnector.bci_disconnected.disconnect(_on_bci_disconnected)


func _setup_background() -> void:
	var bg := ColorRect.new()
	bg.color = GlobalConfig.BG_WARM_CREAM
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)


func _setup_title() -> void:
	_title_label = Label.new()
	_title_label.text = "MetaBCI 脑机接口游戏范式平台"
	_title_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_title_label.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_PRIMARY)
	_title_label.add_theme_font_size_override("font_size", 36)
	_title_label.position = Vector2(0, 120)
	_title_label.size = Vector2(GlobalConfig.GAME_WIDTH, 60)
	add_child(_title_label)

	var subtitle := Label.new()
	subtitle.text = "Brain-Computer Interface Game Paradigm Platform"
	subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	subtitle.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_SECONDARY)
	subtitle.add_theme_font_size_override("font_size", 16)
	subtitle.position = Vector2(0, 175)
	subtitle.size = Vector2(GlobalConfig.GAME_WIDTH, 30)
	add_child(subtitle)

	var hint := Label.new()
	hint.text = "↑↓ 选择范式   Enter 进入   Q 退出"
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_SECONDARY)
	hint.add_theme_font_size_override("font_size", 13)
	hint.position = Vector2(0, 650)
	hint.size = Vector2(GlobalConfig.GAME_WIDTH, 30)
	add_child(hint)


func _setup_paradigm_list() -> void:
	var paradigms := [
		{"name": "🎯 专注度检测", "desc": "实时检测注意力水平，控制角色跨越平台", "type": GlobalConfig.ParadigmType.FOCUS_DETECTION},
		{"name": "👁 SSVEP 稳态视觉诱发电位", "desc": "通过注视闪烁目标实现脑控选择", "type": GlobalConfig.ParadigmType.SSVEP},
		{"name": "🧠 P300 事件相关电位", "desc": "基于 Oddball 范式的脑机接口拼写器", "type": GlobalConfig.ParadigmType.P300},
		{"name": "✋ MI 运动想象", "desc": "想象左右手运动驱动游戏角色", "type": GlobalConfig.ParadigmType.MI},
	]

	var start_y := 250
	var card_height := 80
	var card_width := 500
	var gap := 16

	for i in range(paradigms.size()):
		var p: Dictionary = paradigms[i]

		# 卡片容器
		var card := Panel.new()
		card.position = Vector2((GlobalConfig.GAME_WIDTH - card_width) / 2.0, start_y + i * (card_height + gap))
		card.size = Vector2(card_width, card_height)
		card.name = "Card_%d" % i

		var card_style := StyleBoxFlat.new()
		card_style.bg_color = GlobalConfig.PANEL_BG
		card_style.border_width_left = 2
		card_style.border_width_right = 2
		card_style.border_width_top = 2
		card_style.border_width_bottom = 2
		card_style.border_color = GlobalConfig.PANEL_BORDER
		card_style.corner_radius_top_left = 12
		card_style.corner_radius_top_right = 12
		card_style.corner_radius_bottom_right = 12
		card_style.corner_radius_bottom_left = 12
		card.add_theme_stylebox_override("panel", card_style)
		add_child(card)

		# 范式名称
		var name_label := Label.new()
		name_label.text = p["name"]
		name_label.position = Vector2(20, 14)
		name_label.size = Vector2(card_width - 40, 28)
		name_label.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_PRIMARY)
		name_label.add_theme_font_size_override("font_size", 18)
		card.add_child(name_label)

		# 范式描述
		var desc_label := Label.new()
		desc_label.text = p["desc"]
		desc_label.position = Vector2(20, 42)
		desc_label.size = Vector2(card_width - 40, 24)
		desc_label.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_SECONDARY)
		desc_label.add_theme_font_size_override("font_size", 13)
		card.add_child(desc_label)

		# 保存按钮引用（透明按钮覆盖卡片）
		var btn := Button.new()
		btn.flat = true
		btn.position = Vector2.ZERO
		btn.size = card.size
		btn.pressed.connect(_on_paradigm_selected.bind(i, p["type"]))
		card.add_child(btn)
		_paradigm_buttons.append(btn)


func _setup_status() -> void:
	# 状态栏容器（圆形指示灯 + 文字）
	var container := HBoxContainer.new()
	container.name = "StatusContainer"
	container.alignment = BoxContainer.ALIGNMENT_CENTER
	container.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	container.position = Vector2(0, -50)
	container.add_theme_constant_override("separation", 8)
	add_child(container)

	# 圆形指示灯
	_bci_indicator = Panel.new()
	_bci_indicator.size = Vector2(14, 14)
	var circle_style := StyleBoxFlat.new()
	circle_style.bg_color = Color.RED
	circle_style.set_corner_radius_all(7)
	_bci_indicator.add_theme_stylebox_override("panel", circle_style)
	container.add_child(_bci_indicator)

	# 状态文字
	_status_label = Label.new()
	_status_label.text = "BCI 状态: 检测中..."
	_status_label.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_SECONDARY)
	_status_label.add_theme_font_size_override("font_size", 13)
	container.add_child(_status_label)


func _on_paradigm_selected(_index: int, paradigm_type: GlobalConfig.ParadigmType) -> void:
	print("[MainMenu] 选择范式: ", GlobalConfig.PARADIGM_NAMES[paradigm_type])
	ParadigmManager.switch_to(paradigm_type)


func _on_bci_connected() -> void:
	_update_bci_status()


func _on_bci_disconnected() -> void:
	_update_bci_status()


func _update_bci_status() -> void:
	var style := _bci_indicator.get_theme_stylebox("panel") as StyleBoxFlat
	if BCIConnector._connected:
		_status_label.text = "BCI 已连接 — 脑电数据就绪"
		_status_label.add_theme_color_override("font_color", GlobalConfig.UI_SUCCESS)
		style.bg_color = GlobalConfig.UI_SUCCESS
	else:
		_status_label.text = "BCI 未连接 — 等待脑电数据..."
		_status_label.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_SECONDARY)
		style.bg_color = Color.RED


func _update_selection() -> void:
	for i in range(_paradigm_buttons.size()):
		var card := _paradigm_buttons[i].get_parent() as Panel
		var style := card.get_theme_stylebox("panel").duplicate() as StyleBoxFlat
		if i == _selected_index:
			style.border_color = GlobalConfig.PLATFORM_NORMAL
			style.border_width_left = 3
			style.border_width_right = 3
			style.border_width_top = 3
			style.border_width_bottom = 3
			style.bg_color = GlobalConfig.PLATFORM_NORMAL.lightened(0.75)
		else:
			style.border_color = GlobalConfig.PANEL_BORDER
			style.border_width_left = 2
			style.border_width_right = 2
			style.border_width_top = 2
			style.border_width_bottom = 2
			style.bg_color = GlobalConfig.PANEL_BG
		card.add_theme_stylebox_override("panel", style)


func _input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_up"):
		_selected_index = (_selected_index - 1 + _paradigm_buttons.size()) % _paradigm_buttons.size()
		_update_selection()
		accept_event()

	elif event.is_action_pressed("ui_down"):
		_selected_index = (_selected_index + 1) % _paradigm_buttons.size()
		_update_selection()
		accept_event()

	elif event.is_action_pressed("ui_accept"):
		if _paradigm_buttons.size() > 0:
			_paradigm_buttons[_selected_index].emit_signal("pressed")
		accept_event()

	elif event.is_action_pressed("ui_cancel"):
		get_tree().quit()
		accept_event()
