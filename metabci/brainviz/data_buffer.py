# -*- coding: utf-8 -*-
"""
环形数据缓冲区 — 多通道 EEG 数据存储

参照 metabci.brainflow 数据流模式，提供高效的多通道缓冲。
"""

from collections import deque
import numpy as np
from metabci.brainviz.config import LSL_BUFFER_SECONDS


class EEGBuffer:
    """多通道环形缓冲区"""

    def __init__(self, n_channels: int = 8, srate: float = 250.0):
        self.n_channels = n_channels
        self.srate = srate
        maxlen = int(LSL_BUFFER_SECONDS * srate)
        self._channels: list[deque] = [deque(maxlen=maxlen) for _ in range(n_channels)]
        self._timestamps: deque = deque(maxlen=maxlen)
        self._t0: float | None = None

    def push(self, samples: list[list[float]], timestamps: list[float] | None = None):
        """推入批量样本 [[ch1,ch2,...], ...]"""
        import time
        for i, sample in enumerate(samples):
            if timestamps and i < len(timestamps):
                ts = timestamps[i]
            else:
                ts = time.time()
            if self._t0 is None:
                self._t0 = ts
            self._timestamps.append(ts)
            for ch in range(min(len(sample), self.n_channels)):
                self._channels[ch].append(sample[ch])

    def get_channel(self, ch: int) -> np.ndarray:
        return np.array(self._channels[ch], dtype=np.float64)

    def get_time(self) -> np.ndarray:
        if not self._timestamps:
            return np.array([])
        return np.array(self._timestamps) - (self._t0 or 0.0)

    def get_recent(self, ch: int, seconds: float) -> tuple[np.ndarray, np.ndarray]:
        n = int(seconds * self.srate)
        data = self.get_channel(ch)[-n:]
        time = self.get_time()[-n:]
        return time, data

    @property
    def duration(self) -> float:
        return len(self._timestamps) / self.srate if self.srate else 0.0

    @property
    def sample_count(self) -> int:
        return len(self._timestamps)

    def clear(self):
        for ch in self._channels:
            ch.clear()
        self._timestamps.clear()
        self._t0 = None
