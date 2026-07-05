#!/usr/bin/env python3
"""MI BCI 训练与在线推理 — 图形界面

功能:
  离线训练: 导入 BDF + JSONL → 清洗 → 特征提取 → 训练 LDA → 保存模型
  在线推理: 检测 LSL 流 → 连接 → 实时分类 → WebSocket 发包给游戏

依赖: numpy, scipy, mne, pylsl, websockets, metabci
"""

import json
import queue
import sys
import threading
import time
import tkinter as tk
from datetime import timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import mne
import numpy as np
from scipy import signal as sig

# Add project path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Constants ──
FS = 250.0
T7_IDX, T8_IDX = 4, 5
FEATURE_NAMES = [
    "ERD_T7", "ERD_T8", "lateral",
    "ERD_a_T7", "ERD_a_T8", "lateral_a",
    "ERD_b_T7", "ERD_b_T8", "lateral_b",
]
DEFAULT_MODEL_DIR = Path(__file__).parent / "models"
DEFAULT_MODEL = DEFAULT_MODEL_DIR / "mi_model.json"

# ── Core functions (copied from metabci_bridge) ──

def notch_filter(data, fs=1000, freq=50, q=30):
    """Apply notch filter to 2D array (n_ch, n_samples)."""
    from scipy import signal as sig
    b, a = sig.iirnotch(freq, q, fs)
    out = np.zeros_like(data)
    for ch in range(data.shape[0]):
        out[ch] = sig.filtfilt(b, a, data[ch])
    return out


