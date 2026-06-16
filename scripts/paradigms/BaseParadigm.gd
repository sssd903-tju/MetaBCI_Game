class_name BaseParadigm
extends Node
## BaseParadigm — 所有 BCI 范式的抽象基类
##
## 子类必须实现:
##   _on_paradigm_start()  — 范式启动
##   _on_paradigm_end()    — 范式结束
##   _on_bci_data(data)    — 处理 BCI 数据
##
## 可选覆写:
##   _on_paradigm_pause()
##   _on_paradigm_resume()
##   _get_paradigm_info() -> Dictionary


## 范式类型标识
var paradigm_type: GlobalConfig.ParadigmType

## 是否正在运行
var is_running := false

## 是否暂停
var is_paused := false


func _ready() -> void:
	_setup()


func _setup() -> void:
	"""初始化范式"""
	# 连接 BCI 数据信号
	if BCIConnector.focus_data_received.is_connected(_on_focus_data):
		BCIConnector.focus_data_received.disconnect(_on_focus_data)
	BCIConnector.focus_data_received.connect(_on_focus_data)

	if BCIConnector.paradigm_command_received.is_connected(_on_paradigm_cmd):
		BCIConnector.paradigm_command_received.disconnect(_on_paradigm_cmd)
	BCIConnector.paradigm_command_received.connect(_on_paradigm_cmd)

	_on_paradigm_start()
	is_running = true
	print("[%s] 范式启动" % _get_paradigm_name())


func _exit_tree() -> void:
	_teardown()


func _teardown() -> void:
	"""清理范式"""
	if BCIConnector.focus_data_received.is_connected(_on_focus_data):
		BCIConnector.focus_data_received.disconnect(_on_focus_data)
	if BCIConnector.paradigm_command_received.is_connected(_on_paradigm_cmd):
		BCIConnector.paradigm_command_received.disconnect(_on_paradigm_cmd)

	is_running = false
	_on_paradigm_end()
	print("[%s] 范式结束" % _get_paradigm_name())


func _on_focus_data(ratio: float, theta: float, alpha: float, beta: float) -> void:
	"""处理专注度数据（来自 BCIConnector）"""
	if is_paused:
		return
	_on_bci_data({
		"ratio": ratio,
		"theta": theta,
		"alpha": alpha,
		"beta": beta,
	})


func _on_paradigm_cmd(cmd: String) -> void:
	"""处理 Python 后端指令"""
	match cmd:
		"pause":
			_on_paradigm_pause()
		"resume":
			_on_paradigm_resume()
		"stop":
			ParadigmManager.go_to_main_menu()


# ============================================================
# 子类必需覆写的方法
# ============================================================

func _on_paradigm_start() -> void:
	"""范式启动时调用"""
	push_warning("[%s] _on_paradigm_start() 未被覆写" % _get_paradigm_name())


func _on_paradigm_end() -> void:
	"""范式结束时调用"""
	push_warning("[%s] _on_paradigm_end() 未被覆写" % _get_paradigm_name())


func _on_bci_data(_data: Dictionary) -> void:
	"""处理 BCI 数据
	Args:
	    data: {"ratio": float, "theta": float, "alpha": float, "beta": float}
	"""
	push_warning("[%s] _on_bci_data() 未被覆写" % _get_paradigm_name())


# ============================================================
# 可选覆写
# ============================================================

func _on_paradigm_pause() -> void:
	is_paused = true
	print("[%s] 暂停" % _get_paradigm_name())


func _on_paradigm_resume() -> void:
	is_paused = false
	print("[%s] 恢复" % _get_paradigm_name())


func _get_paradigm_name() -> String:
	return GlobalConfig.PARADIGM_NAMES.get(paradigm_type, "BaseParadigm")


func _get_paradigm_info() -> Dictionary:
	return {
		"name": _get_paradigm_name(),
		"type": paradigm_type,
		"running": is_running,
		"paused": is_paused,
	}
