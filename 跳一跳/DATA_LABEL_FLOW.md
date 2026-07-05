# 跳一跳 — 数据与标签传输逻辑

## 总览

```
┌──────────┐   Serial(44B帧)    ┌─────────────────┐   LSL Stream    ┌──────────────────┐   WebSocket   ┌──────────┐
│ EEG 硬件  │ ─────────────────→ │ 串口→LSL 桥接     │ ──────────────→ │ 在线分类器         │ ────────────→ │ Godot游戏 │
│ (放大器)  │   921600 baud     │ (serial_lsl)     │  4ch 250Hz     │ (LDA / 阈值)      │  port 8767   │ (Game.gd) │
└──────────┘                    └─────────────────┘                 └──────────────────┘               └──────────┘
                                                                                                           │
                                 ┌──────────────────┐   WebSocket                                         │
                                 │ 键盘模拟器         │ ────────────────────────────────────────────────────┘
                                 │ (mi_keyboard)    │   port 8766 (离线模式)
                                 └──────────────────┘
```

---

## 第一层：硬件 → 串口（帧协议）

| 项目 | 值 |
|------|-----|
| 波特率 | 921600 |
| 帧长 | 44 字节 |
| 采样率 | 1000 Hz |
| 通道数 | 4 (CH1/CH2/CH3/CH4) |

**帧结构：**

```
Byte  0      : 0xAA (帧头)
Byte  1- 3   : CH1 INT24 (有符号, big-endian / 高字节在前)
Byte  4- 6   : CH2 INT24
Byte  7- 9   : CH3 INT24
Byte 10-12   : CH4 INT24
Byte 13-29   : 保留 (17字节零)
Byte 30      : 保留
Byte 31      : 序号 (0-255 循环)
Byte 32-41   : 保留 (10字节零)
Byte 42      : 保留
Byte 43      : 0xBB (帧尾)
```

