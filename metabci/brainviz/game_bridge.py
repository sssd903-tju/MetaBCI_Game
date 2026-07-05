# -*- coding: utf-8 -*-
"""
GameBridge — WebSocket 桥接服务器 [MetaBCI]

将 LiveWorker 的 BCI 解码结果实时推送到 Godot 游戏引擎。
协议兼容现有 Godot BCIConnector autoload (ws://127.0.0.1:8768)。

协议 (JSON):
  发送 → Godot:
    {"type": "focus", "ratio": 2.8, "pct": 65, "theta": 0.5, "alpha": 0.3, "beta": 0.2}
    {"type": "ssvep_result", "frequency": 10.0, "target_index": 1, "snr": 3.5}
    {"type": "p300_result", "target_index": 2, "confidence": 0.85}
    {"type": "mi_result", "direction": "left", "confidence": 0.72}
    {"type": "eeg_quality", "value": 0.85}

  接收 ← Godot:
    {"type": "game_event", "event": "baseline_start", ...}
    {"type": "game_state", "score": 42, ...}

架构:
  LiveWorker (QThread) → GameBridge.broadcast() → asyncio WebSocket → Godot BCIConnector
"""

import asyncio
import json
import logging
import queue
import threading

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("brainviz.bridge")

# 与 Godot GlobalConfig.BCI_WS_URL 保持一致
DEFAULT_PORT = 8768
DEFAULT_HOST = "127.0.0.1"

# SSVEP 频率 → 目标索引 — 与 Godot 游戏严格对齐
# 思维贪吃蛇 (ssvep_arrows.gd): ↑8Hz=0 ←15Hz=1 (仅2方向)
# 打地鼠 (mole_grid.gd): 8.0=0 9.2=1 10.4=2 11.6=3 13.0=4 14.4=5 15.6=6
SSVEP_FREQ_MAP = {
    8.0: 0, 15.0: 1,                               # 贪吃蛇方向
    9.2: 2, 10.4: 3, 11.6: 4, 13.0: 5, 14.4: 6, 15.6: 7,  # 打地鼠扩展
}

# 两种游戏的频率集合
SNAKE_FREQS = [8.0, 15.0]
MOLE_FREQS = [8.0, 15.0]


def _check_focus_baseline() -> bool:
    """检查是否有专注度基线校准文件"""
    import os as _os
    return _os.path.exists(
        _os.path.expanduser("~/MetaBCI_Calibration/focus_baseline.json")
    )


