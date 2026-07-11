extends Node2D

const PLATFORM_SCENE: PackedScene = preload("res://scenes/Platform.tscn")

const START_X: float = 140.0
const START_Y: float = 540.0
const START_WIDTH: float = 240.0
const START_PLATFORM_COUNT: int = 8
const BASE_SPAWN_DISTANCE_MIN: float = 180.0
const BASE_SPAWN_DISTANCE_MAX: float = 320.0
const HARD_SPAWN_DISTANCE_MIN: float = 245.0
const HARD_SPAWN_DISTANCE_MAX: float = 430.0
const BASE_PLATFORM_WIDTH_MIN: float = 120.0
const BASE_PLATFORM_WIDTH_MAX: float = 230.0
const HARD_PLATFORM_WIDTH_MIN: float = 86.0
const HARD_PLATFORM_WIDTH_MAX: float = 165.0
const PLATFORM_BUFFER_AHEAD: float = 1500.0
const PLATFORM_CLEANUP_BEHIND: float = 64.0
const CAMERA_LEAD_X: float = 557.6
const CAMERA_FIXED_Y: float = 340.0
const CAMERA_FOLLOW_SMOOTHNESS: float = 7.0
const CAMERA_MAX_SCROLL_SPEED: float = 880.0
const PLATFORM_MOTION_SCALE: float = 0.86
const LANDING_X_MARGIN: float = 3.0
const LANDING_Y_SNAP: float = 14.0
const MIN_LANDING_SUPPORT_WIDTH: float = 12.0
const MIN_STABLE_SUPPORT_WIDTH: float = 16.0
const AMBIGUOUS_SUPPORT_DIFF: float = 6.0
const MIN_DOMINANT_SUPPORT_WIDTH: float = 24.0
const LANDING_X_CLAMP_PADDING: float = 1.0
const PERFECT_RATIO_THRESHOLD: float = 0.09
const PERFECT_BASE_SCORE: int = 2
const NORMAL_BASE_SCORE: int = 1
const PERFECT_COMBO_MULTIPLIER: int = 2
const SPECIAL_BASE_CHANCE: float = 0.1
const SPECIAL_MAX_CHANCE: float = 0.52
const DIFFICULTY_SCORE_TARGET: float = 120.0
const FEEDBACK_SHOW_TIME: float = 0.9
const SFX_SAMPLE_RATE: float = 44100.0
const SFX_BUFFER_LENGTH: float = 0.2
const SETTINGS_FILE_PATH: String = "user://settings.json"
const RECORDS_FILE_PATH: String = "user://records.json"
const MAX_RECORDS: int = 10
const REALTIME_WS_URL: String = "ws://127.0.0.1:8765"
const REALTIME_SEND_INTERVAL: float = 0.05
const REALTIME_RECONNECT_INTERVAL: float = 1.0
const PERFECT_DISPLAY_EXTEND: float = 2.0
const PERFECT_IDLE_HIDE_DELAY: float = 1.0
const COMBO_INTERVAL_LIMIT: float = 1.0
const COMBO_DISPLAY_TIME: float = 1.0
const RACE_DURATION_DEFAULT: int = 60
const RACE_DURATION_OPTIONS: Array[int] = [30, 60, 90]
const MI_OFFLINE_WS_URL: String = "ws://127.0.0.1:8766"
const MI_ONLINE_WS_URL: String = "ws://127.0.0.1:8767"
const MI_RECONNECT_INTERVAL: float = 0.75
const MI_PACKET_TTL_MS: int = 1500
const MI_HAND_CONF_THRESHOLD: float = 0.50
const MI_FOOT_CONF_THRESHOLD: float = 0.50
const MI_HAND_CONFIRM_COUNT: int = 1
const MI_FOOT_CONFIRM_COUNT: int = 1
const MI_KEEPALIVE_TIMEOUT: float = 0.7
const MI_ACTION_COOLDOWN: float = 0.12
const MI_AIR_JUMP_COOLDOWN: float = 0.2
const MI_STATUS_SEND_INTERVAL: float = 0.1
const MANUAL_MAX_CHARGE_TIME: float = 1.2
const MI_MAX_CHARGE_TIME: float = 2.5
const MI_HAND_ACTIVATION_DELAY: float = 0.5

enum GameState {
	START,
	PLAYING,
	GAME_OVER
}

enum GameMode {
	CLASSIC,
	RACE,
	VERTICAL_TRAIN,
	VERTICAL_TRAIN_OFFLINE
}

enum ControlMode {
	MANUAL,
	MI
}

enum MIInputMode {
	OFFLINE,
	ONLINE
}

enum InputAction {
	NONE,
	START_CHARGE,
	CANCEL_CHARGE,
	RELEASE_JUMP,
	AIR_JUMP
}

enum MIState {
	IDLE,
	CHARGING,
	REST_KEEPALIVE,
	AIRBORNE
}

@onready var player: Player = $Player
@onready var platforms_root: Node2D = $Platforms
@onready var camera_2d: Camera2D = $Camera2D
@onready var score_label: Label = $HUD/ScoreLabel
@onready var state_label: Label = $HUD/StateLabel
@onready var start_label: Label = $HUD/StartLabel
@onready var brightness_label: Label = $HUD/BrightnessLabel
@onready var volume_label: Label = $HUD/VolumeLabel
@onready var network_label: Label = $HUD/NetworkLabel
@onready var language_label: Label = $HUD/LanguageLabel
@onready var language_option: OptionButton = $HUD/LanguageOption
@onready var mode_label: Label = $HUD/ModeLabel
@onready var mode_option: OptionButton = $HUD/ModeOption
@onready var duration_label: Label = $HUD/DurationLabel
@onready var duration_option: OptionButton = $HUD/DurationOption
@onready var control_label: Label = $HUD/ControlLabel
@onready var control_option: OptionButton = $HUD/ControlOption
@onready var mi_input_label: Label = $HUD/MIInputLabel
@onready var mi_input_option: OptionButton = $HUD/MIInputOption
@onready var player_name_edit: LineEdit = $HUD/PlayerNameEdit
@onready var records_title: Label = $HUD/RecordsTitle
@onready var records_label: Label = $HUD/RecordsLabel
@onready var perfect_count_label: Label = $HUD/PerfectCountLabel
@onready var combo_label: Label = $HUD/ComboLabel
@onready var race_info_label: Label = $HUD/RaceInfoLabel
@onready var platform_minimap: Control = $HUD/PlatformMinimap

var rng: RandomNumberGenerator = RandomNumberGenerator.new()
const OfflineTrainManagerScript = preload("res://scripts/managers/offline_train_manager.gd")
const LevelModeScript = preload("res://scripts/managers/level_mode_manager.gd")
var offline_train = null
var level_mode = null
var subject_id: String = ""
var subject_ui: Control = null
var _session_name_input: LineEdit = null
var _save_path: String = "user://training_data"
var _save_path_label: Label = null
var _save_dir_dialog: FileDialog = null
var score: int = 0
var game_state: GameState = GameState.START
var wait_for_accept_release: bool = true
var next_platform_x: float = START_X
var brightness: float = 0.7
var sfx_volume: float = 0.65
var full_charge_cue_played: bool = false
var perfect_combo_streak: int = 0
var feedback_text: String = ""
var feedback_timer: float = 0.0
var standing_platform: Platform = null
var standing_platform_last_x: float = 0.0
var recent_records: Array = []
var perfect_count_in_run: int = 0
var perfect_display_timer: float = 0.0
var perfect_idle_timer: float = 0.0
var combo_count: int = 0
var combo_display_timer: float = 0.0
var last_jump_time_sec: float = -1.0
var realtime_ws: WebSocketPeer = WebSocketPeer.new()
var realtime_send_cooldown: float = 0.0
var realtime_reconnect_cooldown: float = 0.0
var realtime_difficulty_scale: float = -1.0
var current_language: String = "zh"
var current_mode: GameMode = GameMode.CLASSIC
var current_control_mode: ControlMode = ControlMode.MANUAL
var current_mi_input_mode: MIInputMode = MIInputMode.OFFLINE
var race_time_left: float = 0.0

var race_start_x: float = START_X
var race_distance: int = 0
var race_duration_seconds: int = RACE_DURATION_DEFAULT

var input_action_pending: InputAction = InputAction.NONE
var mi_state: MIState = MIState.IDLE
var mi_keepalive_timer: float = 0.0
var mi_air_jump_used: bool = false
var mi_last_action_time: float = -10.0
var mi_last_air_jump_time: float = -10.0
var mi_hand_activation_timer: float = 0.0

var mi_ws: WebSocketPeer = WebSocketPeer.new()
var mi_reconnect_cooldown: float = 0.0
var mi_last_seq: int = -1
var mi_raw_label: String = "none"
var mi_raw_streak: int = 0
var mi_decision_label: String = "none"
var mi_last_confidence: float = 0.0
var mi_display_label: String = "..."
var mi_fatigue: float = 50.0

var mi_messages_received: int = 0
var mi_out_of_order_dropped: int = 0
var mi_stale_dropped: int = 0
var mi_invalid_action_count: int = 0
var mi_cancel_count: int = 0
var mi_air_jump_count: int = 0
var mi_action_count: int = 0
var mi_latency_ms_ema: float = 0.0
var mi_status_send_cooldown: float = 0.0

