"""双帧格式解析器: BB主帧(20B, 250Hz) + CC辅帧(22B, 25Hz) + BLE兼容"""
from dataclasses import dataclass
import struct
import time


# ── 旧 Sample 类型 (EDF 录制兼容) ─────────────────────────
@dataclass
class Sample:
    timestamp_ms: int = 0
    ch1: int = 0
    ch2: int = 0
    ads1220: int = 0


# BLE 通知 (0xE101, 50Hz, 108B=5samples+传感器)
FMT_BLE_EEG = '<iiiHHI'
BLE_EEG_LEN = 20  # 单sample 20B, 通知含5个sample共100B
# BLE 传感器通知 (0xE201, 25Hz): IR[2LE] + RED[2LE] + HR + SpO2[2LE] + MOTION
FMT_BLE_ECG = '<HHBHB'
BLE_ECG_LEN = 8


# ── 新串口固件 BB 主帧 (250Hz, 20B) ─────────────────────
# BB | CH1[4LE] | CH2[4LE] | ECG[4LE] | bb_seq[2LE] | dd_seq[2LE] | res[2] | 55
@dataclass
class BBSample:
    """BB 主帧 (250Hz): ADS1292 CH1/CH2 + ADS1220 ECG"""
    ch1: int = 0
    ch2: int = 0
    ecg: int = 0        # ADS1220 心电
    bb_seq: int = 0      # ADS1292 序号
    dd_seq: int = 0      # ADS1220 序号


# ── 新串口固件 CC 辅帧 (25Hz, 22B) ─────────────────────
# CC | ACC[6] | GYRO[6] | IR[2LE] | RED[2LE] | HR | SpO2[2LE] | MOTION | 66
@dataclass
class CCSample:
    """CC 辅帧 (25Hz): ACC + GYRO + 血氧 + 心率 + 运动"""
    acc_x: int = 0
    acc_y: int = 0
    acc_z: int = 0
    gyro_x: int = 0
    gyro_y: int = 0
    gyro_z: int = 0
    ir: int = 0          # <<2 恢复后
    red: int = 0         # <<2 恢复后
    hr: int = 0          # 心率 BPM
    spo2: int = 0        # SpO2×100 (9750 = 97.50%)
    motion: int = 0      # 0=静止 1=微动 2=活跃


# BB 帧常量
BB_HEADER, BB_FOOTER = 0xBB, 0x55
BB_LEN = 20
FMT_BB = '<iiiHHH'       # ch1(i32) + ch2(i32) + ecg(i32) + bb_seq(u16) + dd_seq(u16) + res(u16)

# CC 帧常量
CC_HEADER, CC_FOOTER = 0xCC, 0x66
CC_LEN = 22
FMT_CC = '<hhhhhhHHBHB'  # acc_x,y,z (i16×3) + gyro_x,y,z (i16×3) + ir(u16) + red(u16) + hr(u8) + spo2(u16) + motion(u8)

MOTION_LABELS = {0: '静止', 1: '微动', 2: '活跃'}


