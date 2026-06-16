extends Node
## ParadigmManager — 范式管理器
##
## 负责范式注册、切换、生命周期管理

signal paradigm_changed(from_paradigm: GlobalConfig.ParadigmType, to_paradigm: GlobalConfig.ParadigmType)
signal paradigm_started(paradigm: GlobalConfig.ParadigmType)
signal paradigm_ended(paradigm: GlobalConfig.ParadigmType)

var current_paradigm := GlobalConfig.ParadigmType.FOCUS_DETECTION


func _ready() -> void:
	print("[ParadigmManager] 初始化完成，已注册范式: ",
		GlobalConfig.PARADIGM_NAMES.values())


## 切换到指定范式场景
func switch_to(paradigm: GlobalConfig.ParadigmType) -> void:
	if not GlobalConfig.PARADIGM_SCENES.has(paradigm):
		push_error("[ParadigmManager] 未知范式: ", paradigm)
		return

	var old := current_paradigm
	current_paradigm = paradigm
	paradigm_changed.emit(old, paradigm)

	# 加载场景
	var scene_path: String = GlobalConfig.PARADIGM_SCENES[paradigm]
	var scene := load(scene_path) as PackedScene
	if scene == null:
		push_error("[ParadigmManager] 无法加载场景: ", scene_path)
		return

	# 切换场景
	get_tree().change_scene_to_packed(scene)
	paradigm_started.emit(paradigm)

	print("[ParadigmManager] 切换到范式: ", GlobalConfig.PARADIGM_NAMES[paradigm])


## 返回主菜单
func go_to_main_menu() -> void:
	paradigm_ended.emit(current_paradigm)
	get_tree().change_scene_to_file("res://scenes/main_menu/MainMenu.tscn")


## 启动当前范式
func start_current() -> void:
	switch_to(current_paradigm)


## 获取范式名称
func get_paradigm_name(paradigm: GlobalConfig.ParadigmType = current_paradigm) -> String:
	return GlobalConfig.PARADIGM_NAMES.get(paradigm, "未知范式")
