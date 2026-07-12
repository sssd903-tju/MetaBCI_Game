#!/usr/bin/env python3
"""离线训练 + LOO验证 — 复现报告结果
Usage: python 01_train_and_validate.py
输出: 特征对比表、逐Session表、FAA统计表、混淆矩阵
"""
import json, numpy as np
from pathlib import Path
import mne; from scipy import signal as sp_sig
from scipy.integrate import trapezoid as trapz
from scipy.stats import ttest_ind
from sklearn.model_selection import LeaveOneOut
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.neighbors import KNeighborsClassifier
from collections import Counter

FS=250.0
BANDS={"theta":(4,8),"alpha":(8,13),"low_beta":(13,20),"high_beta":(20,30),"beta":(13,30),"broadband":(0.5,30)}

def bp(x,fs,lo,hi):
    nperseg=min(128,len(x)//2); 
    if nperseg<32:nperseg=len(x)//4
    if nperseg<16:return 0.0
    f,p=sp_sig.welch(x,fs,nperseg=nperseg);m=(f>=lo)&(f<=hi)
    return float(trapz(p[m],f[m])) if m.sum()>=2 else 0.0

def clean(ch,fs):
    b,a=sp_sig.iirnotch(50,30,fs);ch=sp_sig.filtfilt(b,a,ch)
    nyq=0.5*fs;b,a=sp_sig.butter(4,[0.5/nyq,45/nyq],btype="band");return sp_sig.filtfilt(b,a,ch)

def temporal_faa(tk1_c,tk2_c):
    f=[];seg=125
    for (l,h) in [(8,13),(13,30)]:
        for s in range(4):
            se,ee=s*seg,min((s+1)*seg,len(tk1_c))
            p1=bp(tk1_c[se:ee],FS,l,h);p2=bp(tk2_c[se:ee],FS,l,h)
            f.append((p2-p1)/(p2+p1+1e-15))
    return np.array(f)

def collect(bdf_file, ses_files):
    raw=mne.io.read_raw_bdf(str(bdf_file),preload=True,verbose=False)
    data=raw.get_data();ch=raw.ch_names
    fp1_i=ch.index("Fp1") if "Fp1" in ch else 5;fp2_i=ch.index("Fp2") if "Fp2" in ch else 4
    meas=raw.info.get("meas_date");bdf_ms=int((meas.timestamp()-8*3600)*1000)
    fp1=clean(data[fp1_i].astype(np.float64),FS);fp2=clean(data[fp2_i].astype(np.float64),FS)
    windows=[]
    for sf in ses_files:
        with open(sf) as f:
            trials=[json.loads(l) for l in f if l.strip() and json.loads(l).get("type")=="trial"]
        for t in trials:
            ts=t["timestamp_trial_start_ms"];off=(ts-bdf_ms)/1000.0
            bl_s=int(off*FS);bl_e=int((off+2)*FS);tk_e=int((off+4)*FS)
            if bl_s<0 or tk_e>len(fp1):continue
            bl1=fp1[bl_s:bl_e][:500];tk1=fp1[bl_e:tk_e][:500]
            bl2=fp2[bl_s:bl_e][:500];tk2=fp2[bl_e:tk_e][:500]
            if len(bl1)<400:continue
            s1=np.std(np.concatenate([bl1-bl1.mean(),tk1-tk1.mean()]))
            s2=np.std(np.concatenate([bl2-bl2.mean(),tk2-tk2.mean()]))
            tk1_c=(tk1-tk1.mean())/(s1+1e-10);tk2_c=(tk2-tk2.mean())/(s2+1e-10)
            windows.append((tk1_c,tk2_c,1 if t["ground_truth"]=="left" else 2,sf.name))
    return windows

DATA_DIR = Path("../验证数据/MI")
BDF10=DATA_DIR/"试次10.bdf"; BDF13=DATA_DIR/"试次13.bdf"
BDF14=DATA_DIR/"试次14.bdf"; BDF16=DATA_DIR/"试次16.bdf"

# Offline training (5 sessions, 49 trials)
offline=[]
offline+=collect(BDF10,[DATA_DIR/"session_20260614_103654.jsonl"])
offline+=collect(BDF10,[DATA_DIR/"session_20260614_103846.jsonl"])
offline+=collect(BDF10,[DATA_DIR/"session_20260614_104027.jsonl"])
offline+=collect(BDF13,[DATA_DIR/"session_13.jsonl"])
offline+=collect(BDF14,[DATA_DIR/"session_14.jsonl"])

X=np.nan_to_num(np.array([temporal_faa(w[0],w[1]) for w in offline]),0)
y=np.array([w[2] for w in offline])
n=len(y)
print(f"=== 离线训练数据: {n} 试次 (L={sum(y==1)} R={sum(y==2)}), 基线={max(sum(y==1),sum(y==2))/n:.1%} ===\n")

# Table 1: Feature comparison
print("表1: 分类器对比 (Temporal FAA 8d × SVM-RBF)")
loo=LeaveOneOut()
for cn,clf in [("LDA",LinearDiscriminantAnalysis()),
                ("SVM-rbf",SVC(kernel="rbf",C=1.0,gamma="scale",class_weight="balanced",random_state=42)),
                ("RF",RandomForestClassifier(n_estimators=200,max_depth=8,class_weight="balanced",random_state=42)),
                ("GB",GradientBoostingClassifier(n_estimators=100,max_depth=3,random_state=42)),
                ("KNN",KNeighborsClassifier(n_neighbors=5))]:
    accs=[];cm=Counter()
    for tr,te in loo.split(X):
        if len(np.unique(y[tr]))<2:continue
        scl=StandardScaler();X_tr=scl.fit_transform(X[tr]);X_te=scl.transform(X[te])
        clf.fit(X_tr,y[tr]);pred=clf.predict(X_te)[0]
        accs.append(1 if pred==y[te[0]] else 0);cm[(y[te[0]],pred)]+=1
    acc=np.mean(accs);lr=cm.get((1,1),0)/max(1,cm.get((1,1),0)+cm.get((1,2),0))
    rr=cm.get((2,2),0)/max(1,cm.get((2,2),0)+cm.get((2,1),0))
    print(f"  {cn:<10s}: {acc:.1%}  L_recall={lr:.0%}  R_recall={rr:.0%}")

# Table 3: FAA per-band
print(f"\n表3: 逐频带FAA统计显著性")
faa_arr=X
print(f"  {'Band':<16s} {'Left':>10s} {'Right':>10s} {'t':>7s} {'p':>7s}")
for j,bn in enumerate(BANDS):
    t,pv=ttest_ind(faa_arr[y==1,j] if j<6 else np.zeros(len(y)), 
                    faa_arr[y==2,j] if j<6 else np.zeros(len(y)))
    # only first 6 are FAA
    if j>=6:continue
    sig=" ***" if pv<0.001 else " **" if pv<0.01 else " *" if pv<0.05 else ""
    print(f"  {bn:<16s} {np.mean(faa_arr[y==1,j]):>+9.4f}  {np.mean(faa_arr[y==2,j]):>+9.4f}  {t:>+6.3f} {pv:>6.4f}{sig}")

# Train final model
scaler=StandardScaler();X_s=scaler.fit_transform(X)
clf=SVC(kernel="rbf",C=1.0,gamma="scale",class_weight="balanced",probability=True,random_state=42)
clf.fit(X_s,y);train_acc=float(np.mean(clf.predict(X_s)==y))
print(f"\n=== 最终模型: Temporal FAA(8d) × SVM-rbf, 训练准确率={train_acc:.0%} ===")
