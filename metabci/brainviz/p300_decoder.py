# -*- coding: utf-8 -*-
"""
[MetaBCI] P300 解码器 — ERP 分段叠加 + 模板匹配

P300 是事件相关电位 (ERP)，在目标刺激出现后约 300ms 出现正波。
通过多次闪烁叠加平均，提取 P300 成分，实现目标检测。

用于: 卡牌读心游戏 — 6 张牌随机闪烁，检测用户默想的目标牌
"""

import logging
import numpy as np
from collections import defaultdict

logger = logging.getLogger("brainviz.p300")

# P300 典型时间窗: 刺激前 200ms → 刺激后 800ms
PRE_STIM_MS = 200
POST_STIM_MS = 800


class P300Decoder:
    """[MetaBCI] 在线 P300 解码器

    工作流程:
      1. 每次闪牌 → add_flash(card_index) 记录时间点
      2. 扫描完成 → classify() 用累积的 EEG 片段做分类
      3. 返回最可能的目标牌索引

    算法: 叠加平均 → P300 振幅检测 → 最大振幅的牌 = 目标
    """

    def __init__(self, srate: float = 250.0, n_channels: int = 2):
        self.srate = srate
        self.n_channels = n_channels
        # 每个牌的 EEG 片段缓存
        self._segments: dict[int, list] = defaultdict(list)
        self._flash_count: dict[int, int] = defaultdict(int)
        # 上次分类结果
        self._last_result: int = -1
        self._last_confidence: float = 0.0
        # 数据就绪标志
        self.ready = False

    @property
    def pre_samples(self) -> int:
        return int(PRE_STIM_MS / 1000.0 * self.srate)

    @property
    def post_samples(self) -> int:
        return int(POST_STIM_MS / 1000.0 * self.srate)

    @property
    def segment_len(self) -> int:
        return self.pre_samples + self.post_samples

    def add_flash(self, card_index: int, eeg_snapshot: np.ndarray):
        """记录一次闪牌事件的 EEG 片段

        Args:
            card_index: 闪牌的索引 (0-5)
            eeg_snapshot: 当前 EEG 数据 (n_channels, segment_len)
                          应包含 [刺激前200ms, 刺激后800ms]
        """
        if eeg_snapshot.shape[-1] < self.segment_len:
            return
        segment = eeg_snapshot[..., -self.segment_len:].copy()
        # 基线校正 (用刺激前数据)
        baseline = segment[..., :self.pre_samples].mean(axis=-1, keepdims=True)
        segment = segment - baseline
        self._segments[card_index].append(segment)
        self._flash_count[card_index] += 1
        self.ready = True

    def classify(self) -> tuple[int, float]:
        """分类: 返回最可能的目标牌索引和置信度

        算法: 对每个牌叠加平均 EEG 段，在 P300 窗口 (250-500ms) 内找最大振幅
        """
        if not self._segments:
            return -1, 0.0

        p300_start = int(250 / 1000.0 * self.srate)  # 250ms
        p300_end = int(500 / 1000.0 * self.srate)    # 500ms

        scores = {}
        for card_idx, segs in self._segments.items():
            if len(segs) < 2:
                continue
            # 叠加平均
            avg = np.mean(segs, axis=0)  # (n_channels, segment_len)
            # 多通道平均
            if avg.ndim > 1:
                avg = avg.mean(axis=0)  # (segment_len,)
            # P300 窗口内的峰值振幅
            window = avg[self.pre_samples + p300_start:self.pre_samples + p300_end]
            if len(window) > 0:
                scores[card_idx] = float(np.max(np.abs(window)))
            else:
                scores[card_idx] = 0.0

        if not scores:
            return -1, 0.0

        best_idx = max(scores, key=scores.get)
        best_score = scores[best_idx]
        total_score = sum(scores.values()) or 1e-10
        confidence = best_score / total_score if total_score > 0 else 0.0

        self._last_result = best_idx
        self._last_confidence = confidence
        logger.info(f"P300 分类: 目标牌={best_idx}, 置信度={confidence:.2f}, "
                     f"闪牌次数={dict(self._flash_count)}")
        return best_idx, confidence

    def reset(self):
        """重置，准备下一次扫描"""
        self._segments.clear()
        self._flash_count.clear()
        self.ready = False

    def get_flash_stats(self) -> dict:
        """获取当前扫描的闪牌统计"""
        return dict(self._flash_count)
