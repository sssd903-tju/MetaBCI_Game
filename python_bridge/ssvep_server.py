#!/usr/bin/env python3
"""
SSVEP 解码服务器 — 频域分析识别注视目标

算法: 多频段 FFT 功率谱密度分析 (PSDA)
  - 对每个刺激频率, 计算 EEG 在该频率 ±0.3Hz 的功率
  - 信噪比 (SNR) = 目标频率功率 / 邻频平均功率
  - 选择 SNR 最高的频率作为解码结果

用法:
  python ssvep_server.py --simulate          # 模拟模式
  python ssvep_server.py --stream brain-cube-eeg  # 真实EEG

协议 → Godot:
  {"type": "ssvep_result", "frequency": 10.4, "target_index": 2}
  {"type": "eeg_quality", "value": 0.85}
"""

import argparse
import asyncio
import json
import logging
import time
import random
from typing import Optional

import numpy as np
from scipy import signal
import websockets
from websockets.asyncio.server import serve

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SSVEPServer")

# 刺激频率池 (必须与 Godot MoleGrid.FREQ_POOL 一致)
TARGET_FREQS = [8.0, 9.2, 10.4, 11.6, 13.0, 14.4, 15.6]


class SSVEPDecoder:
    """PSDA 频域解码器"""

    def __init__(self, srate: float = 250.0, window_sec: float = 2.0):
        self.srate = srate
        self.window_samples = int(window_sec * srate)
        self._buffer: list[list[float]] = []       # [channel][sample]
        self._last_decode = 0.0
        self._decode_interval = 0.3                  # 300ms 一次解码

    def add_samples(self, chunk: list[list[float]]) -> None:
        """chunk: [[ch1, ch2,...], ...] — 多样本多通道"""
        for sample in chunk:
            self._buffer.append(sample)
        max_len = self.window_samples * 3
        if len(self._buffer) > max_len:
            self._buffer = self._buffer[-max_len:]

    def decode(self, target_freqs: list[float]) -> Optional[dict]:
        """返回 {'frequency': float, 'target_index': int} 或 None"""
        now = time.time()
        if now - self._last_decode < self._decode_interval:
            return None
        if len(self._buffer) < self.window_samples:
            return None
        self._last_decode = now

        # 取最近窗口, 平均通道
        window = np.array(self._buffer[-self.window_samples:], dtype=np.float64)
        eeg = window.mean(axis=1)     # 多通道平均
        eeg = eeg - np.mean(eeg)

        # 功率谱
        freqs, psd = signal.welch(eeg, fs=self.srate, nperseg=min(len(eeg), int(self.srate)))

        # 计算每个目标频率的 SNR
        best_freq = target_freqs[0]
        best_snr = -999.0
        snr_values = {}

        for tf in target_freqs:
            snr = self._snr(freqs, psd, tf)
            snr_values[tf] = snr
            if snr > best_snr:
                best_snr = snr
                best_freq = tf

        # 匹配最近的目标
        best_idx = min(range(len(target_freqs)),
                       key=lambda i: abs(target_freqs[i] - best_freq))

        # 如果所有 SNR 都太低, 认为无有效信号
        if best_snr < 1.5:
            return None

        return {
            "frequency": float(best_freq),
            "target_index": best_idx,
            "snr": round(float(best_snr), 2),
            "all_snr": {str(f): round(float(s), 2) for f, s in snr_values.items()},
        }

    def _snr(self, freqs: np.ndarray, psd: np.ndarray, target: float) -> float:
        """目标频率功率 / 邻频噪声功率"""
        bw = 0.3  # 信号带宽
        nb = 1.0  # 噪声带宽 (邻频范围)

        sig_idx = (freqs >= target - bw) & (freqs <= target + bw)
        noise_idx = ((freqs >= target - nb - bw) & (freqs < target - bw)) | \
                    ((freqs > target + bw) & (freqs <= target + nb + bw))

        sig_power = np.mean(psd[sig_idx]) if sig_idx.any() else 0.0
        noise_power = np.mean(psd[noise_idx]) if noise_idx.any() else 1e-10

        return sig_power / max(noise_power, 1e-10)


class SSEPSimulator:
    """模拟 SSVEP 解码: 70% 命中, 30% 随机"""

    def __init__(self):
        self._last_time = 0.0
        self._interval = 0.3
        self._target = 0

    def set_target(self, index: int) -> None:
        self._target = index

    def decode(self, target_freqs: list[float]) -> Optional[dict]:
        now = time.time()
        if now - self._last_time < self._interval:
            return None
        self._last_time = now

        idx = self._target if random.random() < 0.7 else random.randint(0, len(target_freqs) - 1)
        return {
            "frequency": target_freqs[idx],
            "target_index": idx,
            "snr": round(random.uniform(2.0, 8.0), 2),
        }