**解析代码：** [eeg_reader_fast.py:35-38](python/eeg_reader_fast.py#L35-L38), [eeg_reader_fast.py:61-77](python/eeg_reader_fast.py#L61-L77)

---

## 第二层：串口 → LSL 桥接

有两套实现，用途不同：

### 2a. `serial_lsl_bridge.py` — 独立桥接脚本

- **输入：** 串口 44B 帧 → 解析 4ch INT24
- **输出：** LSL Stream `"serial-eeg"`, 4ch, 250Hz, int32
- **通道名：** C3, C4, F3, F4
- **MI 电极映射：** C3=左手(左idx=0), C4=右手(右idx=1)
- **验证：** 至少 2 个通道的值在合理范围内（`abs(v) < 8,000,000`）才推送

**代码：** [serial_lsl_bridge.py](python/serial_lsl_bridge.py)

### 2b. `mi_bci_gui.py` — GUI 集成桥接

- **输入：** 同上串口帧
- **输出：** LSL Stream（名称/通道数/采样率可配置，默认 `"serial-eeg"`, 4ch, 250Hz）
- **额外功能：**
  - 信号监视（4通道实时值 + 信号质量条）
  - 录制为 .fif 文件（自动 50Hz 陷波）
  - 串口端口下拉选择

**代码：** [mi_bci_gui.py:498-586](python/mi_bci_gui.py#L498-L586)

---

## 第三层：LSL → 分类 → WebSocket（在线推理）

有三套分类器，按复杂度递增：

### 3a. `lsl_bridge_server.py` — 简易阈值分类（端口 8767）

| 项目 | 值 |
|------|-----|
| LSL 流 | `"brain-cube-eeg"` |
| 采样率 | 250 Hz |
| 窗口 | 1 秒 (250 样本) |
| 频段 | 8-30 Hz (alpha+beta) |
| 电机极 | PO3(idx=0), PO4(idx=6) |
| 阈值 | 左右功率比 > 1.3 |

**分类逻辑：**
1. 累积 250 样本窗口 → 差分方差近似带通功率
2. 计算 `ratio = C3_power / C4_power`
3. `ratio > 1.3` → `"left"`, `ratio < 1/1.3` → `"right"`, 否则 `"rest"`
4. 置信度 = `|log2(ratio)| / 4`, 上限 0.95

**数据包格式：**
```json
{"seq": 1, "timestamp_ms": 1718000000000, "label": "left", "confidence": 0.75}
```

**发送频率：** 每 150ms 一次

**代码：** [lsl_bridge_server.py:55-71](python/lsl_bridge_server.py#L55-L71)

### 3b. `mi_bci_gui.py` 在线服务 — LDA 分类（端口 8767）

| 项目 | 值 |
|------|-----|
| LSL 流 | `"serial-eeg"` |
| 采样率 | 可配置 (250/500/1000) |
| 特征 | 9 维 ERD（宽带 + alpha + beta，各 3 维） |
| 分类器 | LDA（离线训练保存为 JSON） |
| 模式 | **试次驱动**（游戏发 trial_start → baseline+task → 分类） |

**试次协议：**
```
游戏 → Python:  {"type": "trial_start", "layer": N, "ground_truth": "left"}

Python 收到后：
  1. 收集 baseline 窗口 (2s, 500 samples @ 250Hz)
  2. 收集 task 窗口 (2s, 500 samples @ 250Hz)
  3. 50Hz 陷波 → 提取 ERD 特征 → LDA 分类
  4. 发送结果给游戏

Python → 游戏: {"seq": 1, "timestamp_ms": ..., "label": "left", "confidence": 0.82}
```

**代码：** [mi_bci_gui.py:777-889](python/mi_bci_gui.py#L777-L889)

### 3c. `metabci_bridge/main_online.py` — 完整流水线（端口 8767）

与 3b 相同协议，但使用模块化的预处理→特征提取→分类器流水线。

**模块：**
- `preprocess.py` — 50Hz 陷波, 去趋势, CAR 重参考
- `feature_extractor.py` — 9 维 ERD + CSP 支持
- `classifier.py` — LDA 加载/保存/推理

**代码：** [metabci_bridge/main_online.py](python/metabci_bridge/main_online.py)

---

## 第四层：WebSocket → Godot 游戏

### 4a. 连接管理

游戏维护一个 **MI WebSocket**，根据 `MIInputMode` 连接到不同端口：

| MI 输入模式 | 连接地址 | 来源 |
|------------|---------|------|
| OFFLINE | `ws://127.0.0.1:8766` | `mi_keyboard_sender.py`（手动按键） |
| ONLINE  | `ws://127.0.0.1:8767` | 上述任一 LSL 分类器 |

**常量定义：** [Game.gd:53-54](scripts/Game.gd#L53-L54)

### 4b. 数据包接收与校验

收包流程（`_update_mi_bridge` → `_process_mi_packet`）：

```
1. WebSocket.poll() → 读取所有待处理包
2. 每个包 JSON 解析
3. 序号检查 (seq > mi_last_seq)：防乱序
   - 若 seq == 1 且是发端重启，允许（mi_last_seq 重置为 0）
   - 否则丢包（mi_out_of_order_dropped++）
4. TTL 检查 (|now_ms - ts_ms| > 1500ms)：防过期
   - 超时丢包（mi_stale_dropped++）
5. 延迟 EMA 更新
6. 标签规范化 + 置信度阈值 → _process_mi_signal()
```

**关键常量：**

| 常量 | 值 | 说明 |
|------|-----|------|
| `MI_PACKET_TTL_MS` | 1500ms | 数据包过期时间 |
| `MI_HAND_CONF_THRESHOLD` | 0.50 | hand 标签置信度阈值 |
| `MI_FOOT_CONF_THRESHOLD` | 0.50 | foot 标签置信度阈值 |
| `MI_HAND_CONFIRM_COUNT` | 1 | hand 标签需连续确认次数 |
| `MI_FOOT_CONFIRM_COUNT` | 1 | foot 标签需连续确认次数 |
| `MI_RECONNECT_INTERVAL` | 0.75s | WebSocket 重连间隔 |

**代码：** [Game.gd:1036-1089](scripts/Game.gd#L1036-L1089), [Game.gd:1091-1121](scripts/Game.gd#L1091-L1121)

### 4c. 标签映射与决策

`_process_mi_signal(label, confidence)` 的标签映射：

```
输入标签                        → 有效标签 (effective_label)
───────────────────────────────────────────────────────────
"hand" / "left" / "left_hand"  → "hand"  (需 conf ≥ 0.50)
"foot" / "right" / "right_hand" → "foot"  (需 conf ≥ 0.50)
其它                            → "rest"
```

**关卡模式特殊映射**（VERTICAL_TRAIN / VERTICAL_TRAIN_OFFLINE）：
```
"hand" / "left" / "left_hand"  → "left"  (左跳)
"foot" / "right" / "right_hand"→ "right" (右跳)
```

**连续确认（去抖）：**
- 相同 `effective_label` 连续到达 `_mi_needed_count(label)` 次后，才更新 `mi_decision_label`
- 离线模式：1 次即可（立即生效）
- 在线模式：hand/foot 需 `MI_HAND_CONFIRM_COUNT`/`MI_FOOT_CONFIRM_COUNT` 次（当前=1）
- rest：始终 1 次即可

**代码：** [Game.gd:1123-1158](scripts/Game.gd#L1123-L1158)

### 4d. MI 动作状态机

`_poll_mi_action(delta)` 将 `mi_decision_label` 转换为具体游戏动作：

```
当前状态          mi_decision_label   → 动作
────────────────────────────────────────────────────────
IDLE              "hand"              → START_CHARGE (蓄力)
                  其它                → 无动作

CHARGING          "foot"              → RELEASE_JUMP (起跳)
                  "rest"              → 暂停蓄力 (保持)
                  其它                → 不改变

REST_KEEPALIVE    "hand"              → 恢复蓄力
                  超时 0.7s           → CANCEL_CHARGE (取消蓄力)

AIRBORNE          "foot"              → AIR_JUMP (空中二段跳)
                  其它                → 无动作
```

**关卡模式：**
```
mi_decision_label == "left"  → 左跳
mi_decision_label == "right" → 右跳
```

**MI 激活延迟：** hand 触发蓄力需持续保持 0.5s（`MI_HAND_ACTIVATION_DELAY`）

**冷却时间：**

| 冷却项 | 值 |
|--------|-----|
| `MI_ACTION_COOLDOWN` | 0.12s（两次动作间最短间隔） |
| `MI_AIR_JUMP_COOLDOWN` | 0.2s（两次空中跳跃间隔） |

**代码：** [Game.gd:561-616](scripts/Game.gd#L561-L616)

---

## 第五层：游戏 → Python（状态回传）

游戏每 0.1s 向 Python 发送状态：

```json
{
  "type": "mi_status",
  "timestamp_ms": ...,
  "score": 5,
  "airborne": false,
  "charging": true,
  "mi_state": 1,
  "control_mode": 1,
  "mi_input_mode": 1
}
```

**代码：** [Game.gd:1054-1072](scripts/Game.gd#L1054-L1072)

---

## 离线训练模式（VERTICAL_TRAIN_OFFLINE）

### 试次协议（10 秒周期）

```
Phase 0: START     (0-2s)   → 游戏发 {"type": "trial_start", "layer": N, "ground_truth": "left/right"}
Phase 1: MI TASK   (2-6s)   → 游戏发 {"type": "mi_task", ...}
                               Python 收 EEG baseline(2s) + task(2s) → 分类 → 回传 label
Phase 2: JUMP      (6-7s)   → 游戏发 {"type": "trial_jump", "direction": "left/right"}
                               _execute_jump() 按正确方向跳
Phase 3: SCORE     (7-8s)   → 游戏发 {"type": "trial_score", "correct": true/false}
Phase 4: RELAX     (8-10s)  → 游戏发 {"type": "trial_relax", ...}
```

**每个试次的完整数据记录（JSONL）：**

```json
{
  "type": "trial",
  "trial_id": 1,
  "layer": 1,
  "ground_truth": "left",
  "mi_decision": "left",
  "correct": true,
  "timestamp_trial_start_ms": 1718000001000,
  "timestamp_mi_task_ms": 1718000003000,
  "timestamp_jump_ms": 1718000007000,
  "timestamp_score_ms": 1718000008000,
  "timestamp_relax_ms": 1718000009000,
  "timestamp_trial_end_ms": 1718000010000
}
```

**会话结束：**
```json
{
  "type": "session_end",
  "total_trials": 10,
  "trials": [...]
}
```

**代码：** [offline_train_manager.gd](scripts/managers/offline_train_manager.gd), [data_logger.gd](scripts/managers/data_logger.gd)

---

## 手动离线 MI 输入

`mi_keyboard_sender.py` 监听键盘，发送 WebSocket 数据包到端口 8766：

**热键：**
- `h` → `{"label": "hand", "confidence": 0.90}`
- `f` → `{"label": "foot", "confidence": 0.90}`
- `r` → `{"label": "rest", "confidence": 1.0}`
- `+/-` → 调整置信度 ±0.05
- `:h 0.85` 回车 → 设置 hand 置信度为 0.85

**数据包格式（与在线分类器一致）：**
```json
{
  "seq": 1,
  "timestamp_ms": 1718000000000,
  "timestamp_iso": "2026-06-13T21:35:00.000",
  "label": "hand",
  "confidence": 0.90,
  "key": "h",
  "delta_ms": 520
}
```

**代码：** [mi_keyboard_sender.py](python/mi_keyboard_sender.py)

---

## 离线训练（模型生成）

```
BDF/FIF 文件 + JSONL 会话文件
        │
        ▼
┌─────────────────────────────┐
│ 离线训练流水线                │
│ 1. 加载 BDF (mne)           │
│ 2. 加载 JSONL 试次数据       │
│ 3. 时间对齐 (bdf_ms → 秒)   │
│ 4. 切片: baseline(0-2s)     │
│          task(2-4s)         │
│ 5. 提取 9 维 ERD 特征        │
│ 6. 训练 LDA 分类器           │
│ 7. 保存 mi_model.json       │
└─────────────────────────────┘
```

**特征（9 维）：**
```
ERD_T7, ERD_T8, lateral         (宽带 0.5-30Hz)
ERD_a_T7, ERD_a_T8, lateral_a   (alpha 8-13Hz)
ERD_b_T7, ERD_b_T8, lateral_b   (beta 13-30Hz)
```

**标签：** left=1, right=2

**模型文件格式 (mi_model.json)：**
```json
{
  "w": [0.12, -0.34, ...],
  "b": 0.05,
  "classes": [1, 2],
  "feature_names": ["ERD_T7", "ERD_T8", "lateral", ...],
  "n_features": 9
}
```

**代码：** [mi_bci_gui.py:326-415](python/mi_bci_gui.py#L326-L415), [metabci_bridge/offline_train.py](python/metabci_bridge/offline_train.py)

---

## 关键文件索引

| 层级 | 文件 | 功能 |
|------|------|------|
| 硬件 | [eeg_reader_fast.py](python/eeg_reader_fast.py) | 串口读取 + 高速显示 + CSV 记录 |
| 桥接 | [serial_lsl_bridge.py](python/serial_lsl_bridge.py) | 串口→LSL 独立桥接 |
| 桥接 | [mi_bci_gui.py](python/mi_bci_gui.py) | GUI: 串口桥接 + 信号监视 + 录制 + 在线推理 |
| 桥接 | [replay_bdf_lsl.py](python/replay_bdf_lsl.py) | BDF 文件重放为 LSL 流（测试用） |
| 分类 | [lsl_bridge_server.py](python/lsl_bridge_server.py) | 简易阈值分类 (C3/C4 功率比) |
| 分类 | [metabci_bridge/main_online.py](python/metabci_bridge/main_online.py) | 完整 LDA 在线推理 |
| 分类 | [metabci_bridge/main_offline.py](python/metabci_bridge/main_offline.py) | 离线训练 CLI |
| 手动 | [mi_keyboard_sender.py](python/mi_keyboard_sender.py) | 键盘模拟 MI 标签发送 |
| 游戏 | [Game.gd](scripts/Game.gd) | 主游戏逻辑：WS连接、标签处理、MI状态机 |
| 游戏 | [Player.gd](scripts/Player.gd) | 玩家物理：蓄力、跳跃、空中跳跃 |
| 游戏 | [Platform.gd](scripts/Platform.gd) | 平台：普通/移动/脆弱 |
| 游戏 | [offline_train_manager.gd](scripts/managers/offline_train_manager.gd) | 离线训练模式：试次协议、阶段管理 |
| 游戏 | [data_logger.gd](scripts/managers/data_logger.gd) | JSONL 数据记录 |
| 游戏 | [level_mode_manager.gd](scripts/managers/level_mode_manager.gd) | 关卡模式管理 |
