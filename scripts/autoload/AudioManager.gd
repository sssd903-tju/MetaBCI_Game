extends Node
## AudioManager — 全局音频管理器
##
## 优先加载 assets/audio/ 外部音频，未找到回退程序化音效
##
## 外部文件 (放 assets/audio/, 支持 .ogg .wav .mp3):
##   bow_draw.ogg      — 弓弦拉紧 (循环)
##   bow_release.ogg   — 射箭释放
##   arrow_hit.ogg     — 命中靶子
##   arrow_hit_10.ogg  — 十环
##   arrow_miss.ogg    — 脱靶
##   combo.ogg         — 连击

const SAMPLE_RATE := 44100.0
const AUDIO_DIR := "res://assets/audio"

const SOUND_MAP := {
	"charge":     "bow_draw",
	"bow_shoot":  "bow_release",
	"hit":        "arrow_hit",
	"hit_10":     "arrow_hit_10",
	"miss":       "arrow_miss",
	"combo":      "combo",
}

var _sound_cache: Dictionary = {}
var _charge_player: AudioStreamPlayer = null


func _ready() -> void:
	for key in SOUND_MAP:
		_sound_cache[key] = _load_external(SOUND_MAP[key])
		if _sound_cache[key] == null:
			_sound_cache[key] = _gen_fallback(key)
	var ext_count := 0
	for key in _sound_cache:
		if not _is_procedural(key):
			ext_count += 1
	print("[AudioManager] 音效就绪 (外部:%d/程序化:%d)" % [ext_count, _sound_cache.size() - ext_count])


func _load_external(base_name: String) -> AudioStream:
	for ext in [".ogg", ".wav", ".mp3"]:
		var path: String = AUDIO_DIR + "/" + base_name + ext
		if ResourceLoader.exists(path):
			var s: AudioStream = load(path)
			if s:
				print("[AudioManager] 加载: %s" % path)
				return s
	return null


func _gen_fallback(key: String) -> AudioStream:
	match key:
		"charge":    return _gen_charge_loop()
		"bow_shoot": return _gen_bow_shoot()
		"hit":       return _gen_hit()
		"hit_10":    return _gen_hit_bullseye()
		"miss":      return _gen_miss()
		"combo":     return _gen_combo()
	return _gen_tone(0.05, 440.0, 0.1)


func _is_procedural(key: String) -> bool:
	var s: AudioStream = _sound_cache.get(key)
	return s == null or s.get_class() == "AudioStreamWAV"


# ============================================================
# 公开 API
# ============================================================

func play_bow_shoot() -> void:
	_play_cached("bow_shoot", -3.0)


func play_hit(ring: int) -> void:
	if ring == 10:
		_play_cached("hit", -3.0)
	else:
		var player := _create_player()
		player.stream = _sound_cache.get("hit", _gen_hit())
		player.pitch_scale = 0.7 + ring * 0.06
		player.volume_db = -3.0
		_add_and_play(player)


func play_miss() -> void:
	_play_cached("miss", -6.0)


func play_combo(combo_count: int) -> void:
	# 连击几次响几次，间隔 120ms
	for i in range(combo_count):
		var player := _create_player()
		player.stream = _sound_cache.get("combo", _gen_combo())
		player.volume_db = -3.0
		add_child(player)
		# 延迟播放
		get_tree().create_timer(i * 0.12).timeout.connect(player.play)
		player.finished.connect(_on_finished.bind(player))


func play_charge() -> void:
	if _charge_player:
		stop_charge()
	_charge_player = _create_player()
	_charge_player.stream = _sound_cache["charge"]
	_charge_player.pitch_scale = 0.5
	_charge_player.volume_db = -10.0
	_charge_player.finished.connect(_on_charge_loop_finished)
	add_child(_charge_player)
	_charge_player.play()


func _on_charge_loop_finished() -> void:
	if _charge_player:
		_charge_player.play()


func update_charge(progress: float) -> void:
	if not _charge_player:
		return
	# 音高攀升 0.5→2.0: 模拟弓弦越拉越紧
	_charge_player.pitch_scale = lerpf(0.5, 2.0, clampf(progress, 0.0, 1.0))
	# 音量渐强 -10→-4dB
	_charge_player.volume_db = lerpf(-10.0, -4.0, clampf(progress, 0.0, 1.0))


func stop_charge() -> void:
	if _charge_player:
		_charge_player.stop()
		_charge_player.queue_free()
		_charge_player = null


func play_baseline_complete() -> void:
	# 基线采集完成 — 升调双音提示
	var p1 := _create_player()
	p1.stream = _gen_tone(0.15, 660.0, 0.3)
	_add_and_play(p1)
	var p2 := _create_player()
	p2.stream = _gen_tone(0.25, 880.0, 0.35)
	get_tree().create_timer(0.15).timeout.connect(_add_and_play.bind(p2))


# ============================================================
# 内部方法
# ============================================================

func _play_cached(key: String, volume_db: float) -> void:
	var stream: AudioStream = _sound_cache.get(key)
	if stream == null:
		return
	var player := _create_player()
	player.stream = stream
	player.volume_db = volume_db
	_add_and_play(player)


func _create_player() -> AudioStreamPlayer:
	var player := AudioStreamPlayer.new()
	player.bus = "Master"
	return player


