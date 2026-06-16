extends Control
## FocusBar — 实时专注度指示条
##
## 显示当前专注度水平（绿/黄/红三色进度条）

@export var bar_height := 24.0
@export var animation_speed := 3.0

var _target_ratio := 0.0
var _display_ratio := 0.0
var _bar_rect: ColorRect
var _bg_rect: ColorRect
var _label: Label
var _quality_rect: ColorRect


func _ready() -> void:
	_setup_ui()
	# 监听 BCI 数据
	BCIConnector.focus_data_received.connect(_on_focus_data)
	BCIConnector.eeg_quality_changed.connect(_on_quality_changed)


func _exit_tree() -> void:
	if BCIConnector.focus_data_received.is_connected(_on_focus_data):
		BCIConnector.focus_data_received.disconnect(_on_focus_data)
	if BCIConnector.eeg_quality_changed.is_connected(_on_quality_changed):
		BCIConnector.eeg_quality_changed.disconnect(_on_quality_changed)


func _setup_ui() -> void:
	# 背景
	var panel := Panel.new()
	panel.size = Vector2(320, bar_height + 36)
	panel.position = Vector2(20, 20)
	add_child(panel)

	var style := StyleBoxFlat.new()
	style.bg_color = GlobalConfig.PANEL_BG
	style.border_width_left = 1
	style.border_width_right = 1
	style.border_width_top = 1
	style.border_width_bottom = 1
	style.border_color = GlobalConfig.PANEL_BORDER
	style.corner_radius_top_left = 8
	style.corner_radius_top_right = 8
	style.corner_radius_bottom_right = 8
	style.corner_radius_bottom_left = 8
	panel.add_theme_stylebox_override("panel", style)

	var container := VBoxContainer.new()
	container.position = Vector2(12, 8)
	container.size = Vector2(296, bar_height + 20)
	panel.add_child(container)

	# 标签
	_label = Label.new()
	_label.text = "专注度: --"
	_label.add_theme_color_override("font_color", GlobalConfig.UI_TEXT_PRIMARY)
	_label.add_theme_font_size_override("font_size", 14)
	container.add_child(_label)

	# 进度条背景
	_bg_rect = ColorRect.new()
	_bg_rect.size = Vector2(296, bar_height)
	_bg_rect.color = Color("D5CFBF")
	container.add_child(_bg_rect)

	# 信号质量指示
	_quality_rect = ColorRect.new()
	_quality_rect.size = Vector2(296, 4)
	_quality_rect.color = Color.DIM_GRAY
	container.add_child(_quality_rect)

	# 进度条前景（在背景之上）
	_bar_rect = ColorRect.new()
	_bar_rect.size = Vector2(0, bar_height)
	_bar_rect.color = GlobalConfig.UI_SUCCESS
	_bg_rect.add_child(_bar_rect)


func _on_focus_data(ratio: float, _theta: float, _alpha: float, _beta: float) -> void:
	_target_ratio = ratio


func _on_quality_changed(value: float) -> void:
	_quality_rect.color = focus_to_color(value * 2.0)  # 映射质量值到颜色


func _process(delta: float) -> void:
	# 平滑动画
	_display_ratio = lerpf(_display_ratio, _target_ratio, animation_speed * delta)

	# 更新进度条
	var max_width := _bg_rect.size.x
	var fill_ratio := clampf(_display_ratio / 4.0, 0.0, 1.0)  # 最大显示 4.0 的比值
	_bar_rect.size.x = lerpf(_bar_rect.size.x, max_width * fill_ratio, animation_speed * delta)

	# 颜色渐变
	_bar_rect.color = focus_to_color(_display_ratio)

	# 文字
	var level := "低"
	if _display_ratio >= GlobalConfig.FOCUS_HIGH_THRESHOLD:
		level = "高 ⬆"
	elif _display_ratio >= GlobalConfig.FOCUS_MEDIUM_THRESHOLD:
		level = "中 →"

	_label.text = "专注度: %.1f  [%s]" % [_display_ratio, level]


## 设置目标专注度（用于测试/调试）
func set_focus(ratio: float) -> void:
	_target_ratio = ratio
