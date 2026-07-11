#!/usr/bin/env python3
"""
EEG高速实时显示 — pyqtgraph版本 (流畅运行1000Hz×4通道)
=================================================================
协议: AA + [4CH×3B INT] + 17B零 + 3B序号 + 10B零 + BB  (44字节/帧)
波特率: 921600, 采样率: 1000Hz
"""

import serial
import serial.tools.list_ports
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
from collections import deque
from datetime import datetime
import threading
import time
import argparse
import queue
import math
import sys

# ============================================================
# 协议常量
# ============================================================
FRAME_SIZE = 44
HEADER = 0xAA
TAIL = 0xBB
CH_COUNT = 4
SAMPLE_RATE = 1000

# ============================================================
# 帧解析 (同前)
# ============================================================
def parse_3byte_int(data, offset, signed=True):
    v = (data[offset] << 16) | (data[offset+1] << 8) | data[offset+2]
    if signed and (v & 0x800000):
        v -= 0x1000000
    return v

class FrameParser:
    def __init__(self):
        self.buffer = bytearray()
        self.frame_count = 0
        self.lost_frames = 0
        self.last_seq = -1

    def feed(self, data):
        self.buffer.extend(data)
        frames = []
        while len(self.buffer) >= FRAME_SIZE:
            head_idx = self.buffer.find(HEADER)
            if head_idx < 0:
                self.buffer = self.buffer[-3:]
                break
            if head_idx > 0:
                self.buffer = self.buffer[head_idx:]
            if len(self.buffer) < FRAME_SIZE:
                break
            if self.buffer[FRAME_SIZE - 1] == TAIL:
                payload = self.buffer[1:FRAME_SIZE - 1]
                ch1 = parse_3byte_int(payload, 0)
                ch2 = parse_3byte_int(payload, 3)
                ch3 = parse_3byte_int(payload, 6)
                ch4 = parse_3byte_int(payload, 9)
                seq = payload[31]
                if self.last_seq >= 0:
                    expected = (self.last_seq + 1) & 0xFF
                    if seq != expected:
                        self.lost_frames += (seq - expected) & 0xFF
                self.last_seq = seq
                self.frame_count += 1
                frames.append((ch1, ch2, ch3, ch4, seq))
                self.buffer = self.buffer[FRAME_SIZE:]
            else:
                self.buffer = self.buffer[1:]
        return frames

# ============================================================
# 50Hz陷波
# ============================================================
class NotchFilter:
    """IIR Biquad 50Hz Notch, fs=1000, Q=30"""
    def __init__(self, freq=50.0, fs=1000.0, q=30.0):
        w0 = 2.0 * math.pi * freq / fs
        alpha = math.sin(w0) / (2.0 * q)
        cos_w0 = math.cos(w0)
        a0 = 1.0 + alpha
        self.b = np.array([1.0, -2.0*cos_w0, 1.0]) / a0
        self.a = np.array([1.0, (-2.0*cos_w0)/a0, (1.0-alpha)/a0])
        # 每通道独立状态
        self.x_buf = np.zeros((CH_COUNT, 2))
        self.y_buf = np.zeros((CH_COUNT, 2))

    def apply(self, ch, x0):
        y0 = (self.b[0]*x0 +
              self.b[1]*self.x_buf[ch, 0] + self.b[2]*self.x_buf[ch, 1] -
              self.a[1]*self.y_buf[ch, 0] - self.a[2]*self.y_buf[ch, 1])
        self.x_buf[ch, 1] = self.x_buf[ch, 0]
        self.x_buf[ch, 0] = x0
        self.y_buf[ch, 1] = self.y_buf[ch, 0]
        self.y_buf[ch, 0] = y0
        return y0

    def apply_all(self, values):
        return [self.apply(i, values[i]) for i in range(CH_COUNT)]

