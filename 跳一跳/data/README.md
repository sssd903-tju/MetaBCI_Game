# 数据目录

## bdf_trials/
BDF 离线采集的训练数据（sessions 10-14），使用 Brain Cube 放大器录制。

| Session | 试次 | 说明 |
|---------|------|------|
| 10 | 40 | session_20260614_103*.jsonl (4 files) |
| 11 | 10 | session_11.jsonl |
| 12 | 10 | session_12.jsonl |
| 13 | 10 | session_13.jsonl |
| 14 | 10 | session_14.jsonl |

**字段说明**（每行一个 JSON）：
- `type`: "trial"
- `trial_id`: 试次序号
- `layer`: 关卡层数 (1-10)
- `ground_truth`: "left" / "right"（正确跳跃方向）
- `correct`: true/false
- `timestamp_trial_start_ms`: Unix 毫秒时间戳

## live_trials/
实时 Brain Cube 串口采集的训练数据（sessions 16, 18），通过 LSL 桥接实时录制。

| Session | 试次 | 说明 |
|---------|------|------|
| 16 | 30 | session_20260614_163*.jsonl (3 files) |
| 18 | 40 | session_20260614_213*.jsonl + 214*.jsonl (4 files) |

## archive/
早期测试数据，仅作参考保留。
