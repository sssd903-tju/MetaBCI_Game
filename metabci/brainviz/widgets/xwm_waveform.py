"""专业级脑电波形显示器 — 滚动时间轴 + 通道显隐 + 可变采样率 + 轻量带通滤波"""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont

THEMES = {
    'dark': {
        'name': '暗色', 'bg': (12, 16, 22), 'grid_alpha': 0.12,
        'text': (130, 140, 160),
        'colors': [(0, 220, 255), (255, 95, 140), (80, 245, 165),
                   (255, 200, 60), (180, 130, 255), (255, 160, 80)],
    },
    'light': {
        'name': '浅色', 'bg': (248, 250, 254), 'grid_alpha': 0.25,
        'text': (90, 100, 120),
        'colors': [(0, 110, 200), (200, 35, 75), (15, 150, 90),
                   (200, 150, 20), (130, 80, 200), (200, 120, 40)],
    },
}


class _EEGViewBox(pg.ViewBox):
    def __init__(self, widget, ch_idx=0): super().__init__(); self._w = widget; self._ch = ch_idx

    def mouseDragEvent(self, ev, axis=None):
        if ev.button() == Qt.RightButton: return
        if axis is not None: super().mouseDragEvent(ev, axis=axis)
        else: super().mouseDragEvent(ev)

    def mouseClickEvent(self, ev):
        if ev.double(): self._w.resume_auto_scroll(); ev.accept()
        elif ev.button() == Qt.RightButton and self._w._context_menu:
            self._w._context_menu.popup(ev.screenPos().toPoint()); ev.accept()
        else: super().mouseClickEvent(ev)

    def wheelEvent(self, ev):
        self._w._gain_wheel(ev, self._ch); ev.accept()