class SSVEPServer:
    def __init__(self, host="127.0.0.1", port=8769, simulate=False, stream_name="brain-cube-eeg"):
        self.host = host
        self.port = port
        self.simulate = simulate
        self.stream_name = stream_name
        self._clients = set()
        self._running = False
        self.decoder: Optional[SSVEPDecoder] = None
        self.simulator: Optional[SSEPSimulator] = None
        self._target_freqs = TARGET_FREQS

    async def handler(self, websocket):
        self._clients.add(websocket)
        logger.info(f"Godot 连接: {websocket.remote_address}")
        try:
            async for message in websocket:
                data = json.loads(message)
                t = data.get("type", "")
                if t == "game_event":
                    ev = data.get("event", "")
                    if ev == "mole_shown":
                        idx = data.get("hole_index", 0)
                        if self.simulator:
                            self.simulator.set_target(idx)
                        logger.info(f"地鼠出现: 洞{idx+1} ({self._target_freqs[idx]}Hz)")
                    elif ev == "game_over":
                        logger.info(f"游戏结束, 得分: {data.get('extra', {}).get('score', 0)}")
                elif t == "set_freqs":
                    self._target_freqs = data.get("freqs", TARGET_FREQS)
                    logger.info(f"更新频率列表: {self._target_freqs}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)

    async def broadcast(self, data: dict):
        if not self._clients:
            return
        msg = json.dumps(data)
        for c in list(self._clients):
            try:
                await c.send(msg)
            except Exception:
                self._clients.discard(c)

    async def processing_loop(self):
        logger.info("SSVEP 解码循环启动")
        while self._running:
            try:
                if self.simulate:
                    result = self.simulator.decode(self._target_freqs)
                else:
                    result = self.decoder.decode(self._target_freqs)

                if result:
                    await self.broadcast({
                        "type": "ssvep_result",
                        **result,
                        "timestamp_ms": int(time.time() * 1000),
                    })
            except Exception as e:
                logger.error(f"解码错误: {e}")
            await asyncio.sleep(0.02)

    async def start(self):
        self._running = True
        if self.simulate:
            logger.info("模拟 SSVEP 模式")
            self.simulator = SSEPSimulator()
        else:
            logger.info(f"连接 LSL: {self.stream_name}")
            try:
                from pylsl import resolve_byprop, StreamInlet
                streams = resolve_byprop("name", self.stream_name, timeout=5)
                if not streams:
                    streams = resolve_byprop("type", "EEG", timeout=5)
                if streams:
                    inlet = StreamInlet(streams[0])
                    info = inlet.info()
                    srate = info.nominal_srate()
                    logger.info(f"LSL 就绪: {info.name()}, {srate}Hz, {info.channel_count()}ch")
                    self.decoder = SSVEPDecoder(srate=srate)
                    # 启动 LSL 采集协程
                    asyncio.create_task(self._lsl_reader(inlet))
                else:
                    logger.warning("LSL 未找到, 回退模拟")
                    self.simulate = True
                    self.simulator = SSEPSimulator()
            except ImportError:
                logger.warning("pylsl 未安装, 回退模拟")
                self.simulate = True
                self.simulator = SSEPSimulator()

        async with serve(self.handler, self.host, self.port):
            asyncio.create_task(self.processing_loop())
            logger.info(f"SSVEP 服务器: ws://{self.host}:{self.port}")
            await asyncio.Future()

    async def _lsl_reader(self, inlet):
        """后台读取 LSL 数据"""
        while self._running:
            try:
                chunk, _ = inlet.pull_chunk(timeout=0.1, max_samples=64)
                if chunk and self.decoder:
                    self.decoder.add_samples(chunk)
            except Exception:
                pass
            await asyncio.sleep(0.01)


def main():
    parser = argparse.ArgumentParser(description="SSVEP 解码服务器")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8769)
    parser.add_argument("--stream", default="brain-cube-eeg")
    parser.add_argument("--simulate", action="store_true")
    args = parser.parse_args()

    server = SSVEPServer(host=args.host, port=args.port, simulate=args.simulate, stream_name=args.stream)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("服务器关闭")


if __name__ == "__main__":
    main()
