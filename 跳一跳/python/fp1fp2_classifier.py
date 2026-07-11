#!/usr/bin/env python3
"""
FP1/FP2 前额叶 MI 分类器
=========================
30 维多频带特征 (FAA + 绝对功率 + ERD) + SVM-RBF/RF/LDA 多分类器

特征提取 (30 维):
  6 频带 × 4 特征 (log_FP1, log_FP2, FAA, log_total)
  + 2 频带 × 3 ERD  (ERD_FP1, ERD_FP2, lateral)

  频带: theta(4-8), alpha(8-13), low_beta(13-20), high_beta(20-30), beta(13-30), broad(0.5-30)

模型格式 (JSON + pickle):
  mi_model.json       — 元数据 (特征名, 最佳分类器类型, 参数)
  mi_model_svm.pkl    — SVM 模型
  mi_model_rf.pkl     — RandomForest 模型
  mi_model_lda.json   — LDA 权重
"""

import json
import logging
import pickle
import time
from pathlib import Path

import numpy as np
from scipy import signal as sig
from scipy.integrate import trapezoid
from sklearn.preprocessing import StandardScaler
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as SkLDA
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier

logger = logging.getLogger(__name__)

FS = 250.0
BANDS = {
    "theta": (4, 8),
    "alpha": (8, 13),
    "low_beta": (13, 20),
    "high_beta": (20, 30),
    "beta": (13, 30),
    "broadband": (0.5, 30),
}
ERD_BANDS = {"alpha": (8, 13), "beta": (13, 30)}

FEATURE_NAMES = []
for band_name in BANDS:
    FEATURE_NAMES.extend([f"log_{band_name}_FP1", f"log_{band_name}_FP2",
                           f"FAA_{band_name}", f"log_total_{band_name}"])
for band_name in ERD_BANDS:
    FEATURE_NAMES.extend([f"ERD_{band_name}_FP1", f"ERD_{band_name}_FP2",
                           f"ERD_lat_{band_name}"])

N_FEATURES = len(FEATURE_NAMES)  # 30


# ═══════════════════════════════════════════════════════════════
# 特征提取
# ═══════════════════════════════════════════════════════════════