var i18n: Dictionary = {
	"zh": {
		"score": "得分",
		"brightness": "亮度",
		"volume": "音量",
		"network": "网络",
		"net_online": "强实时在线",
		"net_connecting": "连接中...",
		"net_offline": "离线",
		"mode": "模式",
		"mode_classic": "经典",
		"mode_race": "竞速赛",
		"mode_vertical_train": "关卡模式",
		"mode_vertical_train_offline": "关卡训练",
		"control": "控制",
		"control_manual": "手操",
		"control_mi": "MI",
		"mi_input": "MI输入",
		"mi_input_offline": "离线",
		"mi_input_online": "在线",
		"state_mi_idle": "MI待机",
		"state_mi_charging": "MI蓄力中",
		"state_mi_keepalive": "MI保活中",
		"state_mi_airborne": "MI空中",
		"mi_metrics": "MI 收:%d 丢序:%d 过期:%d 取消:%d 二跳:%d 延迟:%.0fms",
		"race_time": "竞速时长",
		"language": "语言",
		"lang_zh": "中文",
		"lang_en": "English",
		"player_name_placeholder": "玩家名",
		"records_title": "最近10次记录",
		"records_empty": "暂无记录",
		"start_title": "跳一跳\n按空格开始",
		"state_start": "按空格开始",
		"state_game_over": "游戏结束 - 按空格重开",
		"state_race_over": "竞速结束 - 按空格重开",
		"state_flying": "飞行中",
		"state_charging": "蓄力 %.0f%%",
		"state_idle": "按住空格蓄力，松开起跳",
		"distance": "距离",
		"race_info": "倒计时 %.1fs | 距离 %d",
		"perfect_count": "完美次数: %d",
		"combo": "连击 x%d",
		"feedback_perfect": "完美 +%d",
		"feedback_perfect_combo": "完美连击 x2 +%d",
		"feedback_land": "落地 +%d",
		"feedback_risk": "（风险 +%d）",
		"record_line": "%02d. %s | %s | %s",
		"default_player": "玩家"
	},
	"en": {
		"score": "Score",
		"brightness": "Brightness",
		"volume": "Volume",
		"network": "Net",
		"net_online": "Realtime Online",
		"net_connecting": "Connecting...",
		"net_offline": "Offline",
		"mode": "Mode",
		"mode_classic": "Classic",
		"mode_race": "Race",
		"mode_vertical_train": "Level Mode",
		"mode_vertical_train_offline": "Level Training",
		"control": "Control",
		"control_manual": "Manual",
		"control_mi": "MI",
		"mi_input": "MI Input",
		"mi_input_offline": "Offline",
		"mi_input_online": "Online",
		"state_mi_idle": "MI Idle",
		"state_mi_charging": "MI Charging",
		"state_mi_keepalive": "MI Keepalive",
		"state_mi_airborne": "MI Airborne",
		"mi_metrics": "MI rx:%d oo:%d stale:%d cancel:%d air:%d lag:%.0fms",
		"race_time": "Race Time",
		"language": "Language",
		"lang_zh": "Chinese",
		"lang_en": "English",
		"player_name_placeholder": "Player name",
		"records_title": "Recent 10 Records",
		"records_empty": "No records yet.",
		"start_title": "JUMP JUMP\nPress Space to Start",
		"state_start": "Press Space to Start",
		"state_game_over": "Game Over - Press Space to Restart",
		"state_race_over": "Race Over - Press Space to Restart",
		"state_flying": "Flying",
		"state_charging": "Charging %.0f%%",
		"state_idle": "Hold Space to Charge, Release to Jump",
		"distance": "Distance",
		"race_info": "Time %.1fs | Dist %d",
		"perfect_count": "Perfect Count: %d",
		"combo": "Combo x%d",
		"feedback_perfect": "Perfect +%d",
		"feedback_perfect_combo": "Perfect Combo x2 +%d",
		"feedback_land": "Land +%d",
		"feedback_risk": "(Risk +%d)",
		"record_line": "%02d. %s | %s | %s",
		"default_player": "Player"
	}
}

var sfx_land_player: AudioStreamPlayer
var sfx_perfect_player: AudioStreamPlayer
var sfx_fail_player: AudioStreamPlayer
var sfx_charge_player: AudioStreamPlayer

const BRIGHTNESS_MIN: float = 0.55
const BRIGHTNESS_MAX: float = 1.25
const BRIGHTNESS_STEP: float = 0.05
const SFX_VOLUME_MIN: float = 0.0
const SFX_VOLUME_MAX: float = 1.0
const SFX_VOLUME_STEP: float = 0.05

func _ready() -> void:
	rng.randomize()
	_setup_sfx_players()
	_load_settings()
	_setup_language_option()
	_setup_control_option()
	_setup_mode_option()
	_setup_duration_option()
	_setup_mi_input_option()
	_load_records()
	_apply_charge_profile()
	_apply_sfx_volume()
	_setup_run()
	game_state = GameState.START
	_apply_brightness()
	offline_train = OfflineTrainManagerScript.new()
	offline_train.init(self)
	level_mode = LevelModeScript.new()
	level_mode.init(self)
	_create_subject_ui()
	_create_fatigue_ui()
	_refresh_ui()

func _setup_language_option() -> void:
	language_option.clear()
	language_option.add_item(_t("lang_zh"))
	language_option.set_item_metadata(0, "zh")
	language_option.add_item(_t("lang_en"))
	language_option.set_item_metadata(1, "en")
	var selected_idx: int = 0 if current_language == "zh" else 1
	language_option.select(selected_idx)
	_apply_option_popup_theme(language_option)
	if not language_option.item_selected.is_connected(_on_language_selected):
		language_option.item_selected.connect(_on_language_selected)

func _on_language_selected(index: int) -> void:
	var lang: Variant = language_option.get_item_metadata(index)
	if lang is String and (lang == "zh" or lang == "en"):
		current_language = lang
		_setup_language_option()
		_setup_control_option()
		_setup_mode_option()
		_setup_duration_option()
		_setup_mi_input_option()
		_save_settings()
		_update_records_display()
		_refresh_ui()

func _setup_control_option() -> void:
	control_option.clear()
	control_option.add_item(_t("control_manual"))
	control_option.set_item_metadata(0, ControlMode.MANUAL)
	control_option.add_item(_t("control_mi"))
	control_option.set_item_metadata(1, ControlMode.MI)
	control_option.select(0 if current_control_mode == ControlMode.MANUAL else 1)
	_apply_option_popup_theme(control_option)
	if not control_option.item_selected.is_connected(_on_control_selected):
		control_option.item_selected.connect(_on_control_selected)

func _on_control_selected(index: int) -> void:
	var selected: Variant = control_option.get_item_metadata(index)
	if selected is int:
		current_control_mode = selected
		_apply_charge_profile()
		_reset_mi_runtime_state()
		_save_settings()
		_refresh_ui()

func _setup_mode_option() -> void:
	mode_option.clear()
	mode_option.add_item(_t("mode_classic"))
	mode_option.set_item_metadata(0, GameMode.CLASSIC)
	mode_option.add_item(_t("mode_race"))
	mode_option.set_item_metadata(1, GameMode.RACE)
	mode_option.add_item(_t("mode_vertical_train"))
	mode_option.set_item_metadata(2, GameMode.VERTICAL_TRAIN)
	mode_option.add_item(_t("mode_vertical_train_offline"))
	mode_option.set_item_metadata(3, GameMode.VERTICAL_TRAIN_OFFLINE)
	var selected_idx: int = 0
	if current_mode == GameMode.CLASSIC:
		selected_idx = 0
	elif current_mode == GameMode.RACE:
		selected_idx = 1
	elif current_mode == GameMode.VERTICAL_TRAIN:
		selected_idx = 2
	elif current_mode == GameMode.VERTICAL_TRAIN_OFFLINE:
		selected_idx = 3
	mode_option.select(selected_idx)
	_apply_option_popup_theme(mode_option)
	if not mode_option.item_selected.is_connected(_on_mode_selected):
		mode_option.item_selected.connect(_on_mode_selected)

func _setup_duration_option() -> void:
	duration_option.clear()
	for value: int in RACE_DURATION_OPTIONS:
		duration_option.add_item("%d s" % value)
		duration_option.set_item_metadata(duration_option.item_count - 1, value)
	var selected_idx: int = 0
	for i: int in range(RACE_DURATION_OPTIONS.size()):
		if RACE_DURATION_OPTIONS[i] == race_duration_seconds:
			selected_idx = i
			break
	duration_option.select(selected_idx)
	_apply_option_popup_theme(duration_option)
	if not duration_option.item_selected.is_connected(_on_duration_selected):
		duration_option.item_selected.connect(_on_duration_selected)

func _setup_mi_input_option() -> void:
	mi_input_option.clear()
	mi_input_option.add_item(_t("mi_input_offline"))
	mi_input_option.set_item_metadata(0, MIInputMode.OFFLINE)
	mi_input_option.add_item(_t("mi_input_online"))
	mi_input_option.set_item_metadata(1, MIInputMode.ONLINE)
	mi_input_option.select(0 if current_mi_input_mode == MIInputMode.OFFLINE else 1)
	_apply_option_popup_theme(mi_input_option)
	if not mi_input_option.item_selected.is_connected(_on_mi_input_selected):
		mi_input_option.item_selected.connect(_on_mi_input_selected)

func _on_mi_input_selected(index: int) -> void:
	var selected: Variant = mi_input_option.get_item_metadata(index)
	if selected is int:
		current_mi_input_mode = selected
		_reset_mi_runtime_state()
		_save_settings()
		_refresh_ui()

func _apply_charge_profile() -> void:
	if player == null:
		return
	player.max_charge_time = MI_MAX_CHARGE_TIME if current_control_mode == ControlMode.MI else MANUAL_MAX_CHARGE_TIME

func _apply_option_popup_theme(option: OptionButton) -> void:
	if option == null:
		return
	var popup: PopupMenu = option.get_popup()
	if popup == null:
		return
	var panel_style: StyleBoxFlat = StyleBoxFlat.new()
	panel_style.bg_color = Color(0.934, 0.912, 0.835, 1)
	panel_style.border_width_left = 1
	panel_style.border_width_top = 1
	panel_style.border_width_right = 1
	panel_style.border_width_bottom = 1
	panel_style.border_color = Color(0.364706, 0.52549, 0.392157, 0.75)
	var hover_style: StyleBoxFlat = panel_style.duplicate()
	hover_style.bg_color = panel_style.bg_color
	popup.add_theme_stylebox_override("panel", panel_style)
	popup.add_theme_stylebox_override("hover", hover_style)
	popup.add_theme_color_override("font_color", Color(0.247059, 0.407843, 0.286275, 1))
	popup.add_theme_color_override("font_hover_color", Color(0.247059, 0.407843, 0.286275, 1))
	popup.add_theme_color_override("font_pressed_color", Color(0.247059, 0.407843, 0.286275, 1))
	popup.add_theme_color_override("font_accelerator_color", Color(0.247059, 0.407843, 0.286275, 0.82))
	popup.add_theme_color_override("font_disabled_color", Color(0.247059, 0.407843, 0.286275, 0.55))

