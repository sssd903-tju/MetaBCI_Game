extends Node
## AudioManager — 全局音频管理器
##
## 管理游戏音效播放，支持内置程序化音效和外部音频文件

const SAMPLE_RATE := 44100.0

# 缓存已生成的音效
var _sound_cache: Dictionary = {}

# 蓄力音效播放器引用
var _charge_player: AudioStreamPlayer = null


func _ready() -> void:
	# 预生成内置音效
	_sound_cache["bow_shoot"] = _gen_bow_shoot()
	_sound_cache["hit_10"] = _gen_hit_bullseye()
	_sound_cache["hit"] = _gen_hit()
	_sound_cache["miss"] = _gen_miss()
	_sound_cache["combo"] = _gen_combo()
	_sound_cache["charge"] = _gen_charge_loop()
	print("[AudioManager] 音效就绪")


## 播放射箭声
func play_bow_shoot() -> void:
	_play_cached("bow_shoot", -6.0)


## 播放命中声 (环数越高音调越高)
func play_hit(ring: int) -> void:
	if ring == 10:
		_play_cached("hit_10", -3.0)
	else:
		# 动态调音高
		var player := _create_player()
		var stream := _gen_hit()
		player.stream = stream
		player.pitch_scale = 0.7 + ring * 0.06
		player.volume_db = -6.0
		_add_and_play(player)


## 播放脱靶声
func play_miss() -> void:
	_play_cached("miss", -6.0)


## 播发连击提示
func play_combo(combo_count: int) -> void:
	var player := _create_player()
	var stream := _gen_combo()
	player.stream = stream
	player.pitch_scale = 0.8 + combo_count * 0.15
	player.volume_db = -4.0
	_add_and_play(player)


## 开始蓄力音效 (循环播放)
func play_charge() -> void:
	if _charge_player:
		stop_charge()
	_charge_player = _create_player()
	_charge_player.stream = _sound_cache["charge"]
	_charge_player.pitch_scale = 0.6
	_charge_player.volume_db = -18.0
	_charge_player.finished.connect(_on_charge_loop_finished)
	add_child(_charge_player)
	_charge_player.play()


func _on_charge_loop_finished() -> void:
	if _charge_player:
		_charge_player.play()  # 重新播放实现循环


## 更新蓄力音高 (progress: 0.0→1.0)
func update_charge(progress: float) -> void:
	if _charge_player:
		_charge_player.pitch_scale = lerpf(0.6, 1.4, clampf(progress, 0.0, 1.0))
		_charge_player.volume_db = lerpf(-18.0, -10.0, clampf(progress, 0.0, 1.0))


## 停止蓄力音效
func stop_charge() -> void:
	if _charge_player:
		_charge_player.stop()
		_charge_player.queue_free()
		_charge_player = null


# --- 内部方法 ---

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


# --- 程序化音效生成 ---

## 射箭声：弓弦释放 + 箭矢飞出
func _gen_bow_shoot() -> AudioStream:
	return _gen_twang(0.25, 800.0, 200.0)


## 命中声 (短促确认音)
func _gen_hit() -> AudioStream:
	return _gen_tone(0.08, 880.0, 0.3)


## 十环声 (双音)
func _gen_hit_bullseye() -> AudioStream:
	return _gen_double_tone(0.15, 880.0, 1320.0)


## 脱靶声 (低沉)
func _gen_miss() -> AudioStream:
	return _gen_tone(0.2, 220.0, 0.2)


## 连击声 (上升音)
func _gen_combo() -> AudioStream:
	return _gen_rising_tone(0.15, 440.0, 880.0)


## 生成单频音
func _gen_tone(duration: float, freq: float, volume: float) -> AudioStreamWAV:
	var sample_count := int(SAMPLE_RATE * duration)
	var data := PackedByteArray()
	data.resize(sample_count * 2)  # 16-bit mono

	for i in range(sample_count):
		var t := float(i) / SAMPLE_RATE
		var envelope := 1.0 - (float(i) / float(sample_count))
		var value := sin(2.0 * PI * freq * t) * volume * envelope
		var sample16 := int(clampf(value, -1.0, 1.0) * 32767)
		data.encode_s16(i * 2, sample16)

	var stream := AudioStreamWAV.new()
	stream.data = data
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = int(SAMPLE_RATE)
	stream.stereo = false
	return stream


