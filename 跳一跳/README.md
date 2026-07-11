# 跳一跳 — 脑机接口神经康复训练游戏

基于 [MetaBCI](https://github.com/TBC-TJU/MetaBCI) 框架的脑机接口神经康复训练游戏。

想象左手/右手运动 → 前额叶 EEG 实时解码 → 游戏角色跳跃 → 闭环神经反馈。

## 特性

- **双模式游戏架构**：关卡模式（MI 实时驱动）+ 离线训练模式（5 阶段标准化试次协议）
- **Temporal FAA 特征**：α/β 频段 × 4 子窗(500ms) FAA 时变特征，49 试次 LOO-CV **79.6%**
- **双硬件支持**：消费级 Fp1/Fp2 头环 (LSL 直连) + 自制 C3/C4/Fp1/Fp2 四通道电路板 (串口)
- **实时专注度检测**：(θ+α)/β 比率，绿/黄/红三色进度条，每秒独立推送
- **一体化 GUI**：实时波形/频谱监视 + 模型训练 + 在线推理

## 架构

本系统基于 **MetaBCI** 框架构建：采用 MetaBCI 的 MI 范式设计模式（运动想象→分类→反馈）、BDF 数据加载（`mne`）和频域分析接口（`FrequencyAnalysis`）。在线推理使用轻量级 scipy 实现以满足实时性要求（端到端 60.8ms）。

```
头环(Fp1/Fp2) → LSL数据流 → 带通+陷波 → Temporal FAA(8d) → SVM-RBF → WebSocket → Godot游戏
  250Hz                     0.5-45Hz    α/β×4子窗FAA    79.6% LOO    8767端口    跳一跳
```

## 快速开始

### 依赖

```bash
pip install numpy scipy mne scikit-learn websockets pylsl pyqtgraph metabci
```

### 启动在线推理

```bash
python python/fp1fp2_online.py --stream brain-cube-eeg --port 8767
# Godot 项目 → 控制=MI, MI输入=Online → 开始游戏
```

### 离线训练

```bash
python python/train_fp1fp2.py \
  --bdf data.bdf \
  --sessions data/bdf_trials/ \
  --output python/models/fp1fp2_model
```

### GUI

```bash
python python/mi_bci_gui.py
```

## 项目结构

```
├── python/
│   ├── fp1fp2_online.py         # 在线推理服务器
│   ├── fp1fp2_classifier.py     # 特征提取 + 分类器
│   ├── train_fp1fp2.py          # 离线训练脚本
│   ├── mi_bci_gui.py            # GUI 界面
│   ├── replay_bdf_lsl.py        # BDF → LSL 回放
│   ├── eeg_reader_fast.py       # EEG 实时波形显示
│   └── models/fp1fp2_model/     # 训练好的模型
├── scripts/                     # Godot GDScript
│   ├── Game.gd                  # 主逻辑
│   ├── Player.gd                # 物理系统
│   └── managers/
│       ├── level_mode_manager.gd       # 关卡模式
│       ├── offline_train_manager.gd    # 离线训练模式
│       └── data_logger.gd             # JSONL 数据记录
├── scenes/                      # Godot 场景
├── data/
│   ├── bdf_trials/              # 离线训练数据 (49 试次)
│   └── live_trials/             # 在线测试数据 (30 试次)
├── PROJECT_INTRO.md             # 项目介绍与创新点
├── DATA_LABEL_FLOW.md           # 数据流完整文档
└── README.md
```

## 分类性能

| 特征 | 维度 | 分类器 | LOO-CV | 在线 |
|------|------|--------|--------|------|
| **Temporal FAA** | **8** | **SVM-RBF** | **79.6%** | **72.0%** |
| Power (log) | 12 | SVM | 67.3% | — |
| FAA+Power | 18 | GB | 65.3% | — |
| FAA | 6 | SVM | 67.3% | — |

> 离线：49 试次 (L=25, R=24)，5 个 session | 在线：50 试次关卡模式

## 专注度

$$Fatigue = \frac{P_\theta + P_\alpha}{P_\beta},\quad Focus = 100 - Fatigue$$

## License

MIT