func _on_mode_selected(index: int) -> void:
	var mode_value: Variant = mode_option.get_item_metadata(index)
	if mode_value is int:
		current_mode = mode_value
		_save_settings()
		if current_mode == GameMode.VERTICAL_TRAIN and game_state == GameState.START:
			level_mode.show_level_select()
		else:
			level_mode.hide_level_select()
		_refresh_ui()

func _on_duration_selected(index: int) -> void:
	var duration_value: Variant = duration_option.get_item_metadata(index)
	if duration_value is int:
		race_duration_seconds = duration_value
		_save_settings()
		_refresh_ui()

func _t(key: String) -> String:
	var pack: Dictionary = i18n.get(current_language, i18n["en"])
	return str(pack.get(key, key))

func _input(event: InputEvent) -> void:
	if not (event is InputEventKey) or event.echo:
		return
	var ke: InputEventKey = event as InputEventKey

	# ESC: always return to main menu
	if ke.keycode == KEY_ESCAPE and ke.pressed:
		if game_state == GameState.PLAYING or game_state == GameState.GAME_OVER:
			game_state = GameState.START
			wait_for_accept_release = true
		return

	# Space: start / restart
	if ke.keycode == KEY_SPACE and ke.pressed:
		if game_state == GameState.START:
			_save_settings()
			_setup_run()
			if current_mode != GameMode.VERTICAL_TRAIN:
				game_state = GameState.PLAYING
			wait_for_accept_release = true
		elif game_state == GameState.GAME_OVER:
			_setup_run()
			if current_mode != GameMode.VERTICAL_TRAIN:
				game_state = GameState.PLAYING
			wait_for_accept_release = true

	# A/D: jump direction in level mode (manual only)
	if current_mode == GameMode.VERTICAL_TRAIN and current_control_mode == ControlMode.MANUAL and game_state == GameState.PLAYING and ke.pressed:
		if ke.keycode == KEY_A or ke.keycode == KEY_LEFT:
			level_mode.try_jump(-1)
		elif ke.keycode == KEY_D or ke.keycode == KEY_RIGHT:
			level_mode.try_jump(1)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_TAB:
			if current_mode == GameMode.VERTICAL_TRAIN and game_state == GameState.START:
				if level_mode.select_ui != null and level_mode.select_ui.visible:
					level_mode.hide_level_select()
				else:
					level_mode.show_level_select()
		elif event.keycode == KEY_ESCAPE:
			if game_state == GameState.PLAYING or game_state == GameState.GAME_OVER:
				game_state = GameState.START
				wait_for_accept_release = true
		elif event.keycode == KEY_MINUS or event.keycode == KEY_KP_SUBTRACT:
			_adjust_brightness(-BRIGHTNESS_STEP)
		elif event.keycode == KEY_EQUAL or event.keycode == KEY_PLUS or event.keycode == KEY_KP_ADD:
			_adjust_brightness(BRIGHTNESS_STEP)
		elif event.keycode == KEY_BRACKETLEFT:
			_adjust_sfx_volume(-SFX_VOLUME_STEP)
		elif event.keycode == KEY_BRACKETRIGHT:
			_adjust_sfx_volume(SFX_VOLUME_STEP)

func _queue_input_action(action: InputAction) -> void:
	if action == InputAction.NONE:
		return
	if action > input_action_pending:
		input_action_pending = action

func _poll_manual_action() -> void:
	if player.is_airborne:
		return
	if Input.is_action_pressed("ui_accept"):
		_queue_input_action(InputAction.START_CHARGE)
	if Input.is_action_just_released("ui_accept"):
		_queue_input_action(InputAction.RELEASE_JUMP)

func _poll_mi_action(delta: float) -> void:
	# Level mode: MI left/right triggers jump directly
	if current_mode == GameMode.VERTICAL_TRAIN:
		if mi_decision_label == "left":
			level_mode.try_jump(-1)
		elif mi_decision_label == "right":
			level_mode.try_jump(1)
		_mi_reset_decision_tracking()
		return

	if player.is_airborne:
		mi_state = MIState.AIRBORNE
	else:
		if mi_state == MIState.AIRBORNE:
			mi_state = MIState.IDLE
			mi_air_jump_used = false

	if mi_state == MIState.CHARGING:
		if mi_decision_label == "foot" and not player.is_airborne:
			_queue_input_action(InputAction.RELEASE_JUMP)
			_mi_reset_decision_tracking()
		elif mi_decision_label == "rest":
			mi_state = MIState.REST_KEEPALIVE
			mi_keepalive_timer = 0.0
			player.pause_charge()
			_mi_reset_decision_tracking()
	elif mi_state == MIState.REST_KEEPALIVE:
		mi_keepalive_timer += delta
		if mi_decision_label == "hand":
			mi_state = MIState.CHARGING
			player.resume_charge()
			_mi_reset_decision_tracking()
		elif mi_keepalive_timer >= MI_KEEPALIVE_TIMEOUT:
			_queue_input_action(InputAction.CANCEL_CHARGE)
			mi_keepalive_timer = 0.0
			_mi_reset_decision_tracking()
	elif mi_state == MIState.IDLE:
		if mi_decision_label == "hand" and not player.is_airborne:
			mi_hand_activation_timer += delta
			if mi_hand_activation_timer >= MI_HAND_ACTIVATION_DELAY:
				_queue_input_action(InputAction.START_CHARGE)
				mi_state = MIState.CHARGING
				mi_hand_activation_timer = 0.0
				_mi_reset_decision_tracking()
		else:
			mi_hand_activation_timer = 0.0
	elif mi_state == MIState.AIRBORNE:
		var now_sec: float = Time.get_ticks_msec() / 1000.0
		if mi_decision_label == "foot":
			if not mi_air_jump_used and now_sec - mi_last_air_jump_time >= MI_AIR_JUMP_COOLDOWN:
				_queue_input_action(InputAction.AIR_JUMP)
				mi_air_jump_used = true
				mi_last_air_jump_time = now_sec
			else:
				mi_invalid_action_count += 1
			_mi_reset_decision_tracking()

func _consume_input_action() -> void:
	var action: InputAction = input_action_pending
	if action == InputAction.NONE:
		return
	input_action_pending = InputAction.NONE

	var now_sec: float = Time.get_ticks_msec() / 1000.0
	if current_control_mode == ControlMode.MI and action != InputAction.AIR_JUMP and now_sec - mi_last_action_time < MI_ACTION_COOLDOWN:
		return

	if action == InputAction.START_CHARGE:
		player.begin_charge()
		if current_control_mode == ControlMode.MI:
			player.always_show_charge_bar = false
			mi_state = MIState.CHARGING
	elif action == InputAction.CANCEL_CHARGE:
		player.cancel_charge()
		mi_cancel_count += 1
		if current_control_mode == ControlMode.MI:
			mi_state = MIState.IDLE
	elif action == InputAction.RELEASE_JUMP:
		if player.release_jump():
			if current_control_mode == ControlMode.MI:
				mi_state = MIState.AIRBORNE
				mi_air_jump_used = false
			else:
				_register_jump_combo()
		else:
			mi_invalid_action_count += 1
	elif action == InputAction.AIR_JUMP:
		if current_control_mode == ControlMode.MI and player.air_jump():
			mi_air_jump_count += 1
		else:
			mi_invalid_action_count += 1

	if current_control_mode == ControlMode.MI:
		mi_action_count += 1
		mi_last_action_time = now_sec

func _physics_process(delta: float) -> void:
	if wait_for_accept_release:
		if not Input.is_action_pressed("ui_accept"):
			wait_for_accept_release = false
		_refresh_ui()
		return

	if game_state == GameState.START:
		if Input.is_action_just_pressed("ui_accept"):
			_save_settings()
			_setup_run()
			game_state = GameState.PLAYING
			wait_for_accept_release = true
		_refresh_ui()
		return

	if game_state == GameState.GAME_OVER:
		if Input.is_action_just_pressed("ui_accept"):
			_setup_run()
			game_state = GameState.PLAYING
			wait_for_accept_release = true
			full_charge_cue_played = false
		_refresh_ui()
		return

	if current_mode == GameMode.VERTICAL_TRAIN:
		level_mode.update(delta)
	elif current_mode == GameMode.VERTICAL_TRAIN_OFFLINE:
		offline_train.update(delta)
	elif current_mode == GameMode.RACE:
		race_time_left = max(0.0, race_time_left - delta)
		race_distance = max(race_distance, int(max(0.0, player.global_position.x - race_start_x)))
		score = race_distance
		if race_time_left <= 0.0:
			game_state = GameState.GAME_OVER
			wait_for_accept_release = true
			perfect_combo_streak = 0
			standing_platform = null
			standing_platform_last_x = 0.0
			_save_record(score)
			_save_settings()
			_update_records_display()
			_refresh_ui()
			return

	if current_mode == GameMode.CLASSIC and feedback_timer > 0.0:
		feedback_timer = max(0.0, feedback_timer - delta)
		if feedback_timer <= 0.0:
			feedback_text = ""

	# _update_realtime_bridge(delta)  # disabled
	if current_control_mode == ControlMode.MI or current_mode == GameMode.VERTICAL_TRAIN_OFFLINE or current_mode == GameMode.VERTICAL_TRAIN:
		_update_mi_bridge(delta)

	if current_mode == GameMode.CLASSIC and perfect_display_timer > 0.0:
		perfect_display_timer = max(0.0, perfect_display_timer - delta)
		perfect_idle_timer += delta
		if perfect_display_timer <= 0.0 or perfect_idle_timer >= PERFECT_IDLE_HIDE_DELAY:
			perfect_display_timer = 0.0
			perfect_count_label.visible = false

	if current_mode == GameMode.CLASSIC and combo_display_timer > 0.0:
		combo_display_timer = max(0.0, combo_display_timer - delta)
		if combo_display_timer <= 0.0:
			combo_label.visible = false
			combo_count = 0

	if not player.is_airborne and current_mode != GameMode.VERTICAL_TRAIN and current_mode != GameMode.VERTICAL_TRAIN_OFFLINE:
		_ensure_ground_support()

	if current_mode != GameMode.VERTICAL_TRAIN_OFFLINE:
		if current_mode == GameMode.VERTICAL_TRAIN:
			if current_control_mode == ControlMode.MI:
				_poll_mi_action(delta)
		elif current_control_mode == ControlMode.MANUAL:
			if not player.is_airborne:
				if Input.is_action_pressed("ui_accept"):
					player.begin_charge()
				if Input.is_action_just_released("ui_accept"):
					if player.release_jump():
						_register_jump_combo()
		else:
			_poll_mi_action(delta)
			_consume_input_action()

	if player.is_charging and not full_charge_cue_played and player.charge_ratio() >= 0.995:
		_play_charge_ready_sfx()
		full_charge_cue_played = true
	elif not player.is_charging:
		full_charge_cue_played = false

	var previous_feet_y: float = player.feet_y()
	player.update_motion(delta)

	if player.is_airborne and player.feet_y() >= previous_feet_y - 1.0:
		_try_land_on_platform(previous_feet_y, player.feet_y())

	if current_mode != GameMode.VERTICAL_TRAIN and current_mode != GameMode.VERTICAL_TRAIN_OFFLINE:
		_follow_camera(delta)
		_maintain_platforms()
	_check_game_over()
	_refresh_ui()