## 生成双音 (十环专用)
func _gen_double_tone(duration: float, freq1: float, freq2: float) -> AudioStreamWAV:
	var sample_count := int(SAMPLE_RATE * duration)
	var data := PackedByteArray()
	data.resize(sample_count * 2)

	for i in range(sample_count):
		var t := float(i) / SAMPLE_RATE
		var envelope := 1.0 - (float(i) / float(sample_count))
		var v1 := sin(2.0 * PI * freq1 * t)
		var v2 := sin(2.0 * PI * freq2 * t)
		var value := (v1 * 0.15 + v2 * 0.15) * envelope
		var sample16 := int(clampf(value, -1.0, 1.0) * 32767)
		data.encode_s16(i * 2, sample16)

	var stream := AudioStreamWAV.new()
	stream.data = data
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = int(SAMPLE_RATE)
	stream.stereo = false
	return stream


## 生成滑音 (弓弦声 — 频率下降)
func _gen_twang(duration: float, start_freq: float, end_freq: float) -> AudioStreamWAV:
	var sample_count := int(SAMPLE_RATE * duration)
	var data := PackedByteArray()
	data.resize(sample_count * 2)

	for i in range(sample_count):
		var t := float(i) / SAMPLE_RATE
		var progress := float(i) / float(sample_count)
		var envelope := 1.0 - progress
		var freq := lerpf(start_freq, end_freq, progress)
		# 加一点噪声模拟弦振动
		var value := sin(2.0 * PI * freq * t) * 0.25 * envelope
		value += randf_range(-0.03, 0.03) * envelope
		var sample16 := int(clampf(value, -1.0, 1.0) * 32767)
		data.encode_s16(i * 2, sample16)

	var stream := AudioStreamWAV.new()
	stream.data = data
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = int(SAMPLE_RATE)
	stream.stereo = false
	return stream


## 生成上升音 (连击专用)
func _gen_rising_tone(duration: float, start_freq: float, end_freq: float) -> AudioStreamWAV:
	var sample_count := int(SAMPLE_RATE * duration)
	var data := PackedByteArray()
	data.resize(sample_count * 2)

	for i in range(sample_count):
		var t := float(i) / SAMPLE_RATE
		var progress := float(i) / float(sample_count)
		var envelope := 1.0 - progress
		var freq := lerpf(start_freq, end_freq, progress)
		var value := sin(2.0 * PI * freq * t) * 0.2 * envelope
		var sample16 := int(clampf(value, -1.0, 1.0) * 32767)
		data.encode_s16(i * 2, sample16)

	var stream := AudioStreamWAV.new()
	stream.data = data
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = int(SAMPLE_RATE)
	stream.stereo = false
	return stream


## 生成蓄力循环音 (弓弦摩擦 — 不规则嘎吱声，无持续音)
func _gen_charge_loop() -> AudioStreamWAV:
	var duration := 0.5
	var sample_count := int(SAMPLE_RATE * duration)
	var data := PackedByteArray()
	data.resize(sample_count * 2)

	var rng := RandomNumberGenerator.new()
	rng.seed = 42

	# 预计算摩擦事件 (时间, 强度, 持续帧数)
	var creaks: Array[Dictionary] = []
	var t := 0.0
	while t < duration:
		creaks.append({
			"start": t,
			"duration": rng.randf_range(0.003, 0.015),
			"amp": rng.randf_range(0.15, 0.35),
		})
		t += rng.randf_range(0.02, 0.08)  # 不规则间隔

	for i in range(sample_count):
		var now := float(i) / SAMPLE_RATE
		var value := 0.0

		# 检查是否在摩擦事件中
		for c in creaks:
			var elapsed := now - c.start
			if elapsed >= 0 and elapsed < c.duration:
				# 摩擦噪声 — 带通滤波模拟 (简单粗暴: 白噪 × 衰减包络)
				var env := 1.0 - (elapsed / c.duration)
				value += randf_range(-1.0, 1.0) * c.amp * env
				break

		# 极轻微的底噪 (弓毛持续接触感)
		value += randf_range(-0.01, 0.01)

		var sample16 := int(clampf(value, -1.0, 1.0) * 32767)
		data.encode_s16(i * 2, sample16)

	var stream := AudioStreamWAV.new()
	stream.data = data
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = int(SAMPLE_RATE)
	stream.stereo = false
	return stream
