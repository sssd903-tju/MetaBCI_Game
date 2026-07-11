extends Control
class_name PlatformMinimap

var layout_rows: Array = []
var active_stage: int = -1

func clear_layout() -> void:
	layout_rows.clear()
	active_stage = -1
	queue_redraw()

func set_layout(rows: Array) -> void:
	layout_rows = rows.duplicate(true)
	queue_redraw()

func set_stage(stage_index: int) -> void:
	active_stage = stage_index
	queue_redraw()

func _draw() -> void:
	var rect: Rect2 = Rect2(Vector2.ZERO, size)
	draw_rect(rect, Color(0.95, 0.93, 0.86, 0.82), true)
	draw_rect(rect, Color(0.27, 0.43, 0.32, 0.95), false, 2.0)

	if layout_rows.is_empty():
		return

	var min_x: float = INF
	var max_x: float = -INF
	var min_y: float = INF
	var max_y: float = -INF
	for row_variant: Variant in layout_rows:
		if not (row_variant is Dictionary):
			continue
		var row: Dictionary = row_variant
		var row_y: float = float(row.get("y", 0.0))
		min_y = min(min_y, row_y)
		max_y = max(max_y, row_y)
		var platforms: Array = row.get("platforms", [])
		for platform_variant: Variant in platforms:
			if not (platform_variant is Dictionary):
				continue
			var platform: Dictionary = platform_variant
			var platform_x: float = float(platform.get("x", 0.0))
			var platform_width: float = float(platform.get("width", 0.0))
			min_x = min(min_x, platform_x - platform_width * 0.5)
			max_x = max(max_x, platform_x + platform_width * 0.5)

	if not is_finite(min_x) or not is_finite(max_x) or not is_finite(min_y) or not is_finite(max_y):
		return

	var padding_x: float = 10.0
	var padding_y: float = 10.0
	var map_width: float = max(1.0, size.x - padding_x * 2.0)
	var map_height: float = max(1.0, size.y - padding_y * 2.0)
	var world_width: float = max(1.0, max_x - min_x)
	var world_height: float = max(1.0, max_y - min_y)
	var scale_x: float = map_width / world_width
	var scale_y: float = map_height / world_height
	var scale: float = min(scale_x, scale_y)
	var offset_x: float = (size.x - world_width * scale) * 0.5
	var offset_y: float = (size.y - world_height * scale) * 0.5

	for row_index: int in range(layout_rows.size()):
		var row_data: Dictionary = layout_rows[row_index]
		var row_y: float = float(row_data.get("y", 0.0))
		var row_screen_y: float = offset_y + (row_y - min_y) * scale
		var is_active_row: bool = row_index == active_stage
		var row_line_color: Color = Color(0.30, 0.44, 0.32, 0.22)
		if is_active_row:
			row_line_color = Color(0.15, 0.38, 0.24, 0.44)
		draw_line(Vector2(offset_x, row_screen_y), Vector2(size.x - offset_x, row_screen_y), row_line_color, 1.0)

		var platforms: Array = row_data.get("platforms", [])
		for platform_variant: Variant in platforms:
			if not (platform_variant is Dictionary):
				continue
			var platform: Dictionary = platform_variant
			var platform_x: float = float(platform.get("x", 0.0))
			var platform_width: float = float(platform.get("width", 0.0))
			var platform_left: float = offset_x + (platform_x - platform_width * 0.5 - min_x) * scale
			var platform_top: float = row_screen_y - 6.0
			var platform_size: Vector2 = Vector2(max(8.0, platform_width * scale), 12.0)
			var is_treasure: bool = bool(platform.get("treasure", false))
			var color: Color = Color(0.39, 0.58, 0.41, 0.96)
			if is_treasure:
				color = Color(0.74, 0.43, 0.16, 0.98)
			draw_rect(Rect2(Vector2(platform_left, platform_top), platform_size), color, true)
			draw_rect(Rect2(Vector2(platform_left, platform_top), platform_size), Color(0.21, 0.30, 0.21, 0.55), false, 1.0)
			if is_treasure:
				var chest_center: Vector2 = Vector2(platform_left + platform_size.x * 0.5, platform_top - 5.0)
				draw_rect(Rect2(chest_center - Vector2(5.0, 4.0), Vector2(10.0, 8.0)), Color(0.95, 0.81, 0.25, 0.98), true)
				draw_rect(Rect2(chest_center - Vector2(8.0, 6.0), Vector2(16.0, 4.0)), Color(0.92, 0.66, 0.22, 0.98), true)

	if active_stage >= 0 and active_stage < layout_rows.size():
		var active_row: Dictionary = layout_rows[active_stage]
		var active_y: float = offset_y + (float(active_row.get("y", 0.0)) - min_y) * scale
		draw_rect(Rect2(Vector2(offset_x - 4.0, active_y - 10.0), Vector2(size.x - offset_x * 2.0 + 8.0, 20.0)), Color(0.97, 0.84, 0.28, 0.16), true)