func _setup_run() -> void:
	for child: Node in platforms_root.get_children():
		child.free()

	score = 0
	next_platform_x = START_X
	full_charge_cue_played = false
	perfect_combo_streak = 0
	feedback_text = ""
	feedback_timer = 0.0
	standing_platform = null
	standing_platform_last_x = 0.0
	perfect_count_in_run = 0
	perfect_display_timer = 0.0
	perfect_idle_timer = 0.0
	combo_count = 0
	combo_display_timer = 0.0
	last_jump_time_sec = -1.0
	perfect_count_label.visible = false
	combo_label.visible = false
	race_info_label.visible = false
	race_time_left = float(race_duration_seconds)
	race_distance = 0
	_reset_mi_runtime_state()

	if current_mode == GameMode.VERTICAL_TRAIN:
		level_mode.show_level_select()
		return
	elif current_mode == GameMode.VERTICAL_TRAIN_OFFLINE:
		offline_train.setup_level()
	else:
		var first_platform: Platform = _create_platform(START_X, START_Y, START_WIDTH, Platform.PlatformKind.NORMAL, 0.0)
		player.reset_to_platform(first_platform)
		player.always_show_charge_bar = current_control_mode == ControlMode.MANUAL
		standing_platform = first_platform
		standing_platform_last_x = first_platform.global_position.x
		race_start_x = player.global_position.x

		camera_2d.global_position = Vector2(player.global_position.x + CAMERA_LEAD_X, CAMERA_FIXED_Y)

		for _i: int in range(START_PLATFORM_COUNT):
			_spawn_next_platform(false)

	_refresh_ui()

func _create_platform(x: float, y: float, width: float, kind: Platform.PlatformKind, difficulty: float) -> Platform:
	var platform: Platform = PLATFORM_SCENE.instantiate()
	platform.global_position = Vector2(x, y)
	platforms_root.add_child(platform)
	platform.setup(kind, width, difficulty, rng, PLATFORM_MOTION_SCALE)
	return platform

func _spawn_next_platform(allow_special: bool = true) -> void:
	var difficulty: float = _difficulty_ratio()
	var min_distance: float = lerp(BASE_SPAWN_DISTANCE_MIN, HARD_SPAWN_DISTANCE_MIN, difficulty)
	var max_distance: float = lerp(BASE_SPAWN_DISTANCE_MAX, HARD_SPAWN_DISTANCE_MAX, difficulty)
	next_platform_x += rng.randf_range(min_distance, max_distance)
	var y: float = START_Y
	var min_width: float = lerp(BASE_PLATFORM_WIDTH_MIN, HARD_PLATFORM_WIDTH_MIN, difficulty)
	var max_width: float = lerp(BASE_PLATFORM_WIDTH_MAX, HARD_PLATFORM_WIDTH_MAX, difficulty)
	var kind: Platform.PlatformKind = _roll_platform_kind(difficulty, allow_special)
	var width: float = rng.randf_range(min_width, max_width)

	if kind == Platform.PlatformKind.FRAGILE:
		width *= 0.86

	width = clamp(width, 64.0, 260.0)
	_create_platform(next_platform_x, y, width, kind, difficulty)

func _maintain_platforms() -> void:
	var target_x: float = player.global_position.x + PLATFORM_BUFFER_AHEAD
	while next_platform_x < target_x:
		_spawn_next_platform()

	var viewport_half_width: float = get_viewport_rect().size.x * 0.5
	var visible_left_x: float = camera_2d.global_position.x - viewport_half_width

	for child: Node in platforms_root.get_children():
		var platform: Platform = child as Platform
		if platform != null and platform.right_edge() < visible_left_x - PLATFORM_CLEANUP_BEHIND:
			platform.queue_free()

func _try_land_on_platform(previous_feet_y: float, current_feet_y: float) -> void:
	if current_mode == GameMode.VERTICAL_TRAIN:
		level_mode.try_land(previous_feet_y, current_feet_y)
		return
	if current_mode == GameMode.VERTICAL_TRAIN_OFFLINE:
		offline_train.try_land(previous_feet_y, current_feet_y)
		return

	var best_platform: Platform = null
	var best_overlap: float = -1.0
	var second_overlap: float = -1.0
	var best_top_y: float = 0.0
	var best_vertical_delta: float = INF

	for child: Node in platforms_root.get_children():
		var platform: Platform = child as Platform
		if platform == null:
			continue
		if not platform.can_support_landing():
			continue
		var top_y: float = platform.top_y()
		var within_vertical: bool = previous_feet_y <= top_y + LANDING_Y_SNAP and current_feet_y >= top_y - LANDING_Y_SNAP
		if not within_vertical:
			continue

		var overlap_width: float = platform.support_overlap_width(player.global_position.x, Player.HALF_SIZE, LANDING_X_MARGIN)
		if overlap_width < MIN_LANDING_SUPPORT_WIDTH:
			continue

		var vertical_delta: float = abs(current_feet_y - top_y)
		if overlap_width > best_overlap or (is_equal_approx(overlap_width, best_overlap) and vertical_delta < best_vertical_delta):
			second_overlap = best_overlap
			best_overlap = overlap_width
			best_platform = platform
			best_top_y = top_y
			best_vertical_delta = vertical_delta
		elif overlap_width > second_overlap:
			second_overlap = overlap_width

	if best_platform == null:
		return

	# Crossing two neighboring platforms can create ambiguous support. Ignore landing unless one platform clearly dominates.
	if second_overlap >= 0.0 and abs(best_overlap - second_overlap) <= AMBIGUOUS_SUPPORT_DIFF and best_overlap < MIN_DOMINANT_SUPPORT_WIDTH:
		return

	if best_overlap < MIN_STABLE_SUPPORT_WIDTH:
		return

	var landing_offset: float = abs(player.global_position.x - best_platform.global_position.x)
	var perfect_threshold: float = max(10.0, best_platform.width * PERFECT_RATIO_THRESHOLD)
	var is_perfect: bool = landing_offset <= perfect_threshold
	var should_score: bool = player.can_score_landing()
	player.land_on(best_top_y)
	var clamp_min_x: float = best_platform.left_edge() + Player.HALF_SIZE + LANDING_X_CLAMP_PADDING
	var clamp_max_x: float = best_platform.right_edge() - Player.HALF_SIZE - LANDING_X_CLAMP_PADDING
	if clamp_min_x <= clamp_max_x:
		player.global_position.x = clamp(player.global_position.x, clamp_min_x, clamp_max_x)
	standing_platform = best_platform
	standing_platform_last_x = best_platform.global_position.x

	if not should_score:
		perfect_combo_streak = 0
		return

	if current_mode == GameMode.RACE:
		best_platform.on_landed()
		return

	var landing_score: int = NORMAL_BASE_SCORE
	if is_perfect:
		_register_perfect_count()
		perfect_combo_streak += 1
		landing_score = PERFECT_BASE_SCORE
		if perfect_combo_streak >= 2:
			landing_score *= PERFECT_COMBO_MULTIPLIER
	else:
		perfect_combo_streak = 0

	var bonus: int = best_platform.risk_bonus()
	landing_score += bonus
	score += landing_score
	best_platform.on_landed()
	_show_landing_feedback(is_perfect, bonus, landing_score)
	if is_perfect:
		_play_perfect_land_sfx()
	else:
		_play_land_sfx()