# ============================================================
# 数据保存
# ============================================================
class DataLogger:
    def __init__(self, filename=None):
        if filename is None:
            filename = f"eeg_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.file = open(filename, 'w', newline='', encoding='utf-8')
        self.file.write("timestamp,frame_seq,CH1,CH2,CH3,CH4\n")
        self.start_time = time.time()
        self.count = 0
        print(f"[LOG] Saving to: {filename}")

    def write(self, seq, ch1, ch2, ch3, ch4):
        t = time.time() - self.start_time
        self.file.write(f"{t:.6f},{seq},{ch1},{ch2},{ch3},{ch4}\n")
        self.count += 1
        if self.count % 1000 == 0:
            self.file.flush()

    def close(self):
        self.file.flush()
        self.file.close()
        print(f"[LOG] Saved {self.count} frames")

# ============================================================
# 串口读取线程
# ============================================================
class SerialReader(threading.Thread):
    def __init__(self, port, baudrate, parser, data_queue, logger=None):
        super().__init__(daemon=True)
        self.port = port
        self.baudrate = baudrate
        self.parser = parser
        self.data_queue = data_queue
        self.logger = logger
        self.running = False
        self.ser = None

    def run(self):
        self.running = True
        try:
            self.ser = serial.Serial(
                port=self.port, baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE, timeout=0.1
            )
            print(f"[OK] Serial {self.port} opened @ {self.baudrate}")
        except Exception as e:
            print(f"[ERROR] Cannot open {self.port}: {e}")
            self.running = False
            return

        last_status = time.time()
        while self.running:
            try:
                chunk = self.ser.read(self.ser.in_waiting or 1)
            except serial.SerialException:
                print("[ERROR] Serial read error")
                break
            if not chunk:
                continue
            frames = self.parser.feed(chunk)
            for ch1, ch2, ch3, ch4, seq in frames:
                self.data_queue.put((ch1, ch2, ch3, ch4))
                if self.logger:
                    self.logger.write(seq, ch1, ch2, ch3, ch4)

            now = time.time()
            if now - last_status >= 1.0 and self.parser.frame_count > 0:
                loss_rate = self.parser.lost_frames / max(1, self.parser.frame_count) * 100
                print(f"  [{self.parser.frame_count} frames, lost={self.parser.lost_frames} ({loss_rate:.2f}%)]")
                last_status = now

        if self.ser:
            self.ser.close()

    def stop(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()

# ============================================================
# pyqtgraph 高速显示
# ============================================================
class EEGDisplayFast:
    """基于pyqtgraph的4通道EEG实时显示 — 1000Hz丝滑运行"""
    def __init__(self, window_sec=5.0):
        self.window_sec = window_sec
        self.buf_size = int(SAMPLE_RATE * window_sec)
        self.notch = NotchFilter(freq=50.0, fs=SAMPLE_RATE, q=30.0)
        self.notch_enabled = True

        # 环形缓冲区
        self.times = deque(maxlen=self.buf_size)
        self.data = [deque(maxlen=self.buf_size) for _ in range(CH_COUNT)]
        self.t_counter = 0

        # FFT缓冲区 (2秒)
        self.fft_size = SAMPLE_RATE * 2
        self.fft_raw = deque(maxlen=self.fft_size)
        self.fft_filt = deque(maxlen=self.fft_size)

        # 数据队列
        self.data_queue = queue.Queue()
        self.start_time = time.time()

        # --- 构建界面 ---
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        self.win = pg.GraphicsLayoutWidget(title='EEG Real-time Monitor — 4CH + CH4 FFT (pyqtgraph)')
        self.win.resize(1400, 900)

        ch_names = ['CH1', 'CH2', 'CH3', 'CH4 (10Hz Target)']
        colors = ['#2196F3', '#4CAF50', '#FF9800', '#F44336']

        # 4个时域图
        self.plots = []
        self.curves = []
        for i in range(CH_COUNT):
            p = self.win.addPlot(row=i, col=0, title=ch_names[i])
            p.showGrid(x=True, y=True, alpha=0.3)
            p.setLabel('left', '')
            p.setLabel('bottom', 'Time (s)' if i == CH_COUNT - 1 else '')
            p.setXRange(0, self.window_sec)
            p.enableAutoRange('y', True)
            curve = p.plot(pen=pg.mkPen(color=colors[i], width=1))
            self.plots.append(p)
            self.curves.append(curve)

        # 下一行: FFT
        self.win.nextRow()
        self.fft_plot = self.win.addPlot(row=CH_COUNT, col=0, title='CH4 Spectrum (0-50Hz)')
        self.fft_plot.showGrid(x=True, y=True, alpha=0.3)
        self.fft_plot.setLabel('bottom', 'Frequency (Hz)')
        self.fft_plot.setXRange(0, 50)
        self.fft_plot.setYRange(0, 100)
        self.fft_raw_curve = self.fft_plot.plot(pen=pg.mkPen(color='#999999', width=1, alpha=120),
                                                 name='Raw')
        self.fft_filt_curve = self.fft_plot.plot(pen=pg.mkPen(color='#F44336', width=1.5),
                                                  name='Filtered')
        # 标记线
        self.fft_plot.addItem(pg.InfiniteLine(pos=10, angle=90,
                                              pen=pg.mkPen('g', width=1, style=QtCore.Qt.DashLine)))
        self.fft_plot.addItem(pg.InfiniteLine(pos=50, angle=90,
                                              pen=pg.mkPen(color='orange', width=1, style=QtCore.Qt.DotLine)))

        # 状态标签
        self.status_label = self.win.addLabel('', row=CH_COUNT+1, col=0)
        self.status_label.setMaximumHeight(25)

        self.win.show()

        # 定时器: 30ms = ~33fps刷新显示
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._update)
        self.timer.start(30)

        # FFT更新计数器
        self.fft_update_counter = 0
        self.peak_freq_10hz = 0
        self.peak_mag_10hz = 0

        # 键盘: N切换陷波
        self.win.keyPressEvent = self._on_key

    def _on_key(self, event):
        if event.key() == QtCore.Qt.Key_N:
            self.notch_enabled = not self.notch_enabled
            print(f"  [KEY] 50Hz Notch: {'ON' if self.notch_enabled else 'OFF'}")

    def add_data(self, ch1, ch2, ch3, ch4):
        self.data_queue.put((ch1, ch2, ch3, ch4))

    def _process_queue(self):
        """从队列取数据 + 陷波滤波"""
        while not self.data_queue.empty():
            try:
                raw = self.data_queue.get_nowait()
            except queue.Empty:
                break

            self.fft_raw.append(raw[3])

            if self.notch_enabled:
                ch1, ch2, ch3, ch4 = self.notch.apply_all(raw)
            else:
                ch1, ch2, ch3, ch4 = raw

            t = self.t_counter / SAMPLE_RATE
            self.t_counter += 1
            self.times.append(t)
            self.data[0].append(ch1)
            self.data[1].append(ch2)
            self.data[2].append(ch3)
            self.data[3].append(ch4)
            self.fft_filt.append(ch4)

    def _update(self):
        """定时刷新显示 (30ms一次, 非阻塞)"""
        self._process_queue()

        if len(self.times) < 2:
            return

        times = np.array(self.times)

        # === 时域更新 (降采样到~1000点保证性能) ===
        n = len(times)
        stride = max(1, n // 1000)
        idx = slice(0, n, stride)

        for i in range(CH_COUNT):
            d = np.array(self.data[i])
            self.curves[i].setData(times[idx], d[idx])

        # 滚动X轴
        t_max = max(self.window_sec, times[-1] + 0.1)
        t_min = t_max - self.window_sec
        for p in self.plots:
            p.setXRange(t_min, t_max)

        # === FFT更新 (每15帧一次, ~0.5秒) ===
        self.fft_update_counter += 1
        if self.fft_update_counter >= 15 and len(self.fft_filt) >= 256:
            self.fft_update_counter = 0

            # 滤波后
            fft_arr = np.array(self.fft_filt) - np.mean(self.fft_filt)
            window = np.hanning(len(fft_arr))
            fft_f = np.abs(np.fft.rfft(fft_arr * window))
            freqs = np.fft.rfftfreq(len(fft_arr), d=1.0/SAMPLE_RATE)
            mask = freqs <= 50
            self.fft_filt_curve.setData(freqs[mask], fft_f[mask])

            # 原始
            if len(self.fft_raw) >= 256:
                fft_raw_arr = np.array(self.fft_raw) - np.mean(self.fft_raw)
                fft_r = np.abs(np.fft.rfft(fft_raw_arr * window))
                self.fft_raw_curve.setData(freqs[mask], fft_r[mask])

            # 追踪10Hz
            peak_mask = (freqs >= 8) & (freqs <= 12)
            if np.any(peak_mask) and len(fft_f[peak_mask]) > 0:
                idx = np.argmax(fft_f[peak_mask])
                self.peak_freq_10hz = freqs[peak_mask][idx]
                self.peak_mag_10hz = fft_f[peak_mask][idx]

        # === 状态文字 ===
        elapsed = time.time() - self.start_time
        ch1_val = self.data[0][-1] if self.data[0] else 0
        notch_s = "ON" if self.notch_enabled else "OFF"
        status = (f"Time: {elapsed:.1f}s | Frames: {self.t_counter} | "
                  f"CH1: {ch1_val:+d} | "
                  f"50Hz Notch: [{notch_s}] (N) | "
                  f"10Hz: {self.peak_freq_10hz:.1f}Hz mag={self.peak_mag_10hz:.0f}")
        self.status_label.setText(status)

    def run(self):
        """启动Qt事件循环"""
        self.app.exec_()


# ============================================================
# 主程序
# ============================================================
def list_ports():
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No serial ports detected!")
        return []
    print("Available ports:")
    for p in ports:
        print(f"  {p.device} - {p.description}")
    return [p.device for p in ports]

def main():
    pg.setConfigOptions(antialias=True)

    parser = argparse.ArgumentParser(description='EEG Serial Acquisition — pyqtgraph')
    parser.add_argument('-p', '--port', default='COM3')
    parser.add_argument('-b', '--baudrate', type=int, default=921600)
    parser.add_argument('-l', '--list', action='store_true')
    parser.add_argument('-s', '--save', action='store_true')
    parser.add_argument('-w', '--window', type=float, default=5.0)
    parser.add_argument('--no-notch', action='store_true')
    parser.add_argument('--sim', action='store_true', help='Use simulator (no serial)')
    args = parser.parse_args()

    if args.list:
        list_ports()
        return

    print(f"EEG Serial Acquisition (pyqtgraph)")
    print(f"=" * 50)
    print(f"Port: {'SIMULATOR' if args.sim else args.port}")
    print(f"Baud: {args.baudrate}")
    print(f"Frame: {FRAME_SIZE} bytes | Rate: {SAMPLE_RATE} Hz | Channels: {CH_COUNT}")
    print(f"50Hz Notch: {'OFF' if args.no_notch else 'ON'}")
    print(f"=" * 50)

    frame_parser = FrameParser()
    logger = DataLogger() if args.save else None
    display = EEGDisplayFast(window_sec=args.window)

    if args.no_notch:
        display.notch_enabled = False

    if args.sim:
        # 模拟器模式
        from serial_simulator import generate_signal, build_frame
        print("[INFO] Running in simulator mode")

        t_sim, c1, c2, c3, c4 = generate_signal(30.0)

        def sim_thread():
            seq = 0
            for i in range(len(t_sim)):
                if not display.win.isVisible():
                    break
                display.add_data(c1[i], c2[i], c3[i], c4[i])
                time.sleep(0.001)  # 1ms = 1000Hz
                seq = (seq + 1) & 0xFF
            print("[SIM] Done")

        sim_t = threading.Thread(target=sim_thread, daemon=True)
        sim_t.start()
    else:
        # 串口模式
        reader = SerialReader(args.port, args.baudrate, frame_parser,
                              display.data_queue, logger)
        reader.start()

    display.run()

    # 清理
    if not args.sim:
        reader.stop()
    if logger:
        logger.close()
    print(f"\n[INFO] Done. Frames: {frame_parser.frame_count}, lost: {frame_parser.lost_frames}")


if __name__ == '__main__':
    # 检查依赖
    try:
        import pyqtgraph
    except ImportError:
        print("pyqtgraph not installed. Install with:")
        print("  pip install pyqtgraph PyQt5")
        print()
        print("Or use the matplotlib version: py eeg_reader.py")
        sys.exit(1)

    main()
