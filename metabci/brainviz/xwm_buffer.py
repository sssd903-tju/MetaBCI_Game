"""多通道环形缓冲区 — 支持可变采样率"""
import numpy as np


class RingBuffer:
    """通用多通道环形缓冲区，按采样率生成时间戳。

    用法:
        bb_buf = RingBuffer(3000, n_channels=3, sample_rate=250)  # CH1, CH2, ECG
        cc_buf = RingBuffer(750,  n_channels=2, sample_rate=25)   # IR, RED
        bb_buf.push([ch1_val, ch2_val, ecg_val])
        ts, ch0, ch1, ch2 = bb_buf.get_recent(1250)
    """

    def __init__(self, capacity=30000, n_channels=3, sample_rate=250):
        self._cap = capacity
        self._n_ch = n_channels
        self._sr = sample_rate
        self._ts = np.zeros(capacity, dtype=np.float64)
        self._data = [np.zeros(capacity, dtype=np.float64) for _ in range(n_channels)]
        self._head = 0
        self._dirty = False

    @property
    def sample_rate(self) -> int:
        return self._sr

    def push(self, values: list[float], ts_ms: int = 0):
        i = self._head % self._cap
        self._ts[i] = ts_ms / 1000.0 if ts_ms else self._head / self._sr
        for ch in range(min(len(values), self._n_ch)):
            self._data[ch][i] = float(values[ch])
        self._head += 1
        self._dirty = True

    def get_recent(self, n: int):
        """返回 (ts, ch0, ch1, ...) — 最近 n 个样本"""
        n = min(n, self._cap, self._head)
        if n == 0:
            empty = np.array([], dtype=np.float64)
            return (empty, *[empty.copy() for _ in range(self._n_ch)])
        start = self._head - n
        lo = start % self._cap
        hi = (start + n) % self._cap

        if lo < hi:
            ts = self._ts[lo:hi].copy()
            arrays = [self._data[ch][lo:hi].copy() for ch in range(self._n_ch)]
        else:
            first = self._cap - lo

            def _join(arr):
                out = np.empty(n, dtype=np.float64)
                out[:first] = arr[lo:]
                out[first:] = arr[:hi]
                return out

            ts = _join(self._ts)
            arrays = [_join(self._data[ch]) for ch in range(self._n_ch)]
        return (ts, *arrays)

    def latest_time(self) -> float:
        """最新样本的绝对时间（秒）"""
        if self._head == 0:
            return 0.0
        return self._ts[(self._head - 1) % self._cap]

    def is_dirty(self) -> bool:
        return self._dirty

    def mark_clean(self):
        self._dirty = False

    def reset(self, sample_rate: int = None):
        """清空数据，可选切换采样率"""
        if sample_rate is not None:
            self._sr = sample_rate
        self._head = 0
        self._dirty = False
        self._ts.fill(0)
        for arr in self._data:
            arr.fill(0)

    def __len__(self):
        return min(self._head, self._cap)