func _ensure_ground_support() -> void:
	var best_platform: Platform = null
	var best_overlap: float = -1.0
	var second_overlap: float = -1.0

	for child: Node in platforms_root.get_children():
		var platform: Platform = child as Platform
		if platform == null:
			continue
		if not platform.can_support_landing():
			continue

		var close_to_surface: bool = abs(player.feet_y() - platform.top_y()) <= LANDING_Y_SNAP + 3.0
		if not close_to_surface:
			continue

		var overlap: float = platform.support_overlap_width(player.global_position.x, Player.HALF_SIZE, 0.0)
		if overlap > best_overlap:
			second_overlap = best_overlap
			best_overlap = overlap
			best_platform = platform
		elif overlap > second_overlap:
			second_overlap = overlap

	if best_platform == null or best_overlap < MIN_STABLE_SUPPORT_WIDTH:
		player.drop_from_platform()
		standing_platform = null
		standing_platform_last_x = 0.0
		return

	# If two platforms support almost equally and neither is dominant, treat it as unstable gap support.
	if second_overlap >= 0.0 and abs(best_overlap - second_overlap) <= AMBIGUOUS_SUPPORT_DIFF and best_overlap < MIN_DOMINANT_SUPPORT_WIDTH:
		player.drop_from_platform()
		standing_platform = null
		standing_platform_last_x = 0.0
		return

	if standing_platform != null and is_instance_valid(standing_platform) and standing_platform == best_platform:
		player.global_position.x += best_platform.global_position.x - standing_platform_last_x
	standing_platform_last_x = best_platform.global_position.x
	standing_platform = best_platform
	player.global_position.y = best_platform.top_y() - Player.HALF_SIZE

func _difficulty_ratio() -> float:
	var local_ratio: float = clamp(float(score) / DIFFICULTY_SCORE_TARGET, 0.0, 1.0)
	if realtime_difficulty_scale >= 0.0:
		return clamp((local_ratio * 0.55) + (realtime_difficulty_scale * 0.45), 0.0, 1.0)
	return local_ratio

func _update_realtime_bridge(delta: float) -> void:
	if realtime_ws == null:
		realtime_ws = WebSocketPeer.new()

	var state: WebSocketPeer.State = realtime_ws.get_ready_state()
	if state == WebSocketPeer.STATE_OPEN:
		realtime_ws.poll()
		while realtime_ws.get_available_packet_count() > 0:
			var packet: PackedByteArray = realtime_ws.get_packet()
			var parsed: Variant = JSON.parse_string(packet.get_string_from_utf8())
			if parsed is Dictionary:
				var payload: Dictionary = parsed
				var difficulty_value: Variant = payload.get("difficulty_scale", null)
				var airborne_bonus_value: Variant = payload.get("airborne_bonus", 0.0)
				if difficulty_value is float or difficulty_value is int:
					var difficulty_num: float = float(difficulty_value)
					var bonus_num: float = float(airborne_bonus_value) if (airborne_bonus_value is float or airborne_bonus_value is int) else 0.0
					realtime_difficulty_scale = clamp(difficulty_num + bonus_num, 0.0, 1.0)

		realtime_send_cooldown -= delta
		if realtime_send_cooldown <= 0.0:
			realtime_send_cooldown = REALTIME_SEND_INTERVAL
			var payload_out: Dictionary = {
				"score": score,
				"airborne": player.is_airborne,
				"charging": player.is_charging,
				"time": Time.get_ticks_msec()
			}
			realtime_ws.send_text(JSON.stringify(payload_out))
		return

	if state == WebSocketPeer.STATE_CONNECTING:
		realtime_ws.poll()
		return

	realtime_reconnect_cooldown -= delta
	if realtime_reconnect_cooldown > 0.0:
		return

	realtime_reconnect_cooldown = REALTIME_RECONNECT_INTERVAL
	realtime_difficulty_scale = -1.0
	if realtime_ws.get_ready_state() != WebSocketPeer.STATE_CLOSED:
		realtime_ws.close()
	realtime_ws = WebSocketPeer.new()
	realtime_ws.connect_to_url(REALTIME_WS_URL)

func send_mi_marker(event_type: String, data: Dictionary) -> void:
	if mi_ws == null or mi_ws.get_ready_state() != WebSocketPeer.STATE_OPEN:
		return
	var payload: Dictionary = data.duplicate()
	payload["type"] = event_type
	payload["timestamp_ms"] = int(Time.get_unix_time_from_system() * 1000.0)
	payload["subject_id"] = subject_id
	var msg: String = JSON.stringify(payload)
	mi_ws.send_text(msg)

func _update_mi_bridge(delta: float) -> void:
	var need_mi: bool = current_control_mode == ControlMode.MI or current_mode == GameMode.VERTICAL_TRAIN or current_mode == GameMode.VERTICAL_TRAIN_OFFLINE
	if not need_mi:
		if mi_ws != null and mi_ws.get_ready_state() == WebSocketPeer.STATE_OPEN:
			mi_ws.close()
		return

	if mi_ws == null:
		mi_ws = WebSocketPeer.new()

	var state: WebSocketPeer.State = mi_ws.get_ready_state()
	if state == WebSocketPeer.STATE_OPEN:
		mi_ws.poll()
		if mi_ws.get_ready_state() != WebSocketPeer.STATE_OPEN:
			return
		while mi_ws.get_available_packet_count() > 0:
			var packet: PackedByteArray = mi_ws.get_packet()
			_process_mi_packet(packet.get_string_from_utf8())
		mi_status_send_cooldown -= delta
		if mi_status_send_cooldown <= 0.0:
			mi_status_send_cooldown = MI_STATUS_SEND_INTERVAL
			var status_payload: Dictionary = {
				"type": "mi_status",
				"timestamp_ms": int(Time.get_unix_time_from_system() * 1000.0),
				"score": score,
				"airborne": player.is_airborne,
				"charging": player.is_charging,
				"mi_state": mi_state,
				"control_mode": current_control_mode,
				"mi_input_mode": current_mi_input_mode
			}
			if mi_ws.get_ready_state() == WebSocketPeer.STATE_OPEN:
				var send_result: int = mi_ws.send_text(JSON.stringify(status_payload))
				if send_result != OK:
					mi_reconnect_cooldown = 0.0
					if mi_ws.get_ready_state() != WebSocketPeer.STATE_CLOSED:
						mi_ws.close()
		return

	if state == WebSocketPeer.STATE_CONNECTING:
		mi_ws.poll()
		return

	mi_reconnect_cooldown -= delta
	if mi_reconnect_cooldown > 0.0:
		return

	mi_reconnect_cooldown = MI_RECONNECT_INTERVAL
	if mi_ws.get_ready_state() != WebSocketPeer.STATE_CLOSED:
		mi_ws.close()
	mi_ws = WebSocketPeer.new()
	mi_last_seq = -1
	var target_url: String = MI_OFFLINE_WS_URL if current_mi_input_mode == MIInputMode.OFFLINE else MI_ONLINE_WS_URL
	mi_ws.connect_to_url(target_url)

func _process_mi_packet(raw_text: String) -> void:
	var parsed: Variant = JSON.parse_string(raw_text)
	if not (parsed is Dictionary):
		return
	var data: Dictionary = parsed

	# 独立专注度更新包（每秒推送）
	if data.get("type", "") == "fatigue":
		mi_fatigue = clamp(float(data.get("fatigue", 50.0)), 0.0, 100.0)
		return

	var seq: int = int(data.get("seq", -1))
	if seq <= mi_last_seq:
		# Allow sender restart in offline tests where sequence often resets to 1.
		if seq == 1:
			mi_last_seq = 0
		else:
			mi_out_of_order_dropped += 1
			return
	mi_last_seq = seq

	var now_ms: int = int(Time.get_unix_time_from_system() * 1000.0)
	var ts_ms: int = int(data.get("timestamp_ms", now_ms))
	if abs(now_ms - ts_ms) > MI_PACKET_TTL_MS:
		mi_stale_dropped += 1
		return

	mi_messages_received += 1
	var lag_ms: float = float(max(0, now_ms - ts_ms))
	mi_latency_ms_ema = lag_ms if is_zero_approx(mi_latency_ms_ema) else lerp(mi_latency_ms_ema, lag_ms, 0.18)

	var label: String = str(data.get("label", "rest")).to_lower()
	if label != "hand" and label != "foot" and label != "left" and label != "right":
		label = "rest"
	var confidence: float = clamp(float(data.get("confidence", 0.0)), 0.0, 1.0)
	mi_fatigue = clamp(float(data.get("fatigue", 50.0)), 0.0, 100.0)
	_process_mi_signal(label, confidence)

func _process_mi_signal(label: String, confidence: float) -> void:
	mi_last_confidence = confidence
	var effective_label: String = "rest"
	# Level mode: map hand/foot to left/right
	if current_mode == GameMode.VERTICAL_TRAIN or current_mode == GameMode.VERTICAL_TRAIN_OFFLINE:
		if (label == "hand" or label == "left" or label == "left_hand") and confidence >= MI_HAND_CONF_THRESHOLD:
			effective_label = "left"
		elif (label == "foot" or label == "right" or label == "right_hand") and confidence >= MI_FOOT_CONF_THRESHOLD:
			effective_label = "right"
	elif label == "hand" and confidence >= MI_HAND_CONF_THRESHOLD:
		effective_label = "hand"
	elif label == "foot" and confidence >= MI_FOOT_CONF_THRESHOLD:
		effective_label = "foot"

	if effective_label == mi_raw_label:
		mi_raw_streak += 1
	else:
		mi_raw_label = effective_label
		mi_raw_streak = 1

	var needed: int = _mi_needed_count(effective_label)
	if effective_label == "rest":
		needed = 1
	if mi_raw_streak >= needed and mi_decision_label != effective_label:
		mi_decision_label = effective_label
		mi_display_label = effective_label + " " + str(int(confidence * 100)) + "%"

func _mi_needed_count(effective_label: String) -> int:
	if effective_label == "rest":
		return 1
	if current_mi_input_mode == MIInputMode.OFFLINE:
		return 1
	if effective_label == "hand":
		return MI_HAND_CONFIRM_COUNT
	if effective_label == "foot":
		return MI_FOOT_CONFIRM_COUNT
	return 1

func _mi_reset_decision_tracking() -> void:
	mi_decision_label = "none"
	mi_raw_streak = 0

func _reset_mi_runtime_state() -> void:
	mi_state = MIState.IDLE
	mi_keepalive_timer = 0.0
	mi_air_jump_used = false
	mi_last_action_time = -10.0
	mi_last_air_jump_time = -10.0
	mi_hand_activation_timer = 0.0
	mi_raw_label = "none"
	mi_raw_streak = 0
	mi_decision_label = "none"
	input_action_pending = InputAction.NONE
	mi_status_send_cooldown = 0.0
	player.cancel_charge()
	player.always_show_charge_bar = current_control_mode == ControlMode.MANUAL