func _add_and_play(player: AudioStreamPlayer) -> void:
	add_child(player)
	player.finished.connect(_on_finished.bind(player))
	player.play()


func _on_finished(player: AudioStreamPlayer) -> void:
	player.queue_free()


# ============================================================
# 程序化音效生成 (fallback)
# ============================================================

func _gen_bow_shoot() -> AudioStream:
	return _gen_twang(0.25, 800.0, 200.0)


func _gen_hit() -> AudioStream:
	return _gen_tone(0.08, 880.0, 0.3)


func _gen_hit_bullseye() -> AudioStream:
	return _gen_double_tone(0.15, 880.0, 1320.0)


func _gen_miss() -> AudioStream:
	return _gen_tone(0.2, 220.0, 0.2)


func _gen_combo() -> AudioStream:
	return _gen_rising_tone(0.15, 440.0, 880.0)


func _gen_charge_loop() -> AudioStreamWAV:
	var duration := 0.5
	var sample_count := int(SAMPLE_RATE * duration)
	var data := PackedByteArray()
	data.resize(sample_count * 2)

	var rng := RandomNumberGenerator.new()
	rng.seed = 42

	var creaks: Array[Dictionary] = []
	var t := 0.0
	while t < duration:
		creaks.append({
			"start": t,
			"duration": rng.randf_range(0.003, 0.015),
			"amp": rng.randf_range(0.15, 0.35),
		})
		t += rng.randf_range(0.02, 0.08)

	for i in range(sample_count):
		var now: float = float(i) / SAMPLE_RATE
		var value := 0.0
		for c: Dictionary in creaks:
			var elapsed: float = now - c.start
			if elapsed >= 0 and elapsed < c.duration:
				var env: float = 1.0 - (elapsed / c.duration)
				value += randf_range(-1.0, 1.0) * c.amp * env
				break
		value += randf_range(-0.01, 0.01)
		var sample16 := int(clampf(value, -1.0, 1.0) * 32767)
		data.encode_s16(i * 2, sample16)

	var stream := AudioStreamWAV.new()
	stream.data = data
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = int(SAMPLE_RATE)
	stream.stereo = false
	return stream


func _gen_tone(duration: float, freq: float, volume: float) -> AudioStreamWAV:
	var sample_count := int(SAMPLE_RATE * duration)
	var data := PackedByteArray()
	data.resize(sample_count * 2)
	for i in range(sample_count):
		var t_val: float = float(i) / SAMPLE_RATE
		var envelope := 1.0 - (float(i) / float(sample_count))
		var value := sin(2.0 * PI * freq * t_val) * volume * envelope
		var sample16 := int(clampf(value, -1.0, 1.0) * 32767)
		data.encode_s16(i * 2, sample16)
	var stream := AudioStreamWAV.new()
	stream.data = data
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = int(SAMPLE_RATE)
	stream.stereo = false
	return stream


func _gen_double_tone(duration: float, freq1: float, freq2: float) -> AudioStreamWAV:
	var sample_count := int(SAMPLE_RATE * duration)
	var data := PackedByteArray()
	data.resize(sample_count * 2)
	for i in range(sample_count):
		var t_val: float = float(i) / SAMPLE_RATE
		var envelope := 1.0 - (float(i) / float(sample_count))
		var v1 := sin(2.0 * PI * freq1 * t_val)
		var v2 := sin(2.0 * PI * freq2 * t_val)
		var value := (v1 * 0.15 + v2 * 0.15) * envelope
		var sample16 := int(clampf(value, -1.0, 1.0) * 32767)
		data.encode_s16(i * 2, sample16)
	var stream := AudioStreamWAV.new()
	stream.data = data
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = int(SAMPLE_RATE)
	stream.stereo = false
	return stream


func _gen_twang(duration: float, start_freq: float, end_freq: float) -> AudioStreamWAV:
	var sample_count := int(SAMPLE_RATE * duration)
	var data := PackedByteArray()
	data.resize(sample_count * 2)
	for i in range(sample_count):
		var t_val: float = float(i) / SAMPLE_RATE
		var progress := float(i) / float(sample_count)
		var envelope := 1.0 - progress
		var freq := lerpf(start_freq, end_freq, progress)
		var value := sin(2.0 * PI * freq * t_val) * 0.25 * envelope
		value += randf_range(-0.03, 0.03) * envelope
		var sample16 := int(clampf(value, -1.0, 1.0) * 32767)
		data.encode_s16(i * 2, sample16)
	var stream := AudioStreamWAV.new()
	stream.data = data
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = int(SAMPLE_RATE)
	stream.stereo = false
	return stream


func _gen_rising_tone(duration: float, start_freq: float, end_freq: float) -> AudioStreamWAV:
	var sample_count := int(SAMPLE_RATE * duration)
	var data := PackedByteArray()
	data.resize(sample_count * 2)
	for i in range(sample_count):
		var t_val: float = float(i) / SAMPLE_RATE
		var progress := float(i) / float(sample_count)
		var envelope := 1.0 - progress
		var freq := lerpf(start_freq, end_freq, progress)
		var value := sin(2.0 * PI * freq * t_val) * 0.2 * envelope
		var sample16 := int(clampf(value, -1.0, 1.0) * 32767)
		data.encode_s16(i * 2, sample16)
	var stream := AudioStreamWAV.new()
	stream.data = data
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = int(SAMPLE_RATE)
	stream.stereo = false
	return stream