class WaveformWidget(pg.GraphicsLayoutWidget):
    MIN_GAIN, MAX_GAIN = 0.1, 50.0
    MIN_TW, MAX_TW = 1.0, 60.0

    def __init__(self, buffer, labels=None, sample_rate=250,
                 time_window=5.0, theme='dark', parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)  # 不抢键盘焦点，交给MainWindow
        self.buf = buffer; self._sr = sample_rate; self._tw = float(time_window)
        self._theme_name = theme; self._time_offset = None
        self._labels = labels or ["CH1","CH2","CH3"]; self._n = len(self._labels)
        self._visible = [True]*self._n; self._yrange = [1.0]*self._n  # 每通道独立Y范围
        self._auto_scroll = True; self._paused = False; self._busy = False
        self._bpf_enabled = False; self._bpf_ma_n = 8; self._bpf_passes = 2
        self._context_menu = None
        self._active_ch = 0  # 当前选中通道(键盘缩放用)

        self.ci.layout.setSpacing(0); self.ci.layout.setContentsMargins(0,0,0,0)
        self.plots = []; self._curves = []
        for i in range(self._n):
            vb = _EEGViewBox(self, ch_idx=i); p = self.addPlot(row=i, col=0, viewBox=vb)
            p.showGrid(x=True, y=True, alpha=THEMES[theme]['grid_alpha'])
            vb.setDefaultPadding(0); vb.setMouseEnabled(x=True, y=True)
            p.setLimits(xMin=-1e9, xMax=1e9, minXRange=0.5, maxXRange=120.0)
            c = p.plot(name=f'ch{i}'); self.plots.append(p); self._curves.append(c)
            if i < self._n-1:
                if i > 0: p.setXLink(self.plots[0])
                p.hideAxis('bottom')
            else: p.setLabel('bottom', '时间', units='s')
        self._apply_theme()
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update); self._update_timer.start(33)

    # ── 通道显隐 ──
    def set_visible(self, idx, visible):
        if 0<=idx<self._n and not (not visible and sum(self._visible)<=1):
            self._visible[idx]=visible; self.plots[idx].setVisible(visible)
            self._relink_x(); self.buf.mark_clean()
    def is_visible(self, idx): return self._visible[idx] if 0<=idx<self._n else False
    def visible_count(self): return sum(self._visible)
    def channel_count(self): return self._n
    def _relink_x(self):
        vis=[i for i in range(self._n) if self._visible[i]]
        if not vis: return
        first=vis[0]; last=vis[-1]
        for i in range(self._n):
            self.plots[i].setXLink(None if i==first else self.plots[first])
            (self.plots[i].showAxis if i==last else self.plots[i].hideAxis)('bottom')

    # ── 主题 ──
    def _apply_theme(self):
        t=THEMES[self._theme_name]; self.setBackground(t['bg'])
        for i in range(self._n):
            p=self.plots[i]; p.showGrid(x=True,y=True,alpha=t['grid_alpha'])
            for axn in ('left','bottom'):
                ax=p.getAxis(axn); ax.setPen(pg.mkPen(t['text'],width=1))
                ax.setTextPen(pg.mkPen(t['text']))
                ax.setStyle(tickFont=QFont('Helvetica Neue',9),tickTextOffset=4)
            p.getAxis('left').setWidth(50)
            ci=i%len(t['colors'])
            p.setLabel('left',self._labels[i],color=t['colors'][ci],**{'font-size':'10pt','font-weight':'bold'})
            self._curves[i].setPen(pg.mkPen(color=t['colors'][ci],width=1.6))
        self.plots[-1].setLabel('bottom','时间',units='s',color=t['text'],**{'font-size':'9pt'})
    def set_theme(self,n):
        if n in THEMES and n!=self._theme_name: self._theme_name=n; self._apply_theme()

    # ── 滤波 ──
    def toggle_bpf(self, e): self._bpf_enabled=e; self.buf.mark_clean()
    def set_bpf_params(self, ma_n=8, passes=2): self._bpf_ma_n=ma_n; self._bpf_passes=passes

    # ── 缩放 ──
    def zoom_time_in(self): self._tw=np.clip(self._tw*0.8,self.MIN_TW,self.MAX_TW); self.buf.mark_clean()
    def zoom_time_out(self): self._tw=np.clip(self._tw*1.25,self.MIN_TW,self.MAX_TW); self.buf.mark_clean()
    def zoom_y_in(self): self._yrange[self._active_ch]=np.clip(self._yrange[self._active_ch]*0.5,0.01,100); self.buf.mark_clean()
    def zoom_y_out(self): self._yrange[self._active_ch]=np.clip(self._yrange[self._active_ch]*2.0,0.01,100); self.buf.mark_clean()
    def zoom_y_all_in(self):
        for i in range(self._n): self._yrange[i]=np.clip(self._yrange[i]*0.5,0.01,100)
        self.buf.mark_clean()
    def zoom_y_all_out(self):
        for i in range(self._n): self._yrange[i]=np.clip(self._yrange[i]*2.0,0.01,100)
        self.buf.mark_clean()
    def set_active_channel(self, ch): self._active_ch=ch%self._n

    def _gain_wheel(self, ev, ch=None):
        if ch is None: ch = self._active_ch
        d=ev.angleDelta().y()/120.0 if hasattr(ev,'angleDelta') else ev.delta()/120.0
        self._yrange[ch]=np.clip(self._yrange[ch]*(1.0+d*0.12),0.01,100)
        self.buf.mark_clean()

    # ── 上下文菜单 ──
    def reset_zoom(self):
        self._tw = 5.0
        for i in range(self._n): self._yrange[i] = 1.0

    def set_context_menu(self, menu): self._context_menu=menu

    # ── 降采样 ──
    @staticmethod
    def _downsample(ts, arr, target):
        n=len(arr)
        if n<=target or target<2: return ts,arr
        per=n//target
        if per<=1: return ts,arr
        trunc=per*target; a2d=arr[:trunc].reshape(target,per); t2d=ts[:trunc].reshape(target,per)
        return t2d.mean(axis=1),a2d.mean(axis=1)

    # ── 主刷新 ──
    def _update(self):
        if self._paused: return
        if self._busy: return
        self._busy=True
        try:
            n=int(self._tw*self.buf.sample_rate)
            result=self.buf.get_recent(n); ts=result[0]; arrays=result[1:]
            if len(ts)<2: return

            if self._time_offset is None: self._time_offset=ts[0]
            ts=ts-self._time_offset; now=ts[-1]; tw=self._tw
            vb=self.plots[0].getViewBox(); pw=vb.width()
            target=max(2,min(n,int(pw*2.0))) if pw and pw>0 else n

            for i in range(self._n):
                if not self._visible[i] or i>=len(arrays): continue
                arr=arrays[i]; arr=arr-arr.mean()
                if self._bpf_enabled:
                    for _ in range(self._bpf_passes):
                        nk=self._bpf_ma_n; k=np.ones(nk)/nk; pad=nk//2
                        arr=np.pad(arr,pad,mode='edge'); arr=np.convolve(arr,k,mode='same')
                        arr=arr[pad:-pad]
                xt,ym=self._downsample(ts,arr,target)
                self._curves[i].setData(xt,ym)
                lo,hi=ym.min(),ym.max()
                if not (np.isnan(lo) or np.isnan(hi)):
                    rng=max(hi-lo,1.0)*self._yrange[i]; mid=(lo+hi)/2
                    self.plots[i].setYRange(mid-rng/2,mid+rng/2,padding=0)
            if self._auto_scroll:
                x_min,x_max=(0.0,tw) if now<=tw else (now-tw,now)
                for p in self.plots:
                    if p.isVisible(): p.setXRange(x_min,x_max,padding=0)
        except Exception as e:
            import traceback; print(f"[WAVEFORM] {e}"); traceback.print_exc()
        finally:
            self._busy=False

    def resume_auto_scroll(self): self._auto_scroll=True
    def pause(self): self._paused=True
    def resume(self): self._paused=False; self._auto_scroll=True; self.buf.mark_clean()
    def reset_view(self):
        self._time_offset=None; self._auto_scroll=True
        for p in self.plots: p.setXRange(0.0,self._tw,padding=0); p.enableAutoRange(axis='y')