func _roll_platform_kind(difficulty: float, allow_special: bool) -> Platform.PlatformKind:
	if not allow_special:
		return Platform.PlatformKind.NORMAL
	var special_chance: float = lerp(SPECIAL_BASE_CHANCE, SPECIAL_MAX_CHANCE, difficulty)
	if rng.randf() > special_chance:
		return Platform.PlatformKind.NORMAL

	var roll: float = rng.randf()
	var moving_weight: float = lerp(0.45, 0.32, difficulty)
	if roll < moving_weight:
		return Platform.PlatformKind.MOVING
	return Platform.PlatformKind.FRAGILE

func _show_landing_feedback(is_perfect: bool, bonus: int, landing_score: int) -> void:
	if is_perfect:
		if perfect_combo_streak >= 2:
			feedback_text = _t("feedback_perfect_combo") % landing_score
		else:
			feedback_text = _t("feedback_perfect") % landing_score
	else:
		feedback_text = _t("feedback_land") % landing_score
	if bonus > 0:
		feedback_text += " " + (_t("feedback_risk") % bonus)
	feedback_timer = FEEDBACK_SHOW_TIME

func _follow_camera(delta: float) -> void:
	var current_x: float = camera_2d.global_position.x
	var target_x: float = max(current_x, player.global_position.x + CAMERA_LEAD_X)
	var blend: float = 1.0 - exp(-CAMERA_FOLLOW_SMOOTHNESS * delta)
	var smoothed_target_x: float = lerp(current_x, target_x, blend)
	var max_step: float = CAMERA_MAX_SCROLL_SPEED * delta
	var step: float = min(smoothed_target_x - current_x, max_step)
	camera_2d.global_position.x = current_x + max(0.0, step)
	camera_2d.global_position.y = CAMERA_FIXED_Y

func _check_game_over() -> void:
	if game_state != GameState.PLAYING:
		return
	if current_mode == GameMode.VERTICAL_TRAIN or current_mode == GameMode.VERTICAL_TRAIN_OFFLINE:
		return  # Handled by manager
	var viewport_size: Vector2 = get_viewport_rect().size
	var bottom_limit: float = camera_2d.global_position.y + viewport_size.y * 0.5 + 80.0
	if player.global_position.y > bottom_limit:
		game_state = GameState.GAME_OVER
		wait_for_accept_release = true
		perfect_combo_streak = 0
		standing_platform = null
		standing_platform_last_x = 0.0
		_save_record(score)
		_save_settings()
		_update_records_display()
		_play_fail_sfx()

func _adjust_brightness(amount: float) -> void:
	brightness = clamp(brightness + amount, BRIGHTNESS_MIN, BRIGHTNESS_MAX)
	_apply_brightness()
	_save_settings()
	_refresh_ui()

func _apply_brightness() -> void:
	var tint: Color = Color(brightness, brightness, brightness, 1.0)
	platforms_root.modulate = tint
	player.modulate = tint

func _adjust_sfx_volume(amount: float) -> void:
	sfx_volume = clamp(sfx_volume + amount, SFX_VOLUME_MIN, SFX_VOLUME_MAX)
	_apply_sfx_volume()
	_save_settings()
	_refresh_ui()

func _register_perfect_count() -> void:
	if current_mode != GameMode.CLASSIC:
		return
	perfect_count_in_run += 1
	perfect_count_label.text = _t("perfect_count") % perfect_count_in_run
	perfect_count_label.visible = true
	perfect_display_timer += PERFECT_DISPLAY_EXTEND
	perfect_idle_timer = 0.0

func _register_jump_combo() -> void:
	if current_mode != GameMode.CLASSIC:
		return
	var now_sec: float = Time.get_ticks_msec() / 1000.0
	if last_jump_time_sec < 0.0 or now_sec - last_jump_time_sec > COMBO_INTERVAL_LIMIT:
		combo_count = 1
	else:
		combo_count += 1
	last_jump_time_sec = now_sec
	combo_label.text = _t("combo") % combo_count
	combo_label.visible = true
	combo_display_timer = COMBO_DISPLAY_TIME

func _apply_sfx_volume() -> void:
	var db: float = linear_to_db(max(0.001, sfx_volume))
	if sfx_land_player != null:
		sfx_land_player.volume_db = db
	if sfx_perfect_player != null:
		sfx_perfect_player.volume_db = db
	if sfx_fail_player != null:
		sfx_fail_player.volume_db = db
	if sfx_charge_player != null:
		sfx_charge_player.volume_db = db

func _setup_sfx_players() -> void:
	sfx_land_player = _create_sfx_player("SfxLand")
	sfx_perfect_player = _create_sfx_player("SfxPerfect")
	sfx_fail_player = _create_sfx_player("SfxFail")
	sfx_charge_player = _create_sfx_player("SfxCharge")

func _create_sfx_player(player_name: String) -> AudioStreamPlayer:
	var player_node: AudioStreamPlayer = AudioStreamPlayer.new()
	player_node.name = player_name
	var generator: AudioStreamGenerator = AudioStreamGenerator.new()
	generator.mix_rate = SFX_SAMPLE_RATE
	generator.buffer_length = SFX_BUFFER_LENGTH
	player_node.stream = generator
	add_child(player_node)
	return player_node

func _play_pattern(player_node: AudioStreamPlayer, notes: Array, volume: float) -> void:
	if player_node == null:
		return
	var generator: AudioStreamGenerator = player_node.stream as AudioStreamGenerator
	if generator == null:
		return
	player_node.stop()
	player_node.play()
	var playback: AudioStreamGeneratorPlayback = player_node.get_stream_playback() as AudioStreamGeneratorPlayback
	if playback == null:
		return
	for note in notes:
		var freq: float = note.x
		var duration: float = note.y
		var frame_count: int = max(1, int(duration * generator.mix_rate))
		for i: int in range(frame_count):
			var t: float = float(i) / generator.mix_rate
			var progress: float = float(i) / float(frame_count)
			var env: float = pow(1.0 - progress, 1.9) * sin(PI * progress)
			var fundamental: float = sin(TAU * freq * t)
			var harmonic: float = 0.18 * sin(TAU * freq * 2.0 * t)
			var sample: float = (fundamental + harmonic) * env * volume
			playback.push_frame(Vector2(sample, sample))

func _play_land_sfx() -> void:
	_play_pattern(sfx_land_player, [Vector2(360.0, 0.07), Vector2(430.0, 0.06)], 0.22)

func _play_perfect_land_sfx() -> void:
	_play_pattern(sfx_perfect_player, [Vector2(460.0, 0.07), Vector2(560.0, 0.07), Vector2(660.0, 0.08)], 0.24)

func _play_fail_sfx() -> void:
	_play_pattern(sfx_fail_player, [Vector2(300.0, 0.08), Vector2(230.0, 0.1), Vector2(180.0, 0.13)], 0.25)

func _play_charge_ready_sfx() -> void:
	_play_pattern(sfx_charge_player, [Vector2(690.0, 0.045)], 0.2)

func _load_records() -> void:
	recent_records.clear()
	if not FileAccess.file_exists(RECORDS_FILE_PATH):
		_update_records_display()
		return
	var file: FileAccess = FileAccess.open(RECORDS_FILE_PATH, FileAccess.READ)
	if file == null:
		_update_records_display()
		return
	var raw: String = file.get_as_text()
	file.close()
	var parsed: Variant = JSON.parse_string(raw)
	if parsed is Array:
		recent_records = parsed
	if recent_records.size() > MAX_RECORDS:
		recent_records = recent_records.slice(0, MAX_RECORDS)
	_update_records_display()

func _load_settings() -> void:
	if not FileAccess.file_exists(SETTINGS_FILE_PATH):
		return
	var file: FileAccess = FileAccess.open(SETTINGS_FILE_PATH, FileAccess.READ)
	if file == null:
		return
	var raw: String = file.get_as_text()
	file.close()
	var parsed: Variant = JSON.parse_string(raw)
	if not (parsed is Dictionary):
		return
	var data: Dictionary = parsed
	brightness = clamp(float(data.get("brightness", brightness)), BRIGHTNESS_MIN, BRIGHTNESS_MAX)
	sfx_volume = clamp(float(data.get("sfx_volume", sfx_volume)), SFX_VOLUME_MIN, SFX_VOLUME_MAX)
	var saved_lang: String = str(data.get("language", current_language))
	if saved_lang == "zh" or saved_lang == "en":
		current_language = saved_lang
	subject_id = str(data.get("subject_id", ""))
	var saved_mode: String = str(data.get("mode", "classic"))
	current_mode = GameMode.RACE if saved_mode == "race" else GameMode.CLASSIC
	var saved_control: String = str(data.get("control_mode", "manual"))
	current_control_mode = ControlMode.MI if saved_control == "mi" else ControlMode.MANUAL
	var saved_mi_input: String = str(data.get("mi_input_mode", "offline"))
	current_mi_input_mode = MIInputMode.ONLINE if saved_mi_input == "online" else MIInputMode.OFFLINE
	var saved_duration: int = int(data.get("race_duration", RACE_DURATION_DEFAULT))
	race_duration_seconds = RACE_DURATION_DEFAULT
	for item: int in RACE_DURATION_OPTIONS:
		if item == saved_duration:
			race_duration_seconds = item
			break
	var saved_name: String = str(data.get("player_name", "Player"))
	if saved_name != "":
		player_name_edit.text = saved_name

func _save_settings() -> void:
	var data: Dictionary = {
		"subject_id": subject_id,
		"brightness": brightness,
		"sfx_volume": sfx_volume,
		"language": current_language,
		"control_mode": "mi" if current_control_mode == ControlMode.MI else "manual",
		"mi_input_mode": "online" if current_mi_input_mode == MIInputMode.ONLINE else "offline",
		"mode": "race" if current_mode == GameMode.RACE else "vertical_train_offline" if current_mode == GameMode.VERTICAL_TRAIN_OFFLINE else "classic",
		"race_duration": race_duration_seconds,
		"player_name": player_name_edit.text.strip_edges()
	}
	var file: FileAccess = FileAccess.open(SETTINGS_FILE_PATH, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(data))
		file.close()

