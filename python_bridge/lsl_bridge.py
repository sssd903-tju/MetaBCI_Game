#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LSL Bridge — MetaBCI Brainflow → WebSocket → Godot

将 MetaBCI brainflow 模块采集的 EEG 数据通过 LSL 转发，
同时提供 WebSocket 接口供 Godot 游戏引擎连接。

这个脚本可以配合 MetaBCI 的 brainflow 模块使用：
  1. MetaBCI brainflow 将 EEG 数据推送到 LSL 流
  2. 本脚本从 LSL 流读取数据，计算专注度
  3. 通过 WebSocket 推送到 Godot

或者直接作为演示/测试用途独立运行。

用法:
    # 连接已有 LSL 流
    python lsl_bridge.py --stream meta-eeg --port 8768

    # 模拟模式
    python lsl_bridge.py --simulate
"""

import asyncio
import sys
import os

# 确保可以导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from focus_server import FocusServer, main as focus_main


if __name__ == "__main__":
    focus_main()
