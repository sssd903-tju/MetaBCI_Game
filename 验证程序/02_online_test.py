#!/usr/bin/env python3
"""在线测试验证 — Session 16 (30试次)
复现报告表4: 直播数据FAA统计 + 分类准确率
"""
import json, numpy as np
from pathlib import Path
import mne; from scipy import signal as sp_sig
from scipy.integrate import trapezoid as trapz
from scipy.stats import ttest_ind
from sklearn.model_selection import LeaveOneOut
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

FS=250.0
BANDS={"theta":(4,8),"alpha":(8,13),"low_beta":(13,20),"high_beta":(20,30),"beta":(13,30),"broadband":(0.5,30)}

def bp(x,fs,lo,hi):
    nperseg=min(128,len(x)//2)
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

DATA_DIR = Path("../验证数据/MI")
BDF16=DATA_DIR/"试次16.bdf"

raw=mne.io.read_raw_bdf(str(BDF16),preload=True,verbose=False)
data=raw.get_data();ch=raw.ch_names
fp1_i=ch.index("Fp1") if "Fp1" in ch else 5;fp2_i=ch.index("Fp2") if "Fp2" in ch else 4
meas=raw.info.get("meas_date");bdf_ms=int((meas.timestamp()-8*3600)*1000)
fp1=clean(data[fp1_i].astype(np.float64),FS);fp2=clean(data[fp2_i].astype(np.float64),FS)

windows=[]
for sf in sorted(DATA_DIR.glob("session_20260614_163*.jsonl")):
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
        windows.append((temporal_faa(tk1_c,tk2_c),1 if t["ground_truth"]=="left" else 2))

X=np.nan_to_num(np.array([w[0] for w in windows]),0)
y=np.array([w[1] for w in windows])
n=len(y)
print(f"=== 在线测试数据: {n} 试次 (L={sum(y==1)} R={sum(y==2)}) ===\n")

# FAA per-band stats (Table 4)
print("表4: 逐频带FAA统计显著性 (直播数据)")
faa_arr=X
print(f"  {'Band':<16s} {'Left':>10s} {'Right':>10s} {'t':>7s} {'p':>7s}")
for j,bn in enumerate(BANDS):
    if j>=6:continue
    t,pv=ttest_ind(faa_arr[y==1,j],faa_arr[y==2,j])
    sig=" ***" if pv<0.001 else " **" if pv<0.01 else " *" if pv<0.05 else ""
    print(f"  {bn:<16s} {np.mean(faa_arr[y==1,j]):>+9.4f}  {np.mean(faa_arr[y==2,j]):>+9.4f}  {t:>+6.3f} {pv:>6.4f}{sig}")

# LOO classification
print(f"\n=== LOO-CV 分类准确率 ===")
loo=LeaveOneOut();accs=[]
for tr,te in loo.split(X):
    if len(np.unique(y[tr]))<2:continue
    scl=StandardScaler();X_tr=scl.fit_transform(X[tr]);X_te=scl.transform(X[te])
    clf=SVC(kernel="rbf",C=1.0,gamma="scale",class_weight="balanced",random_state=42)
    clf.fit(X_tr,y[tr]);pred=clf.predict(X_te)[0]
    accs.append(1 if pred==y[te[0]] else 0)
print(f"  Temporal FAA(8d) × SVM-rbf LOO: {np.mean(accs):.1%} ({sum(accs)}/{len(accs)})")

# θFAA sign accuracy
ft=faa_arr[:,0];med=np.median(ft)
sign_acc=sum(1 for i in range(n) if (ft[i]>med and y[i]==1) or (ft[i]<=med and y[i]==2))/n
print(f"  θFAA median-split: {sign_acc:.1%}")
t_theta,p_theta=ttest_ind(faa_arr[y==1,0],faa_arr[y==2,0])
print(f"  θFAA t-test: t={t_theta:.3f} p={p_theta:.4f}")