func _browse_save_path() -> void:
	if _save_dir_dialog != null:
		_save_dir_dialog.popup_centered()

func _on_save_dir_selected(path: String) -> void:
	_save_path = path
	if _save_path_label != null:
		_save_path_label.text = "保存路径: " + path

func _create_subject_ui() -> void:
	subject_ui = Control.new()
	subject_ui.name = "SubjectUI"
	$HUD.add_child(subject_ui)

	# Reposition player_name_edit
	if player_name_edit != null:
		player_name_edit.position.x = 20
		player_name_edit.size.x = 150
		player_name_edit.placeholder_text = "被试ID"
		if not player_name_edit.text_changed.is_connected(_on_subject_id_changed):
			player_name_edit.text_changed.connect(_on_subject_id_changed)
		player_name_edit.text = subject_id

	# Toggle button
	var toggle_btn: Button = Button.new()
	toggle_btn.name = "SubjectToggleBtn"
	toggle_btn.text = "被试管理 ▼"
	toggle_btn.position = Vector2(178, player_name_edit.position.y if player_name_edit != null else 90)
	toggle_btn.size = Vector2(90, 28)
	var sb: StyleBoxFlat = StyleBoxFlat.new()
	sb.bg_color = Color(0.30, 0.55, 0.35, 0.85)
	sb.corner_radius_top_left = 5; sb.corner_radius_top_right = 5
	sb.corner_radius_bottom_right = 5; sb.corner_radius_bottom_left = 5
	toggle_btn.add_theme_stylebox_override("normal", sb)
	toggle_btn.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0, 1.0))
	toggle_btn.add_theme_font_size_override("font_size", 12)
	toggle_btn.pressed.connect(_toggle_subject_panel)
	subject_ui.add_child(toggle_btn)

	# Expandable panel
	var panel: Control = Control.new()
	panel.name = "SubjectPanel"
	panel.visible = false
	var bw: float = 520.0
	var bh: float = 340.0
	var bg: ColorRect = ColorRect.new()
	bg.name = "PanelBG"
	bg.color = Color(0.93, 0.95, 0.90, 0.96)
	bg.size = Vector2(bw, bh)
	bg.position = Vector2(20, toggle_btn.position.y + 34)
	panel.add_child(bg)

	_add_panel_label(panel, "被试管理", 28, bg.position.y + 10, 16, Color(0.15, 0.25, 0.15))
	# Subject info
	var info: Label = _add_panel_label(panel, "", 28, bg.position.y + 34, 13, Color(0.25, 0.35, 0.25))
	info.name = "SubjectInfo"
	info.text = _get_subject_session_info()
	# Session list
	var sl: Label = _add_panel_label(panel, "", 28, bg.position.y + 54, 11, Color(0.35, 0.45, 0.35))
	sl.name = "SessionList"
	sl.size = Vector2(bw - 56, 36)
	sl.text = _get_session_list_text()

	# Session config section
	_add_panel_label(panel, "—— 离线训练配置 ——", 28, bg.position.y + 94, 11, Color(0.20, 0.30, 0.20))

	_session_name_input = LineEdit.new()
	_session_name_input.placeholder_text = "会话名称(可选)"
	_session_name_input.position = Vector2(28, bg.position.y + 112)
	_session_name_input.size = Vector2(240, 22)
	_session_name_input.flat = true
	_session_name_input.add_theme_font_size_override("font_size", 11)
	panel.add_child(_session_name_input)

	var browse_btn: Button = Button.new()
	browse_btn.text = "选择路径..."
	browse_btn.position = Vector2(276, bg.position.y + 112)
	browse_btn.size = Vector2(80, 22)
	browse_btn.flat = true
	browse_btn.add_theme_font_size_override("font_size", 10)
	browse_btn.pressed.connect(_browse_save_path)
	panel.add_child(browse_btn)

	_save_path_label = Label.new()
	_save_path_label.position = Vector2(28, bg.position.y + 138)
	_save_path_label.size = Vector2(460, 16)
	_save_path_label.add_theme_font_size_override("font_size", 9)
	_save_path_label.add_theme_color_override("font_color", Color(0.35, 0.50, 0.35, 0.8))
	_save_path_label.text = "保存路径: user://training_data"
	panel.add_child(_save_path_label)

	_save_dir_dialog = FileDialog.new()
	_save_dir_dialog.file_mode = FileDialog.FILE_MODE_OPEN_DIR
	_save_dir_dialog.access = FileDialog.ACCESS_FILESYSTEM
	_save_dir_dialog.title = "选择离线数据保存路径"
	_save_dir_dialog.size = Vector2(500, 400)
	_save_dir_dialog.dir_selected.connect(_on_save_dir_selected)
	subject_ui.add_child(_save_dir_dialog)

	# Records section title
	_add_panel_label(panel, "—— 最近记录 ——", 28, bg.position.y + 162, 12, Color(0.20, 0.30, 0.20))
	# Records moved here
	var rl: Label = _add_panel_label(panel, "", 28, bg.position.y + 180, 11, Color(0.30, 0.40, 0.30))
	rl.name = "PanelRecords"
	rl.size = Vector2(bw - 56, 80)
	rl.text = _get_records_text()

	# Buttons row
	var by: float = bg.position.y + bh - 32
	var bx: float = 28.0
	_add_small_btn(panel, "刷新", bx, by, _refresh_subject_info); bx += 80
	_add_small_btn(panel, "打开目录", bx, by, _open_data_dir); bx += 80
	_add_small_btn(panel, "导出记录", bx, by, _export_records); bx += 80
	_add_small_btn(panel, "清除记录", bx, by, _clear_records_prompt)

	# Hide original records display
	if records_title != null:
		records_title.visible = false
	if records_label != null:
		records_label.visible = false

	subject_ui.add_child(panel)


func _add_panel_label(parent: Control, txt: String, x: float, y: float, fs: int, col: Color) -> Label:
	var lb: Label = Label.new()
	lb.text = txt
	lb.position = Vector2(x, y)
	lb.size = Vector2(460, fs + 6)
	lb.add_theme_color_override("font_color", col)
	lb.add_theme_font_size_override("font_size", fs)
	parent.add_child(lb)
	return lb


func _add_small_btn(parent: Control, txt: String, x: float, y: float, callback: Callable) -> void:
	var btn: Button = Button.new()
	btn.text = txt
	btn.position = Vector2(x, y)
	btn.size = Vector2(70, 22)
	var s: StyleBoxFlat = StyleBoxFlat.new()
	s.bg_color = Color(0.30, 0.55, 0.35, 0.8)
	s.corner_radius_top_left = 4; s.corner_radius_top_right = 4
	s.corner_radius_bottom_right = 4; s.corner_radius_bottom_left = 4
	btn.add_theme_stylebox_override("normal", s)
	btn.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0, 1.0))
	btn.add_theme_font_size_override("font_size", 11)
	btn.pressed.connect(callback)
	parent.add_child(btn)


func _create_fatigue_ui() -> void:
	# 专注度条 —— state_label 右侧
	var container: Control = Control.new()
	container.name = "FatigueUI"
	container.position = Vector2(20, 164)
	$HUD.add_child(container)

	var bg: ColorRect = ColorRect.new()
	bg.name = "FatigueBG"
	bg.color = Color(0.15, 0.15, 0.15, 0.55)
	bg.size = Vector2(140, 18)
	bg.position = Vector2(0, 0)
	container.add_child(bg)

	var fill: ColorRect = ColorRect.new()
	fill.name = "FatigueFill"
	fill.size = Vector2(70, 16)
	fill.position = Vector2(1, 1)
	container.add_child(fill)

	var label: Label = Label.new()
	label.name = "FatigueLabel"
	label.text = "🟢 专注度 50"
	label.position = Vector2(4, 1)
	label.size = Vector2(132, 16)
	label.add_theme_color_override("font_color", Color(1, 1, 1, 0.9))
	label.add_theme_font_size_override("font_size", 11)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	container.add_child(label)

func _update_fatigue_ui() -> void:
	var container: Control = $HUD.get_node_or_null("FatigueUI")
	if container == null:
		return
	var fill: ColorRect = container.get_node_or_null("FatigueFill")
	var label: Label = container.get_node_or_null("FatigueLabel")
	if fill == null or label == null:
		return

	var focus: float = 100.0 - mi_fatigue
	var w: float = clamp(focus / 100.0 * 138.0, 10.0, 138.0)
	fill.size.x = w

	var t: float = mi_fatigue / 100.0
	if t < 0.4: fill.color = Color(0.25, 0.72, 0.30, 0.9)
	elif t < 0.7: fill.color = Color(0.95, 0.70, 0.15, 0.9)
	else: fill.color = Color(0.95, 0.30, 0.20, 0.9)

	var status: String
	if mi_fatigue < 30: status = "🟢 "
	elif mi_fatigue < 60: status = "🟡 "
	else: status = "🔴 "
	label.text = status + "专注度 " + str(int(focus))

func _get_records_text() -> String:
	if recent_records.is_empty():
		return "暂无记录"
	var lines: Array[String] = []
	var max_s: int = min(5, recent_records.size())
	for i: int in range(max_s):
		var item: Dictionary = recent_records[i]
		var time_text: String = str(item.get("time", ""))
		var player_text: String = str(item.get("player", _t("default_player")))
		var score_text: String = str(item.get("score", ""))
		lines.append("%d. %s %s %s" % [i + 1, time_text, player_text, score_text])
	return "\n".join(lines)


func _open_data_dir() -> void:
	var path: String = OS.get_user_data_dir().path_join("training_data")
	DirAccess.make_dir_recursive_absolute("user://training_data")
	OS.shell_open(ProjectSettings.globalize_path("user://training_data"))