class GameBridge(QObject):
    """[MetaBCI] WebSocket 桥接 — BCI 解码 → Godot 游戏引擎

    在后台线程运行 asyncio 事件循环，通过线程安全队列实现跨线程广播。
    """

    # ── Qt Signals (UI 线程监听) ──
    client_connected = Signal(str)       # 客户端地址
    client_disconnected = Signal(str)    # 客户端地址
    server_started = Signal(int)         # 端口号
    server_stopped = Signal()            # 服务器停止
    game_event = Signal(str, object)     # 事件名, 原始数据

    def __init__(self, port: int = DEFAULT_PORT, host: str = DEFAULT_HOST, parent=None):
        super().__init__(parent)
        self._port = port
        self._host = host
        self._running = False
        self._ready = threading.Event()  # 服务器就绪信号
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._clients: set = set()
        self._outgoing: queue.Queue = queue.Queue()

    # ── 属性 ──

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def client_count(self) -> int:
        return len(self._clients)

    # ── 生命周期 ──

    def start(self):
        """启动 WebSocket 服务器（后台守护线程），阻塞直到服务器就绪"""
        if self._running:
            return
        self._ready.clear()
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True,
                                        name="GameBridge-AsyncIO")
        self._thread.start()
        # 等待服务器就绪 (最多 3 秒)
        if not self._ready.wait(timeout=3.0):
            logger.warning("GameBridge 启动超时")

    def stop(self):
        """停止服务器（优雅关闭）"""
        self._ready.clear()
        self._running = False  # 导致 _serve 的 while 循环退出，协程自然返回
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self.server_stopped.emit()
        logger.info("GameBridge 已停止")

    # ── 线程安全广播 ──

    def broadcast(self, data: dict):
        """线程安全广播 JSON 消息到所有已连接的 Godot 客户端

        可从任何线程调用 —— 消息放入队列，由 asyncio 循环异步发送。

        Args:
            data: 将序列化为 JSON 的字典，需包含 "type" 字段
        """
        if not self._running:
            return
        self._outgoing.put(data)

    # ═══════════════════════════════════════════════════════════
    # 内部实现
    # ═══════════════════════════════════════════════════════════

    def _run_loop(self):
        """后台线程入口 — 创建并运行 asyncio 事件循环"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        except Exception as e:
            logger.error(f"GameBridge 崩溃: {e}")
            self.server_stopped.emit()

    async def _serve(self):
        """启动 WebSocket 服务器，处理客户端连接和出站消息"""
        try:
            from websockets.asyncio.server import serve
            async with serve(self._handler, self._host, self._port,
                             ping_interval=5, ping_timeout=10) as server:
                self.server_started.emit(self._port)
                self._ready.set()  # 通知等待线程
                addr = f"ws://{self._host}:{self._port}"
                logger.info(f"🌐 GameBridge 已启动: {addr}")
                # 主循环 — 处理出站消息队列
                while self._running:
                    await self._flush_outgoing()
                    await asyncio.sleep(0.01)
        except OSError as e:
            logger.error(f"GameBridge 端口 {self._port} 被占用: {e}")
            self.server_stopped.emit()
        except ImportError:
            logger.error("websockets 未安装，请运行: pip install websockets")
            self.server_stopped.emit()

    async def _handler(self, websocket):
        """WebSocket 客户端连接处理器"""
        addr = str(websocket.remote_address)
        self._clients.add(websocket)
        self.client_connected.emit(addr)
        logger.info(f"🎮 Godot 客户端已连接: {addr} (在线: {len(self._clients)})")

        # 发送初始化消息（含基线状态，让游戏决定是否跳过内置基线）
        try:
            init_msg = json.dumps({
                "type": "init",
                "has_baseline": _check_focus_baseline(),
            }, ensure_ascii=False)
            await websocket.send(init_msg)
        except Exception:
            pass

        try:
            from websockets.exceptions import ConnectionClosed
            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type", "")
                    if msg_type == "game_event":
                        evt = data.get("event", "")
                        self.game_event.emit(evt, data)
                        logger.info(f"📨 游戏事件: {evt}")
                    elif msg_type == "game_state":
                        pass  # 暂不处理游戏状态
                except json.JSONDecodeError:
                    logger.debug(f"JSON 解析失败: {message[:80]}")
        except ConnectionClosed:
            logger.info(f"客户端断开: {addr}")
        except Exception as e:
            logger.warning(f"WebSocket 错误: {e}")
        finally:
            self._clients.discard(websocket)
            self.client_disconnected.emit(addr)
            logger.info(f"🎮 客户端离开: {addr} (在线: {len(self._clients)})")

    async def _flush_outgoing(self):
        """处理出站队列中的所有消息"""
        if not self._clients:
            # 没有客户端连接时，清空队列避免堆积
            while not self._outgoing.empty():
                try:
                    self._outgoing.get_nowait()
                except queue.Empty:
                    break
            return

        # 收集本批消息
        msgs = []
        while not self._outgoing.empty():
            try:
                msgs.append(self._outgoing.get_nowait())
            except queue.Empty:
                break

        if not msgs:
            return

        # 取最后一条（最新数据），丢弃中间堆积的旧数据
        # 脑电实时推送只需要最新值
        latest_by_type: dict[str, dict] = {}
        for m in msgs:
            latest_by_type[m.get("type", "unknown")] = m

        # 发送
        from websockets.exceptions import ConnectionClosed
        dead = set()
        for data in latest_by_type.values():
            text = json.dumps(data, ensure_ascii=False)
            for ws in list(self._clients):
                try:
                    await ws.send(text)
                except ConnectionClosed:
                    dead.add(ws)
                except Exception as e:
                    logger.debug(f"发送失败: {e}")
                    dead.add(ws)
        self._clients -= dead
