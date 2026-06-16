extends Node
## BCIConnector — WebSocket 客户端，负责与 Python BCI 后端通信
##
## 协议格式 (JSON):
##   接收 (Python → Godot):
##     {"type": "focus", "ratio": 2.8, "theta": 0.5, "alpha": 0.3, "beta": 0.2, "timestamp_ms": 1718000000000}
##     {"type": "eeg_quality", "value": 0.85}
##     {"type": "paradigm_cmd", "cmd": "start"|"stop"|"pause"}
##
##   发送 (Godot → Python):
##     {"type": "game_event", "event": "trial_start"|"trial_end"|"platform_break", "timestamp_ms": ...}
##     {"type": "game_state", "score": 42, "player_y": 300}

signal focus_data_received(ratio: float, theta: float, alpha: float, beta: float)
signal eeg_quality_changed(value: float)
signal bci_connected()
signal bci_disconnected()
signal paradigm_command_received(cmd: String)

var _ws := WebSocketPeer.new()
var _connected := false
var _last_data_time := 0.0
var _reconnect_timer := 0.0
var _url := ""

## 最新专注度数据
var latest_focus_ratio := 0.0
var latest_theta := 0.0
var latest_alpha := 0.0
var latest_beta := 0.0

## 脑电信号质量 [0.0, 1.0]
var eeg_quality := 0.0


func _ready() -> void:
	_url = GlobalConfig.BCI_WS_URL
	_connect_to_server()


func _process(delta: float) -> void:
	_ws.poll()

	var state := _ws.get_ready_state()

	if state == WebSocketPeer.STATE_OPEN:
		if not _connected:
			_connected = true
			_last_data_time = Time.get_ticks_msec() / 1000.0
			bci_connected.emit()
			print("[BCIConnector] 已连接到 BCI 服务器: ", _url)

		# 读取消息
		while _ws.get_available_packet_count() > 0:
			var packet := _ws.get_packet()
			if packet:
				_handle_packet(packet.get_string_from_utf8())

		# 检查数据超时
		var now := Time.get_ticks_msec() / 1000.0
		if now - _last_data_time > GlobalConfig.BCI_DATA_TIMEOUT:
			if eeg_quality > 0.0:
				eeg_quality = maxf(0.0, eeg_quality - delta * 0.5)
				eeg_quality_changed.emit(eeg_quality)

	elif state == WebSocketPeer.STATE_CLOSED:
		if _connected:
			_connected = false
			bci_disconnected.emit()
			print("[BCIConnector] 与 BCI 服务器断开连接")

		# 自动重连
		_reconnect_timer += delta
		if _reconnect_timer >= GlobalConfig.BCI_RECONNECT_INTERVAL:
			_reconnect_timer = 0.0
			_connect_to_server()


func _connect_to_server() -> void:
	var err := _ws.connect_to_url(_url)
	if err != OK:
		print("[BCIConnector] 连接失败: ", _url, " 错误码: ", err)
	else:
		print("[BCIConnector] 正在连接: ", _url)


func _handle_packet(raw: String) -> void:
	var json := JSON.new()
	var err := json.parse(raw)
	if err != OK:
		print("[BCIConnector] JSON 解析失败: ", raw)
		return

	var data: Dictionary = json.get_data()
	if not data.has("type"):
		return

	_last_data_time = Time.get_ticks_msec() / 1000.0

	match data.get("type"):
		"focus":
			latest_focus_ratio = data.get("ratio", 0.0)
			latest_theta = data.get("theta", 0.0)
			latest_alpha = data.get("alpha", 0.0)
			latest_beta = data.get("beta", 0.0)
			focus_data_received.emit(
				latest_focus_ratio,
				latest_theta,
				latest_alpha,
				latest_beta
			)

		"eeg_quality":
			eeg_quality = data.get("value", 0.0)
			eeg_quality_changed.emit(eeg_quality)

		"paradigm_cmd":
			var cmd: String = data.get("cmd", "")
			paradigm_command_received.emit(cmd)


## 发送游戏事件到 Python 后端
func send_game_event(event_name: String, extra := {}) -> void:
	_send({
		"type": "game_event",
		"event": event_name,
		"timestamp_ms": Time.get_ticks_msec(),
		"extra": extra,
	})


## 发送游戏状态（分数、位置等）
func send_game_state(data: Dictionary) -> void:
	var msg := {
		"type": "game_state",
		"timestamp_ms": Time.get_ticks_msec(),
	}
	msg.merge(data)
	_send(msg)


func _send(data: Dictionary) -> void:
	if _ws.get_ready_state() != WebSocketPeer.STATE_OPEN:
		return
	var json := JSON.stringify(data)
	_ws.send_text(json)


## 模拟 BCI 数据（用于无硬件测试）
func simulate_focus(ratio: float) -> void:
	latest_focus_ratio = ratio
	focus_data_received.emit(ratio, 0.0, 0.0, 0.0)