def band_power(x, fs, lo, hi):
    """Welch 法计算频带功率"""
    nperseg = min(128, len(x) // 2)
    if nperseg < 32:
        nperseg = len(x) // 4
    if nperseg < 16:
        return 0.0
    f, p = sig.welch(x, fs, nperseg=nperseg)
    mask = (f >= lo) & (f <= hi)
    if mask.sum() < 2:
        return 0.0
    return float(trapezoid(p[mask], f[mask]))


def extract_features(fp1_bl, fp1_tk, fp2_bl, fp2_tk, fs=FS, normalize=True):
    """从 Fp1/Fp2 的 baseline + task 窗口提取 30 维特征。

    Args:
        fp1_bl, fp1_tk: Fp1 baseline / task 窗口 (1D array)
        fp2_bl, fp2_tk: Fp2 baseline / task 窗口 (1D array)
        fs: 采样率
        normalize: 是否 z-score 归一化 (使模型对不同设备尺度鲁棒)

    Returns:
        np.ndarray shape (30,)
    """
    fp1_bl_c = fp1_bl - fp1_bl.mean()
    fp1_tk_c = fp1_tk - fp1_tk.mean()
    fp2_bl_c = fp2_bl - fp2_bl.mean()
    fp2_tk_c = fp2_tk - fp2_tk.mean()

    # Z-score 归一化: 用基线+任务合并的 std (保留 task vs baseline 相对差异)
    if normalize:
        s1 = np.std(np.concatenate([fp1_bl_c, fp1_tk_c]))
        s2 = np.std(np.concatenate([fp2_bl_c, fp2_tk_c]))
        if s1 > 1e-10:
            fp1_bl_c, fp1_tk_c = fp1_bl_c / s1, fp1_tk_c / s1
        if s2 > 1e-10:
            fp2_bl_c, fp2_tk_c = fp2_bl_c / s2, fp2_tk_c / s2

    features = []

    # 1. 多频带绝对功率 + FAA (6 bands × 4 = 24 dims)
    for band_name, (lo, hi) in BANDS.items():
        p1 = band_power(fp1_tk_c, fs, lo, hi)
        p2 = band_power(fp2_tk_c, fs, lo, hi)
        features.append(np.log(p1 + 1e-15))
        features.append(np.log(p2 + 1e-15))
        # FAA: (FP2 - FP1) / (FP2 + FP1)
        faa = (p2 - p1) / (p2 + p1 + 1e-15)
        features.append(faa)
        features.append(np.log(p1 + p2 + 1e-15))

    # 2. ERD 特征 (2 bands × 3 = 6 dims)
    for band_name, (lo, hi) in ERD_BANDS.items():
        bl1 = band_power(fp1_bl_c, fs, lo, hi)
        tk1 = band_power(fp1_tk_c, fs, lo, hi)
        bl2 = band_power(fp2_bl_c, fs, lo, hi)
        tk2 = band_power(fp2_tk_c, fs, lo, hi)
        erd1 = (tk1 - bl1) / (bl1 + 1e-15)
        erd2 = (tk2 - bl2) / (bl2 + 1e-15)
        features.append(erd1)
        features.append(erd2)
        features.append(erd1 - erd2)

    return np.array(features, dtype=np.float64)


def extract_features_online(fp1_bl, fp1_tk, fp2_bl, fp2_tk, fs=FS):
    """在线特征提取 (带 NaN/Inf 保护)。"""
    feat = extract_features(fp1_bl, fp1_tk, fp2_bl, fp2_tk, fs)
    feat = np.nan_to_num(feat, nan=0.0, posinf=0.0, neginf=0.0)
    return feat


# ═══════════════════════════════════════════════════════════════
# 多分类器
# ═══════════════════════════════════════════════════════════════

class FP1FP2Classifier:
    """FP1/FP2 MI 分类器 — 支持 LDA / SVM-RBF / RandomForest。

    在线推理接口:
        result = clf.predict_one(features)
        # → {"label": "left"|"right", "confidence": 0.85}
    """

    LABEL_MAP = {1: "left", 2: "right"}  # 关卡模式直接使用 left/right

    def __init__(self, clf_type="svm"):
        self.clf_type = clf_type
        self._clf = None
        self._scaler = StandardScaler()
        self._trained = False
        self._n_features = N_FEATURES
        self._feature_names = FEATURE_NAMES
        self._model_info = {}

    def fit(self, X, y, clf_type="svm"):
        """训练分类器。

        Args:
            X: (n_samples, 30) 特征矩阵
            y: (n_samples,) 标签 (1=left, 2=right)
            clf_type: "lda" | "svm" | "rf"
        """
        self.clf_type = clf_type
        X_scaled = self._scaler.fit_transform(X)

        if clf_type == "lda":
            self._clf = SkLDA()
        elif clf_type == "svm":
            self._clf = SVC(kernel="rbf", C=1.0, gamma="scale",
                            probability=True, random_state=42)
        elif clf_type == "rf":
            self._clf = RandomForestClassifier(
                n_estimators=100, max_depth=5, random_state=42)
        else:
            raise ValueError(f"Unknown classifier type: {clf_type}")

        self._clf.fit(X_scaled, y)
        self._trained = True

        # Record training info
        train_acc = float(np.mean(self._clf.predict(X_scaled) == y))
        self._model_info = {
            "clf_type": clf_type,
            "n_features": self._n_features,
            "feature_names": self._feature_names,
            "n_samples": len(X),
            "class_balance": f"left={int(np.sum(y==1))}/right={int(np.sum(y==2))}",
            "train_accuracy": train_acc,
        }
        return self

    def predict_one(self, features):
        """在线推理: 输入特征向量 → 输出标签+置信度。

        Returns:
            {"label": "left"|"right", "confidence": 0.0-1.0}
        """
        if not self._trained:
            return {"label": "rest", "confidence": 0.0}

        X = np.atleast_2d(np.asarray(features, dtype=np.float64))
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        X_scaled = self._scaler.transform(X)

        pred = int(self._clf.predict(X_scaled)[0])
        label = self.LABEL_MAP.get(pred, "rest")

        # Confidence from probability if available
        if hasattr(self._clf, "predict_proba"):
            proba = self._clf.predict_proba(X_scaled)[0]
            conf = float(np.max(proba))
        elif hasattr(self._clf, "decision_function"):
            score = float(self._clf.decision_function(X_scaled)[0])
            conf = min(0.95, 1.0 / (1.0 + np.exp(-abs(score))))
        else:
            conf = 0.8  # fallback

        return {"label": label, "confidence": round(conf, 3)}

    # ── 序列化 ──

    def save(self, model_dir):
        """保存模型到目录。

        文件:
          mi_model.json       — 元数据
          mi_model_{type}.pkl — 分类器
          mi_model_scaler.pkl — StandardScaler
        """
        model_dir = Path(model_dir)
        model_dir.mkdir(parents=True, exist_ok=True)

        # 元数据
        meta = dict(self._model_info)
        meta["feature_names"] = self._feature_names
        meta["n_features"] = self._n_features
        meta["saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        (model_dir / "mi_model.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False))

        # 分类器
        clf_path = model_dir / f"mi_model_{self.clf_type}.pkl"
        with open(clf_path, "wb") as f:
            pickle.dump(self._clf, f)

        # Scaler
        with open(model_dir / "mi_model_scaler.pkl", "wb") as f:
            pickle.dump(self._scaler, f)

        logger.info("Model saved to %s (type=%s)", model_dir, self.clf_type)

    @classmethod
    def load(cls, model_dir):
        """从目录加载模型。"""
        model_dir = Path(model_dir)

        # 加载元数据
        meta_path = model_dir / "mi_model.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Model metadata not found: {meta_path}")
        meta = json.loads(meta_path.read_text())
        clf_type = meta.get("clf_type", "svm")

        obj = cls(clf_type=clf_type)
        obj._model_info = meta
        obj._n_features = meta.get("n_features", N_FEATURES)
        obj._feature_names = meta.get("feature_names", FEATURE_NAMES)

        # 加载 Scaler
        scaler_path = model_dir / "mi_model_scaler.pkl"
        if scaler_path.exists():
            with open(scaler_path, "rb") as f:
                obj._scaler = pickle.load(f)

        # 加载分类器
        clf_path = model_dir / f"mi_model_{clf_type}.pkl"
        if not clf_path.exists():
            raise FileNotFoundError(f"Classifier not found: {clf_path}")
        with open(clf_path, "rb") as f:
            obj._clf = pickle.load(f)

        obj._trained = True
        logger.info("Model loaded from %s (type=%s, acc=%.1f%%)",
                     model_dir, clf_type,
                     meta.get("train_accuracy", 0) * 100)
        return obj

    @property
    def trained(self):
        return self._trained

    @property
    def model_info(self):
        return dict(self._model_info)