def band_power(x, fs, low, high):
    n = min(128, len(x) // 2)
    if n < 32: n = len(x) // 4
    f, p = sig.welch(x, fs, nperseg=n)
    mask = (f >= low) & (f <= high)
    if mask.sum() < 2: return 0.0
    return float(np.trapezoid(p[mask], f[mask]))


def extract_erd_features(bl, tk, left_idx=T7_IDX, right_idx=T8_IDX, fs=1000):
    """Extract 9 ERD features from baseline+task windows."""
    def erd(c_bl, c_tk, lo, hi):
        a = band_power(c_bl, fs, lo, hi)
        b = band_power(c_tk, fs, lo, hi)
        return (b - a) / (a + 1e-15)

    bl_l = bl[left_idx] - bl[left_idx].mean()
    bl_r = bl[right_idx] - bl[right_idx].mean()
    tk_l = tk[left_idx] - tk[left_idx].mean()
    tk_r = tk[right_idx] - tk[right_idx].mean()

    e7 = erd(bl_l, tk_l, 0.5, 30); e8 = erd(bl_r, tk_r, 0.5, 30)
    a7 = erd(bl_l, tk_l, 8, 13);   a8 = erd(bl_r, tk_r, 8, 13)
    b7 = erd(bl_l, tk_l, 13, 30);  b8 = erd(bl_r, tk_r, 13, 30)

    return np.array([e7, e8, e7-e8, a7, a8, a7-a8, b7, b8, b7-b8])


def train_lda(X, y):
    """Train LDA with proper bias centering."""
    from scipy import linalg
    classes = np.unique(y)
    if len(classes) < 2:
        raise ValueError(f"需要两类标签 (left+right)，当前只有 {len(classes)} 类: {classes.tolist()}")
    c0, c1 = classes[0], classes[1]
    X0, X1 = X[y == c0], X[y == c1]
    mu0, mu1 = X0.mean(0), X1.mean(0)
    cov = (len(X0)*np.cov(X0, rowvar=False) + len(X1)*np.cov(X1, rowvar=False)) / len(X)
    cov += 1e-6 * np.eye(X.shape[1])
    w = linalg.solve(cov, mu1 - mu0, assume_a="pos")
    b = -(mu0 + mu1).dot(w) / 2.0
    return w, b, classes


# ── GUI Application ──

class MIBciApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MI BCI — 运动想象训练与在线推理")
        self.root.geometry("800x680")
        self.root.resizable(True, True)

        # State
        self.bdf_path = tk.StringVar()
        self.session_path = tk.StringVar()
        self.model_path = tk.StringVar(value=str(DEFAULT_MODEL))
        self.session_name = tk.StringVar()
        self.save_dir = tk.StringVar(value=str(Path.home() / "Desktop"))
        self.status = tk.StringVar(value="就绪")
        self.lsl_status = tk.StringVar(value="未检测")
        self.lsl_stream_name = tk.StringVar(value="serial-eeg")
        self.lsl_channels = tk.StringVar(value="4")
        self.lsl_fs = tk.StringVar(value="250")
        self.lsl_left_idx = tk.StringVar(value="0")   # C3
        self.lsl_right_idx = tk.StringVar(value="1")  # C4
        self.ws_status = tk.StringVar(value="未连接")
        self.classify_label = tk.StringVar(value="--")
        self.accuracy_var = tk.StringVar(value="--")
        self.n_trials_var = tk.StringVar(value="--")

        self._w = None
        self._b = 0.0
        self._classes = None
        self._online_running = False
        self._online_thread = None

        # FP1/FP2 classifier
        self.fp1fp2_model_path = tk.StringVar(
            value=str(Path(__file__).parent / "models" / "fp1fp2_model"))
        self.classifier_type = tk.StringVar(value="lda")  # "lda" | "svm_fp1fp2" | "rf_fp1fp2"
        self._fp1fp2_clf = None

        self._build_ui()
        self._try_load_model()

    # ── UI ──

    def _build_ui(self):
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=5, pady=5)

        offline_frame = ttk.Frame(nb)
        online_frame = ttk.Frame(nb)
        nb.add(offline_frame, text="离线训练")
        nb.add(online_frame, text="在线推理")

        self._build_offline_tab(offline_frame)
        self._build_online_tab(online_frame)

        # Status bar
        sb = ttk.Frame(self.root)
        sb.pack(fill="x", padx=5, pady=2)
        ttk.Label(sb, textvariable=self.status).pack(side="left")
        ttk.Label(sb, text="模型: ").pack(side="right")
        ttk.Label(sb, textvariable=self.accuracy_var, width=12).pack(side="right")
        ttk.Label(sb, text="试次: ").pack(side="right")
        ttk.Label(sb, textvariable=self.n_trials_var, width=6).pack(side="right")

    def _build_offline_tab(self, parent):
        # File selection
        frm = ttk.LabelFrame(parent, text="数据文件", padding=10)
        frm.pack(fill="x", padx=5, pady=5)

        ttk.Label(frm, text="FIF/BDF 文件:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.bdf_path, width=60).grid(row=0, column=1, padx=5)
        ttk.Button(frm, text="浏览...", command=self._browse_bdf).grid(row=0, column=2)

        ttk.Label(frm, text="会话 JSONL:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(frm, textvariable=self.session_path, width=60).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(frm, text="浏览...", command=self._browse_session).grid(row=1, column=2, pady=5)

        # Model save
        frm2 = ttk.LabelFrame(parent, text="模型保存", padding=10)
        frm2.pack(fill="x", padx=5, pady=5)

        ttk.Label(frm2, text="模型路径:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm2, textvariable=self.model_path, width=60).grid(row=0, column=1, padx=5)
        ttk.Button(frm2, text="浏览...", command=self._browse_model_save).grid(row=0, column=2)

        # Train button + results
        frm3 = ttk.Frame(parent)
        frm3.pack(fill="x", padx=5, pady=10)
        ttk.Button(frm3, text="开始训练 (LDA)", command=self._run_training, width=20).pack(side="left", padx=10)
        ttk.Button(frm3, text="训练 FP1/FP2 SVM", command=self._run_fp1fp2_training, width=20).pack(side="left", padx=10)
        ttk.Label(frm3, text="准确率:").pack(side="left", padx=(20, 5))
        ttk.Label(frm3, textvariable=self.accuracy_var, font=("", 14, "bold"), foreground="green").pack(side="left")
        ttk.Label(frm3, text="试次:").pack(side="left", padx=(20, 5))
        ttk.Label(frm3, textvariable=self.n_trials_var, font=("", 14, "bold")).pack(side="left")

        # Log area
        frm4 = ttk.LabelFrame(parent, text="训练日志", padding=5)
        frm4.pack(fill="both", expand=True, padx=5, pady=5)
        self.train_log = tk.Text(frm4, height=10, wrap="word")
        self.train_log.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(self.train_log); scroll.pack(side="right", fill="y")
        self.train_log.config(yscrollcommand=scroll.set); scroll.config(command=self.train_log.yview)

    def _build_online_tab(self, parent):
        # Progressbar styles for signal quality
        style = ttk.Style()
        for color in ["green", "gold", "red"]:
            style.configure(f"{color}.Horizontal.TProgressbar",
                            troughcolor="#e0e0e0", background=color)

        # Model selector
        frm0 = ttk.LabelFrame(parent, text="分类模型", padding=10)
        frm0.pack(fill="x", padx=5, pady=5)
        self.model_combo = ttk.Combobox(frm0, state="readonly", width=50)
        self.model_combo.pack(side="left", padx=5)
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_selected)
        ttk.Button(frm0, text="刷新列表", command=self._refresh_model_list).pack(side="left", padx=5)
        ttk.Button(frm0, text="加载选中模型", command=self._load_selected_model).pack(side="left", padx=5)
        ttk.Label(frm0, textvariable=self.accuracy_var, width=8, font=("", 12, "bold"), foreground="green").pack(side="right", padx=5)
        ttk.Label(frm0, textvariable=self.n_trials_var, width=6).pack(side="right", padx=5)
        self._refresh_model_list()

        # Classifier type selector (NEW)
        frm_clf = ttk.LabelFrame(parent, text="分类器类型 (FP1/FP2 头环)", padding=10)
        frm_clf.pack(fill="x", padx=5, pady=5)
        ttk.Label(frm_clf, text="分类器:").pack(side="left")
        self.clf_type_combo = ttk.Combobox(frm_clf, textvariable=self.classifier_type,
                                           values=["lda", "svm_fp1fp2", "rf_fp1fp2"],
                                           state="readonly", width=18)
        self.clf_type_combo.pack(side="left", padx=5)
        self.clf_type_combo.bind("<<ComboboxSelected>>", self._on_clf_type_selected)
        ttk.Label(frm_clf, text="模型路径:").pack(side="left", padx=(15, 0))
        ttk.Entry(frm_clf, textvariable=self.fp1fp2_model_path, width=35).pack(side="left", padx=5)
        ttk.Button(frm_clf, text="浏览...", command=self._browse_fp1fp2_model).pack(side="left")
        self.clf_type_label = ttk.Label(frm_clf, text="", width=20)
        self.clf_type_label.pack(side="left", padx=10)

        # Serial bridge
        frm_ser = ttk.LabelFrame(parent, text="串口 → LSL 桥接", padding=10)
        frm_ser.pack(fill="x", padx=5, pady=5)
        ttk.Label(frm_ser, text="串口:").grid(row=0, column=0, sticky="w")
        self.serial_port_var = tk.StringVar(value="/dev/cu.usbserial-1130")
        self.serial_combo = ttk.Combobox(frm_ser, textvariable=self.serial_port_var, width=25)
        self.serial_combo.grid(row=0, column=1, padx=5)
        ttk.Button(frm_ser, text="刷新", command=self._refresh_serial_ports).grid(row=0, column=2)
        ttk.Label(frm_ser, text="波特率:").grid(row=0, column=3, padx=(10,0))
        self.serial_baud_var = tk.StringVar(value="921600")
        ttk.Entry(frm_ser, textvariable=self.serial_baud_var, width=8).grid(row=0, column=4, padx=5)
        self.serial_btn = ttk.Button(frm_ser, text="启动串口桥接", command=self._toggle_serial_bridge, width=14)
        self.serial_btn.grid(row=0, column=5, padx=10)
        self.serial_status_var = tk.StringVar(value="未启动")
        ttk.Label(frm_ser, textvariable=self.serial_status_var, width=25).grid(row=0, column=6, padx=5)
        self._refresh_serial_ports()

        # LSL / channel config
        frm = ttk.LabelFrame(parent, text="LSL & 通道配置", padding=10)
        frm.pack(fill="x", padx=5, pady=5)
        ttk.Label(frm, text="流名称:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.lsl_stream_name, width=16).grid(row=0, column=1, padx=5)
        ttk.Label(frm, text="通道数:").grid(row=0, column=2, padx=(10,0))
        ttk.Entry(frm, textvariable=self.lsl_channels, width=4).grid(row=0, column=3, padx=5)
        ttk.Label(frm, text="采样率:").grid(row=0, column=4, padx=(10,0))
        self.fs_combo = ttk.Combobox(frm, textvariable=self.lsl_fs, width=8,
                                      values=["250", "500", "1000", "2000"], state="readonly")
        self.fs_combo.grid(row=0, column=5, padx=5)
        ttk.Label(frm, text="左idx:").grid(row=0, column=6, padx=(10,0))
        ttk.Entry(frm, textvariable=self.lsl_left_idx, width=4).grid(row=0, column=7, padx=5)
        ttk.Label(frm, text="右电极idx:").grid(row=0, column=8, padx=(5,0))
        ttk.Entry(frm, textvariable=self.lsl_right_idx, width=4).grid(row=0, column=9, padx=5)
        ttk.Button(frm, text="检测", command=self._detect_lsl).grid(row=0, column=10, padx=10)
        ttk.Label(frm, textvariable=self.lsl_status, width=35).grid(row=0, column=11, padx=5)
        # Remove old detect button — serial bridge creates the stream
        frm.grid_slaves(row=0, column=10)[0].destroy() if frm.grid_slaves(row=0, column=10) else None

        # Signal monitor + recording
        frm_sig = ttk.LabelFrame(parent, text="信号监视 & 录制", padding=10)
        frm_sig.pack(fill="x", padx=5, pady=5)
        self.ch_labels = []
        self.ch_bars = []
        ch_names_display = ["C3", "C4", "F3", "F4"]
        for i, name in enumerate(ch_names_display):
            ttk.Label(frm_sig, text=f"{name}:", width=4).grid(row=0, column=i*4, padx=(10,2))
            lbl = ttk.Label(frm_sig, text="----", width=10, font=("", 11, "bold"))
            lbl.grid(row=0, column=i*4+1)
            self.ch_labels.append(lbl)
            bar = ttk.Progressbar(frm_sig, length=80, mode="determinate", maximum=200)
            bar.grid(row=0, column=i*4+2, padx=2)
            bar["value"] = 100  # center
            self.ch_bars.append(bar)

        self.record_btn = ttk.Button(frm_sig, text="录制 .fif", command=self._toggle_recording, width=12)
        self.record_btn.grid(row=0, column=17, padx=(20,5))
        self.record_time_var = tk.StringVar(value="未录制")
        ttk.Label(frm_sig, textvariable=self.record_time_var, width=10).grid(row=0, column=18)
        ttk.Button(frm_sig, text="保存路径...", command=self._browse_record_path, width=10).grid(row=0, column=19, padx=5)
        self.record_path_var = tk.StringVar(value="")
        ttk.Label(frm_sig, textvariable=self.record_path_var, width=30).grid(row=0, column=20, padx=5)

        # LSL monitor thread
        self._monitor_running = False
        self._recording = False
        self._record_data = []
        self._record_fs = 0

        # WebSocket
        frm2 = ttk.LabelFrame(parent, text="游戏连接", padding=10)
        frm2.pack(fill="x", padx=5, pady=5)
        self.ws_port = tk.StringVar(value="8767")
        ttk.Label(frm2, text="端口:").pack(side="left")
        ttk.Entry(frm2, textvariable=self.ws_port, width=8).pack(side="left", padx=5)
        ttk.Button(frm2, text="启动在线服务", command=self._start_online).pack(side="left", padx=10)
        ttk.Button(frm2, text="停止", command=self._stop_online).pack(side="left")
        ttk.Label(frm2, textvariable=self.ws_status, width=30).pack(side="left", padx=10)

        # Classify display
        frm3 = ttk.LabelFrame(parent, text="实时分类", padding=10)
        frm3.pack(fill="x", padx=5, pady=5)
        self.classify_display = tk.Label(frm3, textvariable=self.classify_label,
                                         font=("", 28, "bold"), fg="blue", width=20)
        self.classify_display.pack(pady=10)

        # Conf display
        frm4 = ttk.Frame(frm3)
        frm4.pack()
        self.conf_bar = ttk.Progressbar(frm4, length=300, mode="determinate", maximum=100)
        self.conf_bar.pack(side="left")
        self.conf_label = ttk.Label(frm4, text="", width=8)
        self.conf_label.pack(side="left", padx=5)

        # Log area
        frm5 = ttk.LabelFrame(parent, text="在线日志", padding=5)
        frm5.pack(fill="both", expand=True, padx=5, pady=5)
        self.online_log = tk.Text(frm5, height=8, wrap="word")
        self.online_log.pack(fill="both", expand=True)

    # ── File dialogs ──

    def _browse_bdf(self):
        p = filedialog.askopenfilename(filetypes=[("BDF/FIF files", "*.bdf *.fif"), ("All", "*.*")])
        if p: self.bdf_path.set(p)

    def _browse_session(self):
        p = filedialog.askopenfilename(filetypes=[("JSONL files", "*.jsonl"), ("All", "*.*")])
        if p: self.session_path.set(p)

    def _browse_model_save(self):
        p = filedialog.asksaveasfilename(defaultextension=".json",
                                         filetypes=[("JSON", "*.json")])
        if p: self.model_path.set(p)

    # ── Training ──

    def _run_training(self):
        bdf = self.bdf_path.get()
        ses = self.session_path.get()
        if not bdf or not ses:
            messagebox.showerror("错误", "请选择 BDF 和 session JSONL 文件")
            return

        def _train():
            try:
                self.status.set("加载数据中...")
                self._log_train("=" * 50)
                self._log_train(f"BDF: {Path(bdf).name}")
                self._log_train(f"Session: {Path(ses).name}")

                if bdf.endswith(".fif"):
                    raw = mne.io.read_raw_fif(bdf, preload=True, verbose=False)
                else:
                    raw = mne.io.read_raw_bdf(bdf, preload=True, verbose=False)
                data = raw.get_data()
                fs = raw.info['sfreq']  # use BDF's actual sample rate
                meas = raw.info.get('meas_date')
                if meas.tzinfo is not None:
                    bdf_ms = int((meas - timedelta(hours=8)).timestamp() * 1000)
                else:
                    bdf_ms = int(meas.timestamp() * 1000)
                self._log_train(f"Channels: {raw.ch_names}, {data.shape[1]/FS:.0f}s")

                with open(ses) as f:
                    trials = [json.loads(l) for l in f if l.strip() and json.loads(l).get('type') == 'trial']
                self._log_train(f"Trials: {len(trials)}")

                self.status.set("提取特征中...")
                feats, labels = [], []
                for t in trials:
                    gt = t['ground_truth']
                    ts = (t['timestamp_trial_start_ms'] - bdf_ms) / 1000.0
                    bo = int(ts * fs); be = int((ts + 2.0) * fs)
                    to = be; te = int((ts + 4.0) * fs)
                    if bo < 0 or te > data.shape[1]: continue
                    f = extract_erd_features(data[:, bo:be], data[:, to:te], fs=fs)
                    feats.append(f)
                    labels.append(1 if gt == 'left' else 2)

                if len(feats) == 0:
                    raise ValueError("没有提取到有效试次——请检查 BDF 和 session 时间是否对齐、文件是否匹配")

                X, y = np.array(feats), np.array(labels)
                self._log_train(f"Features: {X.shape}")

                unique_labels = set(labels)
                if len(unique_labels) < 2:
                    raise ValueError(f"标签只有一类: {unique_labels}，需要同时有 left 和 right 试次")

                self.status.set("训练 LDA...")
                self._w, self._b, self._classes = train_lda(X, y)
                scores = X.dot(self._w) + self._b
                y_pred = np.where(scores < 0, self._classes[0], self._classes[1])
                acc = float(np.mean(y_pred == y))
                self._log_train(f"Accuracy: {acc:.1%}")

                for l in sorted(set(labels)):
                    m = y == l; n = m.sum()
                    c = (y_pred[m] == l).sum()
                    name = "left" if l == 1 else "right"
                    self._log_train(f"  {name}: {c}/{n} ({c/n:.1%})")

                # Save model
                model_path = self.model_path.get()
                Path(model_path).parent.mkdir(parents=True, exist_ok=True)
                model_data = {
                    "w": self._w.tolist(), "b": self._b,
                    "classes": self._classes.tolist(),
                    "feature_names": FEATURE_NAMES,
                    "n_features": X.shape[1],
                }
                with open(model_path, 'w') as f:
                    json.dump(model_data, f, indent=2)
                self._log_train(f"Model saved: {model_path}")

                self.accuracy_var.set(f"{acc:.0%}")
                self.n_trials_var.set(str(len(X)))
                self.status.set("训练完成 ✓")
                self.root.after(0, self._refresh_model_list)

            except Exception as e:
                self._log_train(f"ERROR: {e}")
                self.status.set("训练失败")
                raise

        threading.Thread(target=_train, daemon=True).start()

    def _run_fp1fp2_training(self):
        """训练 FP1/FP2 SVM/RF 分类器。"""
        bdf = self.bdf_path.get()
        ses_dir = str(Path(self.session_path.get()).parent) if self.session_path.get() else ""
        if not bdf:
            messagebox.showerror("错误", "请选择 BDF 文件")
            return
        if not ses_dir or not Path(ses_dir).exists():
            # Try default session dir
            ses_dir = str(Path(__file__).parent.parent / "试次数据")
        output = str(Path(__file__).parent / "models" / "fp1fp2_model")

        def _train_fp():
            try:
                self.status.set("训练 FP1/FP2 SVM...")
                self._log_train("=" * 50)
                self._log_train(f"FP1/FP2 SVM/RF 训练")
                self._log_train(f"BDF: {Path(bdf).name}")
                self._log_train(f"Sessions: {ses_dir}")

                from train_fp1fp2 import main as train_main
                import sys
                sys.argv = ["train_fp1fp2", "--bdf", bdf, "--sessions", ses_dir,
                           "--output", output]
                train_main()

                self._log_train(f"训练完成 → {output}")
                self.status.set("FP1/FP2 训练完成 ✓")
                self.fp1fp2_model_path.set(output)
                self.classifier_type.set("svm_fp1fp2")
                self.root.after(100, self._load_fp1fp2_model)
            except Exception as e:
                self._log_train(f"ERROR: {e}")
                self.status.set("FP1/FP2 训练失败")
                import traceback
                self._log_train(traceback.format_exc())

        threading.Thread(target=_train_fp, daemon=True).start()

    def _log_train(self, msg):
        self.train_log.insert("end", msg + "\n")
        self.train_log.see("end")

    # ── Model management ──

    def _refresh_model_list(self):
        """Scan models directory and populate dropdown (old LDA + FP1/FP2)."""
        model_dir = DEFAULT_MODEL_DIR
        model_dir.mkdir(parents=True, exist_ok=True)
        models = list(model_dir.glob("*.json"))
        self._model_list = [(m.name, m) for m in sorted(models)]

        # Also scan FP1/FP2 model dirs
        fp1fp2_dirs = [d for d in model_dir.glob("fp1fp2_*") if d.is_dir()]
        fp1fp2_dirs += [d for d in model_dir.glob("fp1fp2_model") if d.is_dir()]
        for d in sorted(fp1fp2_dirs):
            meta = d / "mi_model.json"
            if meta.exists():
                self._model_list.append((f"[FP1FP2] {d.name}", meta))

        names = [f"{m.name}  ({self._read_model_info(m)})" for _, m in self._model_list]
        self.model_combo["values"] = names
        if self._model_list:
            self.model_combo.current(0)

        # Also auto-load FP1/FP2 model if available
        fp_path = model_dir / "fp1fp2_model"
        if fp_path.exists() and (fp_path / "mi_model.json").exists():
            if not self._fp1fp2_clf:
                self.fp1fp2_model_path.set(str(fp_path))
                self.classifier_type.set("svm_fp1fp2")
                self.root.after(200, self._load_fp1fp2_model)

    def _read_model_info(self, path):
        try:
            data = json.loads(open(path).read())
            n = data.get("n_trials", data.get("n_samples", "?"))
            a = data.get("accuracy", data.get("train_accuracy", None))
            ctype = data.get("clf_type", "")
            if a is not None: return f"{n}试次 {float(a):.0%}{' '+ctype.upper() if ctype else ''}"
            return f"{n}试次"
        except Exception:
            return "?"

    def _on_model_selected(self, _event=None):
        pass

    def _on_clf_type_selected(self, _event=None):
        """分类器类型切换时加载对应模型。"""
        ctype = self.classifier_type.get()
        if ctype in ("svm_fp1fp2", "rf_fp1fp2"):
            self._load_fp1fp2_model()
        else:
            self._fp1fp2_clf = None
            self.clf_type_label.config(text="使用旧 LDA 模型")

    def _browse_fp1fp2_model(self):
        from tkinter import filedialog as fd
        p = fd.askdirectory(title="选择 FP1/FP2 模型目录")
        if p:
            self.fp1fp2_model_path.set(p)
            self._load_fp1fp2_model()

    def _load_fp1fp2_model(self):
        """加载 FP1/FP2 SVM/RF 模型。"""
        try:
            from fp1fp2_classifier import FP1FP2Classifier
            ctype = self.classifier_type.get()
            clf_type = "svm" if ctype == "svm_fp1fp2" else "rf"
            self._fp1fp2_clf = FP1FP2Classifier.load(
                self.fp1fp2_model_path.get())
            info = self._fp1fp2_clf.model_info
            self.accuracy_var.set(f"{info.get('train_accuracy', 0):.0%}")
            self.n_trials_var.set(str(info.get("n_samples", "?")))
            self.clf_type_label.config(
                text=f"✓ {clf_type.upper()} {info.get('train_accuracy',0):.0%}")
            self.status.set(f"已加载: {self.fp1fp2_model_path.get()}")
            self._log_online(f"加载 FP1/FP2 {clf_type.upper()} 模型")
        except Exception as e:
            self.clf_type_label.config(text=f"加载失败")
            self._log_online(f"FP1/FP2 模型加载失败: {e}")

    def _load_selected_model(self):
        idx = self.model_combo.current()
        if idx < 0 or idx >= len(self._model_list):
            messagebox.showwarning("提示", "请先选择模型")
            return
        name, path = self._model_list[idx]

        # Detect FP1/FP2 model directory
        if "[FP1FP2]" in name:
            # path is the mi_model.json inside the dir
            model_dir = str(path.parent)
            self.fp1fp2_model_path.set(model_dir)
            self.classifier_type.set("svm_fp1fp2")
            self._load_fp1fp2_model()
            return

        # Old LDA model
        try:
            data = json.loads(open(path).read())
            self._w = np.array(data["w"])
            self._b = data["b"]
            self._classes = np.array(data["classes"])
            self.model_path.set(str(path))
            self.accuracy_var.set(data.get("accuracy", "--"))
            self.n_trials_var.set(str(data.get("n_trials", "--")))
            self.status.set(f"已加载: {path.name}")
            self._log_online(f"加载模型: {path.name} ({self._read_model_info(path)})")
        except Exception as e:
            messagebox.showerror("错误", f"加载失败: {e}")

    def _try_load_model(self):
        path = self.model_path.get()
        if Path(path).exists():
            try:
                data = json.loads(open(path).read())
                self._w = np.array(data["w"])
                self._b = data["b"]
                self._classes = np.array(data["classes"])
                self.accuracy_var.set(data.get("accuracy", "--"))
                self.n_trials_var.set(str(data.get("n_trials", "--")))
                self._log_online(f"已加载模型: {Path(path).name}")
            except Exception:
                pass

    # ── Serial bridge ──

    def _refresh_serial_ports(self):
        import glob
        ports = (glob.glob("/dev/cu.usb*") + glob.glob("/dev/cu.wchusb*") +
                 glob.glob("/dev/cu.SLAB*") + glob.glob("/dev/ttyUSB*"))
        self.serial_combo["values"] = ports
        if ports and not self.serial_port_var.get():
            self.serial_port_var.set(ports[0])

    def _toggle_serial_bridge(self):
        if hasattr(self, '_serial_running') and self._serial_running:
            self._serial_running = False
            self.serial_btn.config(text="启动串口桥接")
            self.serial_status_var.set("已停止")
        else:
            self._start_serial_bridge()

    def _start_serial_bridge(self):
        port = self.serial_port_var.get()
        baud = int(self.serial_baud_var.get())
        stream_name = self.lsl_stream_name.get()
        n_ch = int(self.lsl_channels.get())
        fs = float(self.lsl_fs.get())
        ch_names = ["C3", "C4", "F3", "F4"]

        self._serial_running = True
        self.serial_btn.config(text="停止桥接")
        self.serial_status_var.set(f"连接 {port}...")

        def _bridge():
            import serial as pyserial
            from pylsl import StreamInfo, StreamOutlet

            info = StreamInfo(stream_name, "EEG", n_ch, fs, "int32",
                              source_id=f"serial_{port}")
            ch_xml = info.desc().append_child("channels")
            for name in ch_names[:n_ch]:
                ch = ch_xml.append_child("channel")
                ch.append_child_value("label", name)
            outlet = StreamOutlet(info)

            try:
                ser = pyserial.Serial(port, baud, timeout=0.1)
                ser.reset_input_buffer()
            except Exception as e:
                self.root.after(0, lambda: self.serial_status_var.set(f"串口错误: {e}"))
                self.root.after(0, lambda: self.serial_btn.config(text="启动串口桥接"))
                self._serial_running = False
                return

            buf = bytearray()
            count = 0
            recorded = 0
            t0 = time.time()
            self.root.after(0, lambda: self.serial_status_var.set(f"✓ {stream_name} ({n_ch}ch@{fs:.0f}Hz)"))
            self._log_online(f"串口桥接启动: {port} → LSL {stream_name}")
            self.root.after(500, self._start_monitor)

            try:
                while self._serial_running:
                    waiting = ser.in_waiting
                    if waiting:
                        chunk = ser.read(waiting)
                        buf.extend(chunk)

                    # Parse AA + 12B (4ch×3B), ignore BB
                    i = 0
                    buflen = len(buf)
                    while i < buflen - 13:
                        if buf[i] != 0xAA:
                            i += 1
                            continue
                        raw = buf[i+1:i+13]
                        samples = [int.from_bytes(raw[ch*3:(ch+1)*3], "big", signed=True) for ch in range(n_ch)]
                        # Validate: at least 2 channels have varying values (not stuck at 0x808080)
                        varying = sum(1 for v in samples if abs(v) < 8000000)
                        if varying >= 2:
                            outlet.push_sample(samples)
                            count += 1
                            if self._recording:
                                self._record_buf.append(samples)
                                recorded += 1
                            i += 13  # skip the data we just parsed
                        else:
                            i += 1  # false AA, advance 1 byte

                    if i > 0: buf = buf[i:]
                    elif len(buf) > 65536: buf = buf[-32768:]
                    if waiting == 0: time.sleep(0.005)

                    if count > 0 and count % 100 == 0:
                        elapsed = time.time() - t0
                        rate = count / elapsed if elapsed > 0 else 0
                        self.root.after(0, lambda c=count, r=recorded, rt=rate: self.serial_status_var.set(
                            f"✓ {c}帧 {rt:.0f}fps" + (f" 已录{r}" if self._recording else "")))

            except Exception as e:
                self.root.after(0, lambda: self._log_online(f"串口错误: {e}"))
            finally:
                ser.close()
                self.root.after(0, lambda: self.serial_status_var.set("已断开"))
                self.root.after(0, lambda: self.serial_btn.config(text="启动串口桥接"))
                self._serial_running = False
                self._log_online(f"串口桥接停止 ({count} 样本)")

        threading.Thread(target=_bridge, daemon=True).start()

    # ── Signal monitor & recording ──

    def _start_monitor(self):
        """Start LSL monitor thread — updates channel displays and handles recording."""
        if self._monitor_running:
            return
        self._monitor_running = True
        stream_name = self.lsl_stream_name.get()
        n_ch = int(self.lsl_channels.get())

        def _monitor():
            from pylsl import StreamInlet, resolve_byprop
            # Wait for LSL stream to appear
            inlet = None
            for _ in range(50):  # 5s timeout
                streams = resolve_byprop("type", "EEG", timeout=1.0)
                target = [s for s in streams if s.name() == stream_name]
                if target:
                    inlet = StreamInlet(target[0])
                    break
                time.sleep(0.1)

            if not inlet:
                self.root.after(0, lambda: self._log_online("监视器: LSL 流未找到"))
                self._monitor_running = False
                return

            info = inlet.info()
            fs = info.nominal_srate()
            self.root.after(0, lambda: self._log_online(
                f"监视器已连接: {info.name()} {info.channel_count()}ch {fs:.0f}Hz"))
            self.root.after(0, lambda: self.lsl_status.set(
                f"✓ 监视: {info.name()} {fs:.0f}Hz"))

            self._record_fs = fs
            self._record_buf = []
            rec_start = 0.0

            total_pulled = 0
            try:
                while self._monitor_running:
                    chunk, chunk_ts = inlet.pull_chunk(timeout=0.1, max_samples=200)
                    if chunk:
                        total_pulled += len(chunk)
                        # Update display with last sample
                        last = chunk[-1]
                        for i in range(min(n_ch, len(last))):
                            self.root.after(0, lambda v=last[i], idx=i: self._update_ch_display(idx, v))

                        # Recording
                        if self._recording:
                            for sample in chunk:
                                self._record_buf.append(sample[:n_ch])
                            elapsed = time.time() - rec_start
                            if len(self._record_buf) % 1000 == 0:
                                self.root.after(0, lambda: self.record_time_var.set(
                                    f"录制中 {len(self._record_buf)/fs:.0f}s ({total_pulled} total)"))
                    time.sleep(0.005)
            except Exception as e:
                self.root.after(0, lambda: self._log_online(f"监视器错误: {e}"))
            self._monitor_running = False

        threading.Thread(target=_monitor, daemon=True).start()

    def _update_ch_display(self, idx, value):
        """Update channel value label and bar. Bar color = signal quality."""
        if idx < len(self.ch_labels):
            self.ch_labels[idx].config(text=f"{value:+.0f}")
            bar_val = max(0, min(200, 100 + value / 100000))
            self.ch_bars[idx]["value"] = bar_val
            # Signal quality by running variance (proxy for impedance)
            if not hasattr(self, '_ch_history'):
                self._ch_history = [[0.0]*50 for _ in range(4)]
            self._ch_history[idx].append(value)
            self._ch_history[idx] = self._ch_history[idx][-50:]
            std = np.std(self._ch_history[idx])
            if std < 50000: color = "green"       # low noise = good contact
            elif std < 200000: color = "gold"      # moderate
            else: color = "red"                     # high noise = poor contact
            try:
                self.ch_bars[idx].configure(style=f"{color}.Horizontal.TProgressbar")
            except Exception:
                pass  # fallback if style not configured

    def _browse_record_path(self):
        p = filedialog.askdirectory(title="选择 BDF 保存目录")
        if p:
            self.save_dir.set(p)
            self.root.after(100, self._update_record_path_display)

    def _update_record_path_display(self):
        self.record_path_var.set(f"保存到: {self.save_dir.get()}")

    def _toggle_recording(self):
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        if not hasattr(self, '_serial_running') or not self._serial_running:
            messagebox.showwarning("提示", "请先启动串口桥接")
            return
        self._recording = True
        self._record_buf = []
        self._record_start = time.time()
        self.record_btn.config(text="停止录制")
        self.record_time_var.set("录制中 0s")
        save_dir = self.save_dir.get()
        ts = time.strftime("%Y%m%d_%H%M%S")
        fname = f"recording_{ts}.fif"
        self._record_path = Path(save_dir) / fname
        self.record_path_var.set(fname)
        self._log_online(f"开始录制: {self._record_path}")

    def _stop_recording(self):
        self._recording = False
        self.record_btn.config(text="录制 .fif")
        self.record_time_var.set("保存中...")
        self._log_online("录制已停止，保存中...")
        # Save in background thread to not block UI
        threading.Thread(target=self._do_save_recording, daemon=True).start()

    def _do_save_recording(self):
        """Actually save the recorded data."""
        time.sleep(0.3)  # let final samples flush
        if hasattr(self, '_record_buf') and self._record_buf:
            self._save_recorded_bdf(self._record_buf, self._record_fs)

    def _save_recorded_bdf(self, data, fs):
        """Save recorded data as BDF file with 50Hz notch filter."""
        import mne
        import numpy as np

        try:
            if not data or len(data) < 100:
                self.root.after(0, lambda: self._log_online(
                    f"保存失败: 数据太短 ({len(data)} 样本)"))
                self.root.after(0, lambda: self.record_time_var.set("数据太短"))
                return

            n_ch = len(data[0])
            arr = np.array(data).T  # (n_ch, n_samples)
            ch_names = ["C3", "C4", "F3", "F4"][:n_ch]
            ch_types = ["eeg"] * n_ch

            info = mne.create_info(ch_names, fs, ch_types)
            raw = mne.io.RawArray(arr, info)

            # Apply 50Hz notch filter
            raw.notch_filter(50, fir_design="firwin", verbose=False)

            # Ensure directory exists
            self._record_path.parent.mkdir(parents=True, exist_ok=True)
            raw.save(str(self._record_path), overwrite=True)

            self.root.after(0, lambda: self.record_time_var.set("已保存"))
            self.root.after(0, lambda: self._log_online(
                f"文件已保存: {self._record_path} ({arr.shape[1]/fs:.0f}s, {n_ch}ch, 已去50Hz)"))
            self.root.after(0, lambda: messagebox.showinfo("录制完成",
                f"文件已保存:\n{self._record_path}\n\n{arr.shape[1]/fs:.0f}s, {n_ch}ch\n50Hz 工频已过滤"))
        except Exception as e:
            self.root.after(0, lambda: self._log_online(f"保存失败: {e}"))
            self.root.after(0, lambda: self.record_time_var.set("保存失败"))

    # ── LSL detection ──

    def _detect_lsl(self):
        """检测 LSL 流 (串口桥接启动后自动可见)"""
        try:
            from pylsl import resolve_streams
            all_s = resolve_streams(2.0)
            target = self.lsl_stream_name.get()
            eeg = [s for s in all_s if s.type() == "EEG" and s.name() == target]
            if not eeg:
                eeg = [s for s in all_s if s.type() == "EEG"]
            if eeg:
                s = eeg[0]
                self.lsl_stream_name.set(s.name())
                self.lsl_channels.set(str(s.channel_count()))
                self.lsl_fs.set(f"{s.nominal_srate():.0f}")
                self.lsl_status.set(f"✓ {s.name()} | {s.channel_count()}ch | {s.nominal_srate():.0f}Hz")
            else:
                self.lsl_status.set("未找到 — 请先启动串口桥接")
        except Exception as e:
            self.lsl_status.set(f"错误: {e}")

    # ── Online service ──

    def _start_online(self):
        ctype = self.classifier_type.get()
        use_fp1fp2 = ctype in ("svm_fp1fp2", "rf_fp1fp2")

        if use_fp1fp2:
            if self._fp1fp2_clf is None:
                messagebox.showerror("错误", "请先加载 FP1/FP2 模型")
                return
        else:
            if self._w is None:
                messagebox.showerror("错误", "请先训练或加载模型")
                return

        port = int(self.ws_port.get())
        self._online_running = True
        self.status.set(f"在线服务启动中 ({ctype})...")
        stream_name = self.lsl_stream_name.get()
        left_idx = int(self.lsl_left_idx.get())
        right_idx = int(self.lsl_right_idx.get())
        fs_gui = int(self.lsl_fs.get())

        # Capture refs for thread
        _w, _b, _classes = self._w, self._b, self._classes
        _fp1fp2_clf = self._fp1fp2_clf

        def _serve():
            import asyncio
            import websockets
            from pylsl import StreamInlet, resolve_byprop
            from scipy import signal as scipy_sig

            def notch_filt(x, fs, freq=50, q=30):
                b, a = scipy_sig.iirnotch(freq, q, fs)
                return scipy_sig.filtfilt(b, a, x)

            def butter_bandpass(x, lo, hi, fs, order=4):
                nyq = 0.5 * fs
                b, a = scipy_sig.butter(order, [lo/nyq, hi/nyq], btype="band")
                return scipy_sig.filtfilt(b, a, x)

            def build_packet(seq, label, conf):
                return json.dumps({
                    "seq": seq, "timestamp_ms": int(time.time() * 1000),
                    "label": label, "confidence": round(float(conf), 3),
                })

            async def handler(websocket):
                self.root.after(0, lambda: self.ws_status.set("游戏已连接"))
                self._log_online(f"游戏连接 (classifier={ctype})")

                streams = resolve_byprop("type", "EEG", timeout=5.0)
                target = [s for s in streams if s.name() == stream_name] if streams else []
                if target:
                    inlet = StreamInlet(target[0])
                elif streams:
                    inlet = StreamInlet(streams[0])
                    self.root.after(0, lambda: self._log_online(
                        f"注意: 用了 {streams[0].name()} 而非 {stream_name}"))
                else:
                    inlet = None
                if not inlet:
                    self._log_online(f"LSL 流 '{stream_name}' 未找到!")
                    await websocket.close()
                    return
                self._log_online(f"LSL: {stream_name}")
                self.root.after(0, lambda: self.lsl_status.set(f"已连接 {stream_name}"))

                # Trial state
                trial_baseline, trial_task = [], []
                baseline_done, task_done = False, False
                baseline_n, task_n = 500, 500
                seq = 0

                try:
                    while self._online_running:
                        chunk, _ = inlet.pull_chunk(timeout=0.05, max_samples=40)
                        if chunk:
                            for sample in chunk:
                                arr = np.asarray(sample, dtype=np.float64)
                                if not baseline_done:
                                    trial_baseline.append(arr)
                                    if len(trial_baseline) >= baseline_n:
                                        baseline_done = True
                                elif not task_done:
                                    trial_task.append(arr)
                                    if len(trial_task) >= task_n:
                                        task_done = True
                                        bl = np.array(trial_baseline).T
                                        tk = np.array(trial_task).T

                                        if use_fp1fp2:
                                            # FP1(idx=4) / FP2(idx=5)
                                            fp1_bl = notch_filt(butter_bandpass(bl[4], 0.5, 45, fs_gui), fs_gui)
                                            fp2_bl = notch_filt(butter_bandpass(bl[5], 0.5, 45, fs_gui), fs_gui)
                                            fp1_tk = notch_filt(butter_bandpass(tk[4], 0.5, 45, fs_gui), fs_gui)
                                            fp2_tk = notch_filt(butter_bandpass(tk[5], 0.5, 45, fs_gui), fs_gui)

                                            from fp1fp2_classifier import extract_features_online
                                            feat = extract_features_online(fp1_bl, fp1_tk, fp2_bl, fp2_tk, fs_gui)
                                            result = _fp1fp2_clf.predict_one(feat)
                                            label = result["label"]
                                            conf = result["confidence"]
                                        else:
                                            # Old LDA: ERD(9feat) from T7/T8
                                            bl = notch_filter(bl, fs=fs_gui)
                                            tk = notch_filter(tk, fs=fs_gui)
                                            f = extract_erd_features(bl, tk, left_idx=left_idx, right_idx=right_idx, fs=fs_gui)
                                            score = float(f.dot(_w) + _b)
                                            label = "left" if score < 0 else "right"
                                            conf = min(0.95, 1.0 / (1.0 + np.exp(-abs(score))))

                                        seq += 1
                                        await websocket.send(build_packet(seq, label, conf))
                                        self.root.after(0, lambda l=label, c=conf: self._show_classify(l, c))
                                        self._log_online(f"→ {label} conf={conf:.2f}")
                                        trial_baseline, trial_task = [], []
                                        baseline_done, task_done = False, False

                        try:
                            raw = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                            event = json.loads(raw)
                            ev_type = event.get("type", "")
                            if ev_type == "trial_start":
                                trial_baseline, trial_task = [], []
                                baseline_done, task_done = False, False
                                self._log_online(f"trial_start layer={event.get('layer')}")
                        except (asyncio.TimeoutError, json.JSONDecodeError):
                            pass

                        await asyncio.sleep(0.02)

                except websockets.exceptions.ConnectionClosed:
                    self._log_online("游戏断开")
                finally:
                    self.root.after(0, lambda: self.ws_status.set("等待连接..."))

            async def main():
                self._log_online(f"WebSocket: ws://0.0.0.0:{port}")
                self.root.after(0, lambda: self.ws_status.set(f"监听端口 {port}"))
                self.root.after(0, lambda: self.status.set(f"在线服务运行中 ({ctype})"))
                async with websockets.serve(handler, "0.0.0.0", port, max_size=2**20):
                    while self._online_running:
                        await asyncio.sleep(0.5)

            asyncio.run(main())

        self._online_thread = threading.Thread(target=_serve, daemon=True)
        self._online_thread.start()

    def _stop_online(self):
        self._online_running = False
        self.status.set("在线服务已停止")
        self.ws_status.set("已停止")

    def _show_classify(self, label, conf):
        self.classify_label.set(f"{label}")
        if label == "left":
            self.classify_display.config(fg="blue")
        elif label == "right":
            self.classify_display.config(fg="red")
        else:
            self.classify_display.config(fg="gray")
        self.conf_bar["value"] = conf * 100
        self.conf_label.config(text=f"{conf:.0%}")

    def _log_online(self, msg):
        self.online_log.insert("end", f"{time.strftime('%H:%M:%S')} {msg}\n")
        self.online_log.see("end")


# ── Main ──

if __name__ == "__main__":
    root = tk.Tk()
    app = MIBciApp(root)
    root.mainloop()
