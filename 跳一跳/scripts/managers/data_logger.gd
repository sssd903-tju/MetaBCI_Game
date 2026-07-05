# DataLogger - handles trial data recording to JSON Lines files
extends RefCounted

const DATA_DIR: String = "user://training_data"

var session_file: String = ""
var trial_id: int = 0
var trials: Array[Dictionary] = []
var session_meta: Dictionary = {}


func start_session(total_layers: int, cycle_duration: float, phases: Dictionary, session_name: String = "", save_path: String = "") -> void:
	var data_dir: String = save_path if save_path != "" else DATA_DIR
	DirAccess.make_dir_recursive_absolute(data_dir)
	var dt: Dictionary = Time.get_datetime_dict_from_system()
	var filename: String
	if session_name != "":
		filename = "%s_%04d%02d%02d_%02d%02d%02d.jsonl" % [
			session_name, dt["year"], dt["month"], dt["day"], dt["hour"], dt["minute"], dt["second"]
		]
	else:
		filename = "session_%04d%02d%02d_%02d%02d%02d.jsonl" % [
			dt["year"], dt["month"], dt["day"], dt["hour"], dt["minute"], dt["second"]
		]
	session_file = data_dir.path_join(filename)
	trial_id = 0
	trials.clear()
	session_meta = phases
	var header: Dictionary = {
		"type": "session_start",
		"timestamp_ms": int(Time.get_unix_time_from_system() * 1000.0),
		"total_layers": total_layers,
		"mode": phases.get("mode", "offline_train"),
		"cycle_duration_s": cycle_duration,
		"phases": phases
	}
	_append_json(header)
	print("DataLogger: ", session_file)


func save_trial(layer: int, ground_truth: String, mi_decision: String, correct: bool, trial_start_ms: int) -> void:
	trial_id += 1
	var now_ms: int = int(Time.get_unix_time_from_system() * 1000.0)
	var trial: Dictionary = {
		"type": "trial",
		"trial_id": trial_id,
		"layer": layer,
		"ground_truth": ground_truth,
		"mi_decision": mi_decision,
		"correct": correct,
		"timestamp_trial_start_ms": trial_start_ms,
		"timestamp_trial_end_ms": now_ms,
	}
	_append_json(trial)
	trials.append(trial)


func save_trial_full(trial_data: Dictionary) -> void:
	trial_id += 1
	trial_data["trial_id"] = trial_id
	trial_data["type"] = "trial"
	_append_json(trial_data)
	trials.append(trial_data)


func get_all_trials() -> Array[Dictionary]:
	return trials.duplicate()


func get_session_summary() -> Dictionary:
	var session_end_ms: int = int(Time.get_unix_time_from_system() * 1000.0)
	return {
		"type": "session_end",
		"session_file": session_file,
		"timestamp_ms": session_end_ms,
		"total_trials": trials.size(),
		"mode": session_meta.get("mode", ""),
		"trials": get_all_trials()
	}


func _append_json(data: Dictionary) -> void:
	if session_file == "":
		return
	var file: FileAccess = FileAccess.open(session_file, FileAccess.READ_WRITE)
	if file == null:
		file = FileAccess.open(session_file, FileAccess.WRITE)
		if file == null:
			return
	else:
		file.seek_end()
	file.store_line(JSON.stringify(data))
	file.close()