# ═══════════════════════════════════════════════════════════════
# 便捷函数: 对比训练所有分类器
# ═══════════════════════════════════════════════════════════════

def train_and_compare(X, y, save_dir=None):
    """训练所有分类器并返回对比结果。

    Returns:
        dict: {clf_type: {"accuracy": float, "classifier": FP1FP2Classifier}}
    """
    from sklearn.model_selection import LeaveOneOut

    results = {}
    loo = LeaveOneOut()

    for clf_type in ["lda", "svm", "rf"]:
        accs = []
        for tr, te in loo.split(X):
            if len(np.unique(y[tr])) < 2:
                continue
            try:
                clf = FP1FP2Classifier()
                clf.fit(X[tr], y[tr], clf_type=clf_type)
                pred = clf.predict_one(X[te][0])
                true_label = FP1FP2Classifier.LABEL_MAP.get(y[te[0]], "rest")
                accs.append(1 if pred["label"] == true_label else 0)
            except Exception:
                continue

        acc = np.mean(accs) if accs else 0
        loo_n = len(accs)

        # Train on all data for production use
        clf_full = FP1FP2Classifier()
        clf_full.fit(X, y, clf_type=clf_type)

        results[clf_type] = {
            "accuracy": acc,
            "loo_n": loo_n,
            "classifier": clf_full,
        }
        logger.info("%s LOO accuracy: %.1f%% (%d/%d)",
                     clf_type.upper(), acc * 100, sum(accs), loo_n)

    # Save the best classifier
    if save_dir and results:
        best_type = max(results, key=lambda k: results[k]["accuracy"])
        best_clf = results[best_type]["classifier"]
        best_clf.save(save_dir)
        logger.info("Best classifier: %s (%.1f%%), saved to %s",
                     best_type, results[best_type]["accuracy"] * 100, save_dir)

    return results
