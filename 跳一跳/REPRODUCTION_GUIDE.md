# 复现指南 — 脑机接口神经康复训练游戏

## 你需要什么

### 硬件
| 设备 | 用途 | 替代方案 |
|------|------|---------|
| Brain Cube 8ch EEG 放大器 | 采集 Fp1/Fp2 脑电 | 任何支持 LSL 的 EEG 设备 |
| Fp1/Fp2 干电极头环 | 前额叶信号采集 | C3/C4 电极帽（需改代码中通道索引） |
| macOS / Linux / Windows PC | 运行 Godot + Python | — |

> **无需硬件也能跑**：项目自带训练数据（49 试次离线 + 30 试次在线），可直接验证分类算法。游戏可用键盘模拟 MI 输入（见步骤 4）。

### 软件
- Python 3.10+  
- Godot 4.x（[godotengine.org](https://godotengine.org) 下载，免费）
- Git（克隆仓库）

## 1 克隆项目

```bash
git clone https://github.com/sssd903-tju/MI_-.git
cd MI_-
```

## 2 安装 Python 依赖

```bash
pip install numpy scipy mne scikit-learn websockets pylsl pyqtgraph
```

## 3 复现分类算法（无需 EEG 硬件）

```bash
cd 项目数据与验证程序/验证脚本
python 01_train_and_validate.py
```

预期输出：
```
SVM-rbf: 79.6%  L_recall=88%  R_recall=71%
theta FAA: p=0.018 *
```

## 4 启动游戏（键盘模拟 MI）

### 4.1 打开 Godot 项目

1. 启动 Godot 4.x → 导入 → 选择 `project.godot`
2. 点击运行（F5）

### 4.2 游戏设置

- **控制**: MI
- **MI输入**: Online
- **模式**: 关卡模式

### 4.3 此时游戏会尝试连接 ws://127.0.0.1:8767，但没有服务器

两种方式让游戏动起来：

**方式 A：Python 在线推理（需 EEG 硬件）**
```bash
python python/fp1fp2_online.py --stream brain-cube-eeg --port 8767
```

**方式 B：键盘直接控制（无需 EEG）**

在 Godot 编辑器中，`Game.gd` 第 732 行，取消手动模式的注释：
```gdscript
# 游戏设置改为: 控制=Manual，用空格键蓄力跳跃
```

## 5 连接真实 EEG 硬件

### 5.1 确认 LSL 流

```bash
python -c "from pylsl import resolve_streams; [print(s.name()) for s in resolve_streams()]"
```

应看到 `brain-cube-eeg`（头环）或 `serial-eeg`（电路板）。

### 5.2 启动在线推理

```bash
python python/fp1fp2_online.py \
  --stream brain-cube-eeg \
  --port 8767 \
  --model python/models/fp1fp2_model
```

### 5.3 开始游戏

Godot → 控制=MI, MI输入=Online, 模式=关卡模式 → 开始

## 6 用自己的数据训练模型

### 6.1 采集数据

游戏 → **离线训练模式** → 完成一轮（10层，约2分钟）→ 数据自动保存到 `user://training_data/`

### 6.2 导出 BDF

Brain Cube 自带 BDF 录制功能，或使用 `mi_bci_gui.py` 的录制功能。

### 6.3 训练

```bash
python python/train_fp1fp2.py \
  --bdf 你的数据.bdf \
  --sessions 你的JSONL目录/ \
  --output python/models/fp1fp2_model
```

## 7 项目结构速查

```
├── python/
│   ├── fp1fp2_online.py      # 在线推理 (启动这个)
│   ├── train_fp1fp2.py       # 离线训练
│   └── models/fp1fp2_model/  # 79.6% LOO 模型
├── data/                     # 训练数据样例
├── README.md                 # 项目说明
├── DATA_LABEL_FLOW.md        # 数据流文档
└── 项目数据与验证程序/        # 独立复现包
```

## 常见问题

**Q: 没有 EEG 硬件能体验游戏吗？**
A: 可以。Godot 中把控制模式改为 Manual，用空格键玩。或者用 BDF 回放模拟 EEG 流：
```bash
python python/replay_bdf_lsl.py 你的数据.bdf
# 另开终端启动在线推理（步骤 5.2）
```

**Q: 我的 EEG 设备通道顺序不同怎么办？**
A: 修改 `fp1fp2_online.py` 第 34 行的 `FP1_IDX, FP2_IDX`。

**Q: LSL 流名不同怎么办？**
A: 加 `--stream` 参数：`python fp1fp2_online.py --stream 你的流名`

**Q: 模型准确率低怎么办？**
A: (1) 检查电极接触阻抗 (2) 增加试次数量至 50+ (3) 确保被试在执行 MI 时保持专注 (4) 用 Temporal FAA(8d) 替代静态 FAA
