# -*- coding: utf-8 -*-
"""
MetaBCI brainflow.ProcessWorker 子类 — 桥接 LiveWorker 处理管线到标准 ProcessWorker 接口

使用示例 (无 GUI 模式):
    from metabci.brainviz.brainflow_worker import BrainflowWorker

    worker = BrainflowWorker(buffer, name="ssvep_worker")
    worker.start()       # 启动子进程: pre() → 循环 consume() → post()
    worker.put(data)     # 从主进程推送 EEG 数据
    worker.stop()        # 停止
"""

import numpy as np
from metabci.brainflow.workers import ProcessWorker
from metabci.brainviz.live_worker import LiveWorker


class BrainflowWorker(ProcessWorker):
    """brainflow.ProcessWorker 子类 — 封装 LiveWorker 的处理管线

    遵循 ProcessWorker 的标准 pre/consume/post 模式，在独立子进程中运行，
    通过 multiprocessing.Queue 接收主进程推送的 EEG 数据。
    """

    def __init__(self, buffer=None, srate: float = 250.0, n_channels: int = 8,
                 timeout: float = 1e-3, name: str = None):
        super().__init__(timeout=timeout, name=name)
        self._buffer = buffer
        self._srate = srate
        self._n_channels = n_channels
        self._processor = None  # LiveWorker 实例 (子进程中创建)

    def pre(self):
        """[brainflow] 初始化处理管线"""
        # 在子进程中创建 LiveWorker (不启动 QThread, 直接调用其方法)
        if self._buffer is None:
            from metabci.brainviz.data_buffer import EEGBuffer
            self._buffer = EEGBuffer(n_channels=self._n_channels, srate=self._srate)

        # 使用 LiveWorker 的处理方法 (不启动 QThread)
        self._processor = LiveWorker(self._buffer)
        self._processor.pre()  # 加载模板与基线

    def consume(self, data: np.ndarray):
        """[brainflow] 处理单试次 EEG 数据

        Args:
            data: shape (n_channels, n_samples)
        """
        if self._processor:
            self._processor.consume(data)

    def post(self):
        """[brainflow] 清理"""
        if self._processor:
            self._processor.post()
        self._processor = None