func _export_records() -> void:
	var text: String = "被试ID: %s\\n" % subject_id
	text += _get_records_text()
	text += "\n\n\u4f1a\u8bdd\u5217\u8868:\n" + _get_session_list_text()
	var file: FileAccess = FileAccess.open("user://export_records.txt", FileAccess.WRITE)
	if file != null:
		file.store_string(text)
		file.close()
	OS.shell_open(ProjectSettings.globalize_path("user://export_records.txt"))


func _clear_records_prompt() -> void:
	recent_records.clear()
	_save_settings()
	_update_records_display()
	_refresh_subject_info()


func _toggle_subject_panel() -> void:
	if subject_ui == null:
		return
	var panel: Control = subject_ui.get_node_or_null("SubjectPanel")
	var btn: Button = subject_ui.get_node_or_null("SubjectToggleBtn")
	if panel != null:
		panel.visible = not panel.visible
		if btn != null:
			btn.text = "被试管理 \u25b2" if panel.visible else "被试管理 \u25bc"
		if panel.visible:
			_refresh_subject_info()

func _get_session_list_text() -> String:
	var sid: String = subject_id.strip_edges()
	if sid == "":
		return "\uff08未设置被试ID\uff09"
	var d: String = "user://training_data/"
	var files: Array = []
	var da: DirAccess = DirAccess.open(d)
	if da != null:
		da.list_dir_begin()
		var fn: String = da.get_next()
		while fn != "":
			if sid in fn and fn.ends_with(".jsonl"):
				files.append(fn)
			fn = da.get_next()
		da.list_dir_end()
	if files.is_empty():
		return "暂无训练数据"
	files.sort()
	var text: String = ""
	var max_s: int = min(3, files.size())
	for i in range(max_s):
		text += files[files.size() - 1 - i] + "\n"
	if files.size() > max_s:
		text += "... 共%d次训练记录" % files.size()
	return text


func _on_subject_id_changed(txt: String) -> void:
	subject_id = txt
	_save_settings()
	_refresh_subject_info()

func _refresh_subject_info() -> void:
	if subject_ui == null:
		return
	var panel: Control = subject_ui.get_node_or_null("SubjectPanel")
	if panel == null:
		return
	var lb: Label = panel.get_node_or_null("SubjectInfo")
	if lb != null:
		lb.text = _get_subject_session_info()
	var sl: Label = panel.get_node_or_null("SessionList")
	if sl != null:
		sl.text = _get_session_list_text()

func _get_subject_session_info() -> String:
	var sid: String = subject_id.strip_edges()
	if sid == "":
		return "未设置被试ID"
	var d: String = "user://training_data/"
	var count: int = 0
	var da: DirAccess = DirAccess.open(d)
	if da != null:
		da.list_dir_begin()
		var fn: String = da.get_next()
		while fn != "":
			if sid in fn and fn.ends_with(".jsonl"):
				count += 1
			fn = da.get_next()
		da.list_dir_end()
	return "已采集 %d 次训练" % count

func mi_send_event(ev_type: String, extra: Dictionary = {}) -> void:
	if mi_ws == null or mi_ws.get_ready_state() != WebSocketPeer.STATE_OPEN:
		return
	var p: Dictionary = {"type": ev_type, "timestamp_ms": int(Time.get_unix_time_from_system() * 1000.0)}
	p.merge(extra)
	mi_ws.send_text(JSON.stringify(p))

func end_game(final_score) -> void:
	_save_record(final_score)
	_save_settings()
	_update_records_display()
	game_state = GameState.GAME_OVER
	wait_for_accept_release = true
	_refresh_ui()

func _save_record(final_score) -> void:
	var player_name: String = player_name_edit.text.strip_edges()
	if player_name == "":
		player_name = _t("default_player")
	var record: Dictionary = {
		"time": _now_text(),
		"player": player_name,
		"score": final_score
	}
	recent_records.push_front(record)
	if recent_records.size() > MAX_RECORDS:
		recent_records = recent_records.slice(0, MAX_RECORDS)
	var file: FileAccess = FileAccess.open(RECORDS_FILE_PATH, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(recent_records))
		file.close()

func _now_text() -> String:
	var d: Dictionary = Time.get_datetime_dict_from_system()
	return "%04d-%02d-%02d %02d:%02d:%02d" % [
		int(d.get("year", 2026)),
		int(d.get("month", 1)),
		int(d.get("day", 1)),
		int(d.get("hour", 0)),
		int(d.get("minute", 0)),
		int(d.get("second", 0))
	]

func _update_records_display() -> void:
	if records_label == null:
		return
	if recent_records.is_empty():
		records_label.text = _t("records_empty")
		return
	var lines: Array[String] = []
	for i: int in range(recent_records.size()):
		var item: Dictionary = recent_records[i]
		var time_text: String = str(item.get("time", "----"))
		var player_text: String = str(item.get("player", _t("default_player")))
		var score_text: String = str(item.get("score", 0))
		lines.append(_t("record_line") % [i + 1, time_text, player_text, score_text])
	records_label.text = "\n".join(lines)
	_refresh_subject_info()

func _refresh_ui() -> void:
	if current_mode == GameMode.RACE:
		score_label.text = "%s: %d" % [_t("distance"), score]
	elif current_mode == GameMode.VERTICAL_TRAIN:
		score_label.text = ""
	elif current_mode == GameMode.VERTICAL_TRAIN_OFFLINE:
		score_label.text = ""
	else:
		score_label.text = "%s: %d" % [_t("score"), score]
	brightness_label.text = "%s: %d%% (-/+)" % [_t("brightness"), int(brightness * 100.0)]
	volume_label.text = "%s: %d%% ([/])" % [_t("volume"), int(sfx_volume * 100.0)]
	language_label.text = _t("language")
	control_label.text = _t("control")
	mode_label.text = _t("mode")
	duration_label.text = _t("race_time")
	mi_input_label.text = _t("mi_input")
	control_option.select(0 if current_control_mode == ControlMode.MANUAL else 1)
	mi_input_option.select(0 if current_mi_input_mode == MIInputMode.OFFLINE else 1)
	player_name_edit.placeholder_text = _t("player_name_placeholder")
	records_title.text = _t("records_title")
	start_label.text = _t("start_title")
	race_info_label.text = _t("race_info") % [race_time_left, race_distance]
	if mi_ws != null and mi_ws.get_ready_state() == WebSocketPeer.STATE_OPEN:
		network_label.text = "%s: %s" % [_t("network"), _t("net_online")]
	elif mi_ws != null and mi_ws.get_ready_state() == WebSocketPeer.STATE_CONNECTING:
		network_label.text = "%s: %s" % [_t("network"), _t("net_connecting")]
	else:
		network_label.text = "%s: %s" % [_t("network"), _t("net_offline")]
	records_title.visible = false
	records_label.visible = false
	player_name_edit.visible = game_state != GameState.PLAYING
	language_label.visible = game_state != GameState.PLAYING
	language_option.visible = game_state != GameState.PLAYING
	mode_label.visible = game_state != GameState.PLAYING
	mode_option.visible = game_state != GameState.PLAYING
	control_label.visible = game_state != GameState.PLAYING
	control_option.visible = game_state != GameState.PLAYING
	mi_input_label.visible = game_state != GameState.PLAYING and current_control_mode == ControlMode.MI
	mi_input_option.visible = game_state != GameState.PLAYING and current_control_mode == ControlMode.MI
	duration_label.visible = game_state != GameState.PLAYING and current_mode == GameMode.RACE
	duration_option.visible = game_state != GameState.PLAYING and current_mode == GameMode.RACE
	race_info_label.visible = game_state == GameState.PLAYING and current_mode == GameMode.RACE
	platform_minimap.visible = false
	_update_fatigue_ui()
	if subject_ui != null:
		subject_ui.visible = game_state != GameState.PLAYING

	if game_state != GameState.PLAYING or current_mode != GameMode.CLASSIC:
		perfect_count_label.visible = false
		combo_label.visible = false
	start_label.visible = game_state == GameState.START
	if game_state == GameState.START:
		state_label.text = _t("state_start")
	elif game_state == GameState.GAME_OVER:
		state_label.text = _t("state_race_over") if current_mode == GameMode.RACE else _t("state_game_over")
	elif current_mode == GameMode.CLASSIC and feedback_timer > 0.0 and feedback_text != "":
		state_label.text = feedback_text
	elif current_mode == GameMode.VERTICAL_TRAIN and game_state == GameState.PLAYING:
		state_label.text = "MI: %s    " % mi_display_label
	elif current_mode == GameMode.VERTICAL_TRAIN_OFFLINE and game_state == GameState.PLAYING:
		var pn: Array[String] = ["START", "MI TASK", "JUMP", "SCORE", "RELAX"]
		state_label.text = pn[clampi(offline_train.phase, 0, 4)]
	elif current_control_mode == ControlMode.MI:
		if game_state == GameState.PLAYING:
			var mi_state_key: String = "state_mi_idle"
			if mi_state == MIState.CHARGING:
				mi_state_key = "state_mi_charging"
			elif mi_state == MIState.REST_KEEPALIVE:
				mi_state_key = "state_mi_keepalive"
			elif mi_state == MIState.AIRBORNE:
				mi_state_key = "state_mi_airborne"
			state_label.text = _t("mi_metrics") % [mi_messages_received, mi_out_of_order_dropped, mi_stale_dropped, mi_cancel_count, mi_air_jump_count, mi_latency_ms_ema]
			state_label.text += " | " + _t(mi_state_key)
		else:
			state_label.text = _t("state_idle")
	elif player.is_airborne:
		state_label.text = _t("state_flying")
	elif player.is_charging:
		state_label.text = _t("state_charging") % (player.charge_ratio() * 100.0)
	else:
		state_label.text = _t("state_idle")

	if level_mode != null:
		level_mode.update_hud()
	if offline_train != null:
		offline_train.update_hud()