class FrameParser:
    """统一解析器: 新串口 BB/CC 协议 + 旧 BLE 协议"""

    def __init__(self):
        # BLE 缓冲区 (0xE101 统一)
        self._buf_ble = bytearray()
        # 串口缓冲区 (BB/CC格式)
        self._buf = bytearray()
        # 序列号追踪 (丢帧检测)
        self._last_bb_seq: int | None = None
        self._last_dd_seq: int | None = None
        # 统计
        self.bb_count: int = 0
        self.cc_count: int = 0
        self.bb_lost: int = 0      # BB 累计丢帧
        self.dd_lost: int = 0      # DD 累计丢帧
        self._t0: float = time.time()

    # ── 新串口协议: BB/CC 双帧解析 ────────────────────────
    def feed_uart(self, data: bytes) -> tuple[list[BBSample], list[CCSample]]:
        """喂入串口原始字节流，返回 (bb_samples, cc_samples)"""
        self._buf.extend(data)
        # 防止缓冲区无限增长
        if len(self._buf) > 8192:
            self._buf = self._buf[-4096:]

        bb_out: list[BBSample] = []
        cc_out: list[CCSample] = []
        MIN_LEN = min(BB_LEN, CC_LEN)

        i = 0
        while i <= len(self._buf) - MIN_LEN:
            hdr = self._buf[i]

            # ── 尝试解析 BB 帧 ──
            if hdr == BB_HEADER and i + BB_LEN <= len(self._buf):
                if self._buf[i + BB_LEN - 1] == BB_FOOTER:
                    ch1, ch2, ecg, bb_seq, dd_seq, _ = \
                        struct.unpack_from(FMT_BB, self._buf, i + 1)
                    # 丢帧检测
                    if self._last_bb_seq is not None:
                        gap = (bb_seq - self._last_bb_seq - 1) & 0xFFFF
                        if 0 < gap < 100:
                            self.bb_lost += gap
                    if self._last_dd_seq is not None:
                        gap = (dd_seq - self._last_dd_seq - 1) & 0xFFFF
                        if 0 < gap < 100:
                            self.dd_lost += gap
                    self._last_bb_seq = bb_seq
                    self._last_dd_seq = dd_seq
                    bb_out.append(BBSample(ch1, ch2, ecg, bb_seq, dd_seq))
                    self.bb_count += 1
                    i += BB_LEN
                    continue

            # ── 尝试解析 CC 帧 ──
            if hdr == CC_HEADER and i + CC_LEN <= len(self._buf):
                if self._buf[i + CC_LEN - 1] == CC_FOOTER:
                    (acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z,
                     ir, red, hr, spo2, motion) = \
                        struct.unpack_from(FMT_CC, self._buf, i + 1)
                    # IR/RED 恢复 (>>2 → <<2)
                    ir = ir << 2
                    red = red << 2
                    cc_out.append(CCSample(acc_x, acc_y, acc_z,
                                           gyro_x, gyro_y, gyro_z,
                                           ir, red, hr, spo2, motion))
                    self.cc_count += 1
                    i += CC_LEN
                    continue

            i += 1

        # 裁剪已处理数据
        if i > 0:
            del self._buf[:i]

        return bb_out, cc_out

    # ── 帧率 & 统计 ────────────────────────────────────────
    def rates(self) -> tuple[float, float]:
        """返回 (BB帧率 Hz, CC帧率 Hz)"""
        dt = time.time() - self._t0
        if dt <= 0:
            return 0.0, 0.0
        return self.bb_count / dt, self.cc_count / dt

    def reset_stats(self):
        """重置帧率统计 + 清空缓冲区"""
        self._buf.clear()
        self.bb_count = 0
        self.cc_count = 0
        self.bb_lost = 0
        self.dd_lost = 0
        self._last_bb_seq = None
        self._last_dd_seq = None
        self._t0 = time.time()

    # ── BLE EEG (0xE101, 25Hz降采样, 通知含N个20B帧) ──
    _ble_bb_lost = 0; _ble_dd_lost = 0
    _ble_last_bb = None; _ble_last_dd = None

    def feed_ble_eeg(self, data: bytes) -> list[BBSample]:
        self._buf_ble.extend(data)
        if len(self._buf_ble) > 4096: self._buf_ble.clear(); return []
        out = []
        while len(self._buf_ble) >= BLE_EEG_LEN:
            ch1, ch2, ecg, bb_seq, dd_seq, _ = struct.unpack_from(FMT_BLE_EEG, self._buf_ble, 0)
            # BLE丢帧: 250Hz全量, gap=0正常, gap>0即丢帧
            if self._ble_last_bb is not None:
                g = (bb_seq - self._ble_last_bb - 1) & 0xFFFF
                if 0 < g < 100: self._ble_bb_lost += g
            if self._ble_last_dd is not None:
                g = (dd_seq - self._ble_last_dd - 1) & 0xFFFF
                if 0 < g < 100: self._ble_dd_lost += g
            self._ble_last_bb = bb_seq; self._ble_last_dd = dd_seq
            self.bb_count += 1
            out.append(BBSample(ch1, ch2, ecg, bb_seq, dd_seq))
            del self._buf_ble[:BLE_EEG_LEN]
        return out

    # ── BLE 传感器 (8B) ──────────────────────────────────
    _buf_sen = bytearray()
    def feed_ble_ecg(self, data: bytes) -> list[CCSample]:
        self._buf_sen.extend(data)
        if len(self._buf_sen) > 4096: self._buf_sen.clear(); return []
        out = []
        while len(self._buf_sen) >= BLE_ECG_LEN:
            ir, red, hr, spo2, motion = struct.unpack_from(FMT_BLE_ECG, self._buf_sen, 0)
            out.append(CCSample(ir=ir<<2, red=red<<2, hr=hr, spo2=spo2, motion=motion))
            self.cc_count += 1
            del self._buf_sen[:BLE_ECG_LEN]
        return out
