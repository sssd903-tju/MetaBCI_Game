#!/usr/bin/env python3
"""FP1/FP2 前额叶 MI 在线推理 — LSL → Temporal FAA(8d) → SVM-RBF → WebSocket

Usage:
    python fp1fp2_online.py [--port 8767] --model models/fp1fp2_model
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import websockets
from pylsl import StreamInlet, resolve_byprop
from scipy import signal as sig

sys.path.insert(0, str(Path(__file__).parent))
from fp1fp2_classifier import FP1FP2Classifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── 配置 ──
FS = 250.0
FP1_IDX, FP2_IDX = 4, 5
BUFFER_N = 1000  # 4s @ 250Hz
LSL_STREAM = "brain-cube-eeg"

# ── Temporal FAA 特征提取 (8维) ──

def extract_8d(fp1_tk, fp2_tk):
    """Temporal FAA: α/β × 4子窗(500ms) = 8维 (68.6% LOO, 70trial)"""
    from scipy.integrate import trapezoid
    def bp(x, lo, hi):
        nperseg = min(128, len(x)//2)
        if nperseg<32: nperseg=len(x)//4
        if nperseg<16: return 0.0
        f,p=sig.welch(x, FS, nperseg=nperseg)
        m=(f>=lo)&(f<=hi)
        return float(trapezoid(p[m],f[m])) if m.sum()>=2 else 0.0

    feat = []
    seg = 125  # 500ms @ 250Hz
    for (lo, hi) in [(8,13),(13,30)]:  # alpha, beta
        for s in range(4):
            se, ee = s*seg, min((s+1)*seg, len(fp1_tk))
            p1 = bp(fp1_tk[se:ee], lo, hi)
            p2 = bp(fp2_tk[se:ee], lo, hi)
            feat.append((p2-p1)/(p2+p1+1e-15))
    return np.nan_to_num(np.array(feat), nan=0, posinf=0, neginf=0)


def notch_filt(x, fs, freq=50, q=30):
    b, a = sig.iirnotch(freq, q, fs)
    return sig.filtfilt(b, a, x)


def butter_bandpass(x, lo, hi, fs, order=4):
    nyq = 0.5 * fs
    b, a = sig.butter(order, [lo / nyq, hi / nyq], btype="band")
    return sig.filtfilt(b, a, x)


class OnlineProcessor:
    """简化在线处理器：环形缓冲 + trial_start 定时触发分类。

    每个试次:
      1. trial_start → 记录时间
      2. 始终用环形缓冲收集 Fp1/Fp2 数据
      3. trial_start 4 秒后 → 缓冲前 2s=baseline, 后 2s=task → 分类
      4. 只发一次结果
    """

    def __init__(self, clf):
        self.clf = clf
        self.seq = 0
        self.buffer = []  # (fp1, fp2) tuples, 全量环形缓冲

        # 简化协议: trial_start → 等4s → classify (前2s=baseline, 后2s=task)
        self.trial_layer = None
        self.trial_ts = 0.0
        self.trial_done = False
        self._fatigue = 50.0

    def feed(self, fp1, fp2):
        self.buffer.append((fp1, fp2))
        if len(self.buffer) > BUFFER_N:
            self.buffer.pop(0)

    def has_result(self):
        if self.trial_layer is None or self.trial_done:
            return False
        return time.time() - self.trial_ts >= 4.0 and len(self.buffer) >= BUFFER_N

    def classify(self):
        try:
            buf = np.array(self.buffer)
            # 前2s=baseline, 后2s=task
            mid = len(buf) // 2
            bl, tk = buf[:mid], buf[mid:]

            fp1_bl = notch_filt(butter_bandpass(bl[:, 0], 0.5, 45, FS), FS)
            fp2_bl = notch_filt(butter_bandpass(bl[:, 1], 0.5, 45, FS), FS)
            fp1_tk = notch_filt(butter_bandpass(tk[:, 0], 0.5, 45, FS), FS)
            fp2_tk = notch_filt(butter_bandpass(tk[:, 1], 0.5, 45, FS), FS)

            # Z-score 归一化 (与训练一致)
            fp1_bl_c = fp1_bl - np.mean(fp1_bl); fp1_tk_c = fp1_tk - np.mean(fp1_tk)
            fp2_bl_c = fp2_bl - np.mean(fp2_bl); fp2_tk_c = fp2_tk - np.mean(fp2_tk)
            s1 = np.std(np.concatenate([fp1_bl_c, fp1_tk_c]))
            s2 = np.std(np.concatenate([fp2_bl_c, fp2_tk_c]))
            if s1 > 1e-10: fp1_bl_c /= s1; fp1_tk_c /= s1
            if s2 > 1e-10: fp2_bl_c /= s2; fp2_tk_c /= s2

            feat = extract_8d(fp1_tk_c, fp2_tk_c)
            result = self.clf.predict_one(feat)
            self._fatigue = self._compute_fatigue(fp1_tk, fp2_tk)

            self.trial_done = True
            logger.info("layer=%s → %s conf=%.3f fatigue=%.0f",
                         self.trial_layer, result["label"],
                         result["confidence"], self._fatigue)
            return result["label"], result["confidence"]
        except Exception as e:
            logger.error("classify: %s", e)
            self.trial_done = True
            return "rest", 0.0

    def _compute_fatigue(self, fp1_tk, fp2_tk):
        """计算疲劳指数: (θ+α)/β，Fp1/Fp2 均值，映射到 0-100。"""
        # Z-score 先归一化，保证跨设备鲁棒
        s1, s2 = np.std(fp1_tk), np.std(fp2_tk)
        if s1 > 1e-10: fp1_tk = fp1_tk / s1
        if s2 > 1e-10: fp2_tk = fp2_tk / s2

        def bp(x, lo, hi):
            nperseg = min(128, len(x)//2)
            if nperseg<32: nperseg=len(x)//4
            if nperseg<16: return 0.0
            f,p=sig.welch(x, FS, nperseg=nperseg)
            m=(f>=lo)&(f<=hi)
            from scipy.integrate import trapezoid
            return float(trapezoid(p[m],f[m])) if m.sum()>=2 else 0.0

        # (θ+α)/β 比值 → 越高越疲劳
        def ch_f(ch): return (bp(ch,4,8)+bp(ch,8,13))/(bp(ch,13,30)+1e-15)
        raw = (ch_f(fp1_tk)+ch_f(fp2_tk))/2.0

        # 映射到 0-100: 归一化后典型范围 0.8~4.0
        fatigue = max(0, min(100, (raw-0.8)/(4.0-0.8)*100))
        return round(fatigue, 1)

    def compute_fatigue(self):
        """公开接口：从环形缓冲计算实时专注度 (0-100)，无需完整分类。"""
        try:
            buf = np.array(self.buffer)
            if len(buf) < 250:
                return 50.0
            tk = buf[-500:] if len(buf) >= 500 else buf[-250:]
            fp1_tk = notch_filt(butter_bandpass(tk[:, 0], 0.5, 45, FS), FS)
            fp2_tk = notch_filt(butter_bandpass(tk[:, 1], 0.5, 45, FS), FS)
            return self._compute_fatigue(fp1_tk, fp2_tk)
        except Exception:
            return 50.0

    def on_event(self, event):
        if event.get("type") == "trial_start":
            layer = event.get("layer", -1)
            if self.trial_layer == layer and not self.trial_done:
                return
            self.trial_layer = layer
            self.trial_ts = time.time()
            self.trial_done = False
            logger.info("trial_start layer=%s", layer)

    def packet(self, label, conf):
        self.seq += 1
        return json.dumps({
            "seq": self.seq,
            "timestamp_ms": int(time.time() * 1000),
            "label": label,
            "confidence": round(conf, 3),
            "fatigue": getattr(self, "_fatigue", 50.0),
        })


# ── handler ──

async def handle_connection(websocket, proc):
    logger.info("Game connected")
    logger.info("LSL: %s", LSL_STREAM)
    streams = resolve_byprop("name", LSL_STREAM, timeout=10.0)
    if not streams:
        logger.error("LSL stream not found: %s", LSL_STREAM)
        await websocket.send(json.dumps({"label": "rest", "confidence": 0, "seq": 0}))
        await websocket.close()
        return
    inlet = StreamInlet(streams[0])
    info = inlet.info()
    logger.info("LSL ok: %s ch=%d fs=%.0f", info.name(), info.channel_count(),
                 info.nominal_srate())

    proc.seq = 0
    proc.trial_layer = None
    proc.trial_done = True
    last_fatigue_send = 0.0

    try:
        while True:
            chunk, _ = inlet.pull_chunk(timeout=0.05, max_samples=40)
            if chunk:
                for s in chunk:
                    proc.feed(s[FP1_IDX], s[FP2_IDX])

            if proc.has_result():
                label, conf = proc.classify()
                await websocket.send(proc.packet(label, conf))

            # 每秒单独推送专注度
            if time.time() - last_fatigue_send > 1.0 and len(proc.buffer) >= 500:
                last_fatigue_send = time.time()
                f = proc.compute_fatigue()
                proc.seq += 1
                await websocket.send(json.dumps({
                    "type": "fatigue",
                    "seq": proc.seq,
                    "fatigue": f,
                    "timestamp_ms": int(time.time() * 1000),
                }))

            try:
                raw = await asyncio.wait_for(websocket.recv(), timeout=0.005)
                proc.on_event(json.loads(raw))
            except (asyncio.TimeoutError, json.JSONDecodeError):
                pass

            await asyncio.sleep(0.01)

    except websockets.exceptions.ConnectionClosed:
        logger.info("Game disconnected")


# ── CLI ──

def parse_args():
    p = argparse.ArgumentParser(description="FP1/FP2 MI Online Inference")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8767)
    p.add_argument("--stream", default=LSL_STREAM)
    p.add_argument("--model", default="models/fp1fp2_model")
    return p.parse_args()


async def main():
    global LSL_STREAM
    args = parse_args()
    LSL_STREAM = args.stream

    model_dir = Path(__file__).parent / args.model
    clf = FP1FP2Classifier.load(model_dir)
    logger.info("Model: %s (acc=%.0f%%)", clf.clf_type,
                 clf.model_info.get("train_accuracy", 0) * 100)

    proc = OnlineProcessor(clf)

    logger.info("FP1/FP2 MI Server ws://%s:%d | LSL=%s | %s",
                 args.host, args.port, LSL_STREAM, clf.clf_type.upper())
    logger.info("server listening on %s:%d", args.host, args.port)

    async with websockets.serve(
        lambda ws: handle_connection(ws, proc),
        args.host, args.port, max_size=2 ** 20,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
