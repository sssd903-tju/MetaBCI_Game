"""BLE蓝牙数据源 (基于 bleak — macOS CoreBluetooth 后端)"""
import asyncio
import queue
from PySide6.QtCore import QThread, Signal as pyqtSignal
import bleak

EEG_SVC = "0000e100-0000-1000-8000-00805f9b34fb"
EEG_CH  = "0000e101-0000-1000-8000-00805f9b34fb"

class BleThread(QThread):
    signal_status  = pyqtSignal(str)
    signal_devices = pyqtSignal(list)
    signal_connected = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._loop = None
        self._client = None
        self._target = None
        self._scan_only = False
        self.data_queue = queue.Queue(maxsize=1000)

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            if self._scan_only:
                self._loop.run_until_complete(self._scan())
            else:
                self._loop.run_until_complete(self._connect_and_stream())
        except RuntimeError:
            pass

    def stop(self):
        if self._client and self._loop:
            async def _cleanup():
                try:
                    if hasattr(self, '_eeg_char') and self._eeg_char:
                        try: await self._client.stop_notify(self._eeg_char.uuid)
                        except Exception: pass
                    if self._client.is_connected:
                        await self._client.disconnect()
                except Exception: pass
            try:
                future = asyncio.run_coroutine_threadsafe(_cleanup(), self._loop)
                future.result(timeout=3.0)
            except Exception: pass
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        self.wait(3000)

    async def _scan(self):
        self.signal_status.emit("正在扫描...")
        devices = await bleak.BleakScanner.discover(timeout=4.0, return_adv=True)
        result = []
        for addr, (dev, adv) in devices.items():
            name = dev.name or adv.local_name or ""
            if name: result.append((name, addr))
        self.signal_devices.emit(result)
        self.signal_status.emit(f"找到 {len(result)} 个设备")

    async def _connect_and_stream(self):
        self.signal_status.emit(f"正在连接到 {self._target}...")
        self._client = bleak.BleakClient(self._target)
        try:
            await self._client.connect()
        except bleak.exc.BleakError as e:
            self.signal_status.emit(f"❌ 蓝牙连接失败: {str(e)[:80]}")
            return
        except OSError as e:
            self.signal_status.emit(f"❌ 系统错误: {e}")
            return

        # 查找 0xE101
        eeg_char = None
        for svc in self._client.services:
            for ch in svc.characteristics:
                if svc.uuid.lower() == EEG_SVC and ch.uuid.lower() == EEG_CH:
                    eeg_char = ch; break
        if eeg_char is None:
            self.signal_status.emit("❌ 未找到EEG特征 (0xE101)")
            return
        self._eeg_char = eeg_char

        # 控制特征 (0xE102)
        EEG_CTRL = "0000e102-0000-1000-8000-00805f9b34fb"
        ctrl_char = None
        for svc in self._client.services:
            if svc.uuid.lower() == EEG_SVC:
                for ch in svc.characteristics:
                    if ch.uuid.lower() == EEG_CTRL and 'write' in ch.properties:
                        ctrl_char = ch; break
                break

        # 统一回调
        def cb(sender, data):
            try:
                self.data_queue.put_nowait(bytes(data))
            except queue.Full:
                try: self.data_queue.get_nowait(); self.data_queue.put_nowait(bytes(data))
                except queue.Empty: pass

        # 订阅 0xE101
        try:
            await self._client.start_notify(eeg_char, cb)
            self.signal_connected.emit()
            self.signal_status.emit("✅ 蓝牙已连接 (0xE101)")
        except Exception as e:
            self.signal_status.emit(f"订阅失败: {e}")
            return

        # 发启动命令
        if ctrl_char:
            for cmd in (b'\x01', b'\x02', b'\x01\x00', b'\xff'):
                try: await self._client.write_gatt_char(ctrl_char.uuid, cmd, response=True)
                except Exception: pass
                await asyncio.sleep(0.02)

        # 保活: 定期读RSSI防止macOS降级BLE连接
        _keepalive = 0
        while self._client and self._client.is_connected:
            await asyncio.sleep(0.5)
            _keepalive += 1
            if _keepalive % 4 == 0:  # 每2秒
                try: await self._client.get_rssi()
                except Exception: pass


class BleManager:
    def __init__(self):
        self._thread = None

    def scan(self, callback_devices, callback_status):
        self._stop()
        self._thread = BleThread()
        self._thread._scan_only = True
        self._thread.signal_devices.connect(callback_devices)
        self._thread.signal_status.connect(callback_status)
        self._thread.start()

    def connect(self, address, callback_status, callback_connected):
        self._stop()
        self._thread = BleThread()
        self._thread._scan_only = False
        self._thread._target = address
        self._thread.signal_status.connect(callback_status)
        self._thread.signal_connected.connect(callback_connected)
        self._thread.start()
        return self._thread

    def disconnect(self):
        self._stop()

    def _stop(self):
        if self._thread and self._thread.isRunning():
            self._thread.stop()
        self._thread = None
