#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Focus Detection Server — 专注度检测实时服务器

从 LSL 脑电数据流中实时计算专注度指标，通过 WebSocket 推送给 Godot 游戏引擎。

专注度算法:
    focus_ratio = (theta_power + alpha_power) / beta_power

    - theta: 4-8 Hz   (放松/冥想)
    - alpha: 8-13 Hz  (闭眼放松/专注)
    - beta:  13-30 Hz (活跃思考/紧张)

    比值越高 → 越放松/专注
    比值越低 → 越紧张/分心

用法:
    # 真实 EEG 数据
    python focus_server.py --stream brain-cube-eeg --port 8768

    # 模拟数据（无硬件测试）
    python focus_server.py --simulate --port 8768

协议 (WebSocket JSON):
    发送 → Godot:
        {"type": "focus", "ratio": 2.8, "theta": 0.5, "alpha": 0.3, "beta": 0.2, "timestamp_ms": ...}
        {"type": "eeg_quality", "value": 0.85}

    接收 ← Godot:
        {"type": "game_event", "event": "trial_start", ...}
        {"type": "game_state", ...}

Author: MetaBCI Paradigm Platform
"""

import argparse
import asyncio
import json
import math
import time
import logging
import random
from typing import Optional

import numpy as np
from scipy import signal
import websockets
from websockets.asyncio.server import serve

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("FocusServer")


# ============================================================
# Focus Detection Engine
# ============================================================


class FocusDetector:
    """实时专注度检测器

    使用滑动窗口 FFT 计算频带功率，输出 (θ+α)/β 比值。
    """

    def __init__(
        self,
        srate: float = 250.0,
        window_sec: float = 2.0,
        update_interval: float = 0.2,
        theta_band: tuple = (4, 8),
        alpha_band: tuple = (8, 13),
        beta_band: tuple = (13, 30),
    ):
        self.srate = srate
        self.window_samples = int(window_sec * srate)
        self.update_interval = update_interval
        self.theta_band = theta_band
        self.alpha_band = alpha_band
        self.beta_band = beta_band

        # 数据缓冲区
        self._buffer: list[float] = []
        self._last_update = 0.0
        self._last_ratio = 1.5  # 默认值

        # 信号质量追踪
        self._quality = 0.0

        # 基线矫正
        self.baseline_ratio = 2.0
        self._baseline_buffer: list[float] = []
        self._baseline_active = False

    def add_sample(self, value: float) -> None:
        """添加单个样本到缓冲区"""
        self._buffer.append(value)
        # 保持窗口大小
        if len(self._buffer) > self.window_samples * 2:
            self._buffer = self._buffer[-self.window_samples:]

    def add_samples(self, values: list[float]) -> None:
        """批量添加样本"""
        self._buffer.extend(values)
        if len(self._buffer) > self.window_samples * 2:
            self._buffer = self._buffer[-self.window_samples:]

    def get_focus(self) -> Optional[dict]:
        """计算专注度指标

        Returns:
            dict or None: {"ratio", "theta", "alpha", "beta", "quality", "timestamp_ms"}
        """
        now = time.time()
        if now - self._last_update < self.update_interval:
            return None

        if len(self._buffer) < self.window_samples:
            return None

        self._last_update = now

        # 取最近窗口
        window = np.array(self._buffer[-self.window_samples:], dtype=np.float64)
        window = window - np.mean(window)  # 去均值

        # 计算功率谱
        freqs, psd = self._compute_psd(window)

        # 频带功率
        theta_power = self._band_power(freqs, psd, self.theta_band)
        alpha_power = self._band_power(freqs, psd, self.alpha_band)
        beta_power = self._band_power(freqs, psd, self.beta_band)

        # 避免除零
        beta_power = max(beta_power, 1e-10)

        # 专注度比值
        ratio = (theta_power + alpha_power) / beta_power

        # 信号质量评估（基于总功率和信噪比）
        total_power = theta_power + alpha_power + beta_power
        self._quality = min(1.0, total_power / 100.0)  # 启发式阈值

        self._last_ratio = ratio

        self.feed_baseline(ratio)

        # 限制异常值
        ratio = max(0.1, min(10.0, ratio))

        return {
            "type": "focus",
            "ratio": round(float(ratio), 2),
            "pct": self.get_focus_pct(ratio),
            "theta": round(float(theta_power), 4),
            "alpha": round(float(alpha_power), 4),
            "beta": round(float(beta_power), 4),
            "quality": round(self._quality, 3),
            "timestamp_ms": int(now * 1000),
        }

    def start_baseline(self) -> None:
        """开始基线采集"""
        self._baseline_buffer.clear()
        self._baseline_active = True
        logger.info("基线采集开始...")

    def feed_baseline(self, ratio: float) -> None:
        """喂入基线数据点"""
        if self._baseline_active:
            self._baseline_buffer.append(ratio)

    def finish_baseline(self) -> float:
        """结束基线, 返回平均比值"""
        self._baseline_active = False
        if self._baseline_buffer:
            self.baseline_ratio = float(np.mean(self._baseline_buffer))
            logger.info(f"基线矫正完成: {self.baseline_ratio:.2f}")
        return self.baseline_ratio

    def get_focus_pct(self, ratio: float) -> int:
        """将原始比值转换为0-100百分制"""
        if self.baseline_ratio <= 0:
            return 50
        pct = (ratio / self.baseline_ratio) * 50.0
        return max(0, min(100, int(round(pct))))

    def _compute_psd(self, data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """计算功率谱密度 (Welch 方法)"""
        nperseg = min(len(data), int(self.srate))
        freqs, psd = signal.welch(
            data,
            fs=self.srate,
            nperseg=nperseg,
            noverlap=nperseg // 2,
        )
        return freqs, psd

    def _band_power(
        self, freqs: np.ndarray, psd: np.ndarray, band: tuple
    ) -> float:
        """计算指定频带的总功率"""
        low, high = band
        idx = np.where((freqs >= low) & (freqs <= high))[0]
        if len(idx) == 0:
            return 0.0
        return float(np.trapz(psd[idx], freqs[idx]))

    @property
    def quality(self) -> float:
        return self._quality

    @property
    def last_ratio(self) -> float:
        return self._last_ratio


# ============================================================
# LSL Data Source
# ============================================================


class LSLDataSource:
    """LSL 脑电数据源"""

    def __init__(self, stream_name: str = "brain-cube-eeg"):
        self.stream_name = stream_name
        self._inlet = None
        self._srate = 250.0
        self._channel_count = 0

    def connect(self) -> bool:
        """连接到 LSL 流"""
        try:
            from pylsl import resolve_byprop, StreamInlet

            logger.info(f"正在查找 LSL 流: '{self.stream_name}'...")
            streams = resolve_byprop("name", self.stream_name, timeout=5)

            if not streams:
                # 尝试按类型查找
                logger.info("按名称未找到，尝试按类型查找 EEG 流...")
                streams = resolve_byprop("type", "EEG", timeout=5)

            if not streams:
                logger.error("未找到 LSL 流！请确保 EEG 设备已连接并发送数据。")
                return False

            self._inlet = StreamInlet(streams[0])
            info = self._inlet.info()
            self._srate = info.nominal_srate()
            self._channel_count = info.channel_count()

            logger.info(
                f"已连接到 LSL 流: {info.name()}, "
                f"采样率: {self._srate} Hz, "
                f"通道数: {self._channel_count}"
            )
            return True

        except ImportError:
            logger.error("pylsl 未安装。请运行: pip install pylsl")
            return False
        except Exception as e:
            logger.error(f"连接 LSL 失败: {e}")
            return False

    def pull_chunk(self, timeout: float = 0.0) -> Optional[list[list[float]]]:
        """拉取数据块

        Returns:
            list of list or None: [[ch1, ch2, ...], ...]
        """
        if self._inlet is None:
            return None

        try:
            chunk, timestamps = self._inlet.pull_chunk(
                timeout=timeout, max_samples=128
            )
            if chunk and len(chunk) > 0:
                return chunk
        except Exception as e:
            logger.warning(f"LSL 读取错误: {e}")

        return None

    @property
    def srate(self) -> float:
        return self._srate

    @property
    def channel_count(self) -> int:
        return self._channel_count


# ============================================================
# EEG Simulator
# ============================================================


class EEGSimulator:
    """模拟 EEG 数据生成器（用于无硬件测试）

    生成带专注度调制的合成脑电信号，用于测试游戏功能。
    """

    def __init__(self, srate: float = 250.0):
        self.srate = srate
        self._t = 0.0

    def generate_chunk(self, focus_level: float, duration: float = 0.1) -> list[float]:
        """生成一段模拟 EEG 数据

        Args:
            focus_level: 目标专注度水平 [0.0, 4.0]，值越高 alpha/theta 越强
            duration: 数据时长（秒）

        Returns:
            list of float: 模拟 EEG 样本
        """
        n_samples = int(duration * self.srate)
        t = np.linspace(self._t, self._t + duration, n_samples, endpoint=False)
        self._t += duration

        # 基础噪声
        noise = np.random.randn(n_samples) * 5.0

        # alpha 波（专注时增强）
        alpha_amp = 15.0 * (focus_level / 3.0)
        alpha = alpha_amp * np.sin(2 * np.pi * 10.0 * t)

        # theta 波
        theta_amp = 8.0 * (focus_level / 3.0)
        theta = theta_amp * np.sin(2 * np.pi * 6.0 * t)

        # beta 波（紧张时增强，专注时减弱）
        beta_amp = 12.0 * (1.0 - focus_level / 4.0)
        beta = beta_amp * np.sin(2 * np.pi * 20.0 * t)

        # 50Hz 工频干扰（模拟）
        line_noise = 3.0 * np.sin(2 * np.pi * 50.0 * t)

        eeg = noise + alpha + theta + beta + line_noise

        return eeg.tolist()


# ============================================================
# WebSocket Server
# ============================================================


class FocusServer:
    """专注度检测 WebSocket 服务器

    整合 LSL 数据采集（或模拟器）、专注度计算和 WebSocket 通信。
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8768,
        simulate: bool = False,
        stream_name: str = "brain-cube-eeg",
        srate: float = 250.0,
    ):
        self.host = host
        self.port = port
        self.simulate = simulate
        self.stream_name = stream_name
        self.srate = srate

        self._clients: set = set()
        self._running = False
        self._focus_level = 2.0  # 模拟专注度

        # 组件
        self.detector = FocusDetector(srate=srate)
        self.lsl_source: Optional[LSLDataSource] = None
        self.simulator: Optional[EEGSimulator] = None

    # ---- WebSocket 处理 ----

    async def handler(self, websocket):
        """WebSocket 连接处理器"""
        self._clients.add(websocket)
        client_addr = websocket.remote_address
        logger.info(f"Godot 客户端已连接: {client_addr}")

        try:
            async for message in websocket:
                await self._handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"客户端断开: {client_addr}")
        finally:
            self._clients.discard(websocket)

    async def _handle_message(self, websocket, message: str):
        """处理来自 Godot 的消息"""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")

            match msg_type:
                case "game_event":
                    event_name = data.get("event", "")
                    logger.info(f"游戏事件: {event_name} | {data.get('extra', {})}")
                    if event_name == "baseline_start":
                        self.detector.start_baseline()
                    elif event_name == "baseline_done":
                        self.detector.finish_baseline()
                    elif event_name == "game_over":
                        logger.info(
                            f"  分数: {data.get('extra', {}).get('score', 0)}"
                        )

                case "game_state":
                    pass  # 记录状态，暂不处理

                case "set_focus":
                    # 允许手动设置模拟专注度
                    self._focus_level = data.get("value", 2.0)
                    logger.info(f"设置模拟专注度: {self._focus_level}")

                case _:
                    logger.debug(f"未知消息类型: {msg_type}")

        except json.JSONDecodeError:
            logger.warning(f"JSON 解析失败: {message[:100]}")

    async def broadcast(self, data: dict):
        """广播消息到所有已连接客户端"""
        if not self._clients:
            return

        message = json.dumps(data, ensure_ascii=False)
        # 使用 asyncio.gather 并发发送
        tasks = []
        for client in list(self._clients):
            try:
                tasks.append(client.send(message))
            except websockets.exceptions.ConnectionClosed:
                self._clients.discard(client)

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.debug(f"发送失败: {result}")

    # ---- 主循环 ----

    async def processing_loop(self):
        """EEG 数据处理主循环"""
        logger.info("数据处理循环已启动")

        while self._running:
            try:
                if self.simulate:
                    # 模拟模式
                    chunk = self.simulator.generate_chunk(self._focus_level)
                    self.detector.add_samples(chunk)
                else:
                    # 真实 LSL 模式
                    if self.lsl_source is None:
                        await asyncio.sleep(0.5)
                        continue

                    chunk = self.lsl_source.pull_chunk(timeout=0.0)
                    if chunk:
                        # 取第一个通道 (Fp1)
                        channel_data = [sample[0] for sample in chunk]
                        self.detector.add_samples(channel_data)

                # 计算专注度
                result = self.detector.get_focus()
                if result:
                    await self.broadcast(result)

                    # 定期发送信号质量
                    await self.broadcast({
                        "type": "eeg_quality",
                        "value": round(self.detector.quality, 3),
                    })

            except Exception as e:
                logger.error(f"数据处理错误: {e}")

            await asyncio.sleep(0.01)  # ~100Hz 循环

    # ---- 生命周期 ----

    async def start(self):
        """启动服务器"""
        self._running = True

        if self.simulate:
            logger.info("🎮 模拟模式 — 使用合成 EEG 数据")
            self.simulator = EEGSimulator(srate=self.srate)
        else:
            logger.info("🧠 真实模式 — 连接 LSL 脑电数据流")
            self.lsl_source = LSLDataSource(stream_name=self.stream_name)
            if not self.lsl_source.connect():
                logger.warning("LSL 连接失败，回退到模拟模式")
                self.simulate = True
                self.simulator = EEGSimulator(srate=self.srate)
            else:
                self.srate = self.lsl_source.srate
                self.detector = FocusDetector(srate=self.srate)

        # 启动 WebSocket 服务器
        logger.info(f"🌐 WebSocket 服务器: ws://{self.host}:{self.port}")
        async with serve(self.handler, self.host, self.port):
            # 启动数据处理循环
            processing_task = asyncio.create_task(self.processing_loop())

            try:
                await asyncio.Future()  # 永久运行
            except asyncio.CancelledError:
                pass
            finally:
                self._running = False
                processing_task.cancel()
                logger.info("服务器已停止")

    def stop(self):
        """停止服务器"""
        self._running = False


# ============================================================
# CLI
# ============================================================


def main():
    parser = argparse.ArgumentParser(
        description="MetaBCI 专注度检测服务器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python focus_server.py --simulate                    # 模拟模式测试
  python focus_server.py --stream brain-cube-eeg       # 连接真实设备
  python focus_server.py --stream serial-eeg --port 8768
        """,
    )

    parser.add_argument(
        "--host", default="127.0.0.1", help="WebSocket 绑定地址"
    )
    parser.add_argument(
        "--port", type=int, default=8768, help="WebSocket 端口"
    )
    parser.add_argument(
        "--stream", default="brain-cube-eeg", help="LSL 流名称"
    )
    parser.add_argument(
        "--srate", type=float, default=250.0, help="采样率 (Hz)"
    )
    parser.add_argument(
        "--simulate", action="store_true", help="使用模拟 EEG 数据"
    )

    args = parser.parse_args()

    server = FocusServer(
        host=args.host,
        port=args.port,
        simulate=args.simulate,
        stream_name=args.stream,
        srate=args.srate,
    )

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")


if __name__ == "__main__":
    main()
