"""Desktop analysis of real FPGA PCM and acknowledged musical events."""
import binascii
import struct
import time
from collections import deque

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QPainter, QColor, QPen, QPainterPath
from PyQt5.QtWidgets import QWidget

FS = 27000000 / 512
MAGIC = b'FMV1'


class FrameParser:
    def __init__(self):
        self.buffer = bytearray()
        self.errors = 0
        self.gaps = 0
        self.sequence = None

    def feed(self, data):
        self.buffer.extend(data)
        frames = []
        while len(self.buffer) >= 16:
            start = self.buffer.find(MAGIC)
            if start < 0:
                self.buffer[:] = self.buffer[-3:]
                break
            if start:
                del self.buffer[:start]
                self.errors += 1
            if len(self.buffer) < 16:
                break
            kind, seq, size, stamp, losses, fmt = struct.unpack('<BHHIHB', self.buffer[4:16])
            if fmt not in (1,2) or (kind, size) not in ((1, 1024), (2, 2)):
                del self.buffer[0]
                self.errors += 1
                continue
            if len(self.buffer) < size + 18:
                break
            raw = bytes(self.buffer[:size + 18])
            if binascii.crc_hqx(raw[4:-2], 0xffff) != int.from_bytes(raw[-2:], 'big'):
                del self.buffer[0]
                self.errors += 1
                continue
            del self.buffer[:size + 18]
            if self.sequence is not None and seq != (self.sequence + 1) & 65535:
                self.gaps += 1
            self.sequence = seq
            frames.append(dict(kind=kind, sequence=seq, timestamp=stamp, losses=losses,
                               payload=raw[16:-2], raw=raw, format=fmt))
        return frames


class LiveWorker(QThread):
    batch = pyqtSignal(object)
    failure = pyqtSignal(str)
    started_stream = pyqtSignal()

    def __init__(self, link, parent=None):
        super().__init__(parent)
        self.link = link
        self.stop_requested = False
        self.stats = {}

    def stop(self):
        self.stop_requested = True

    def run(self):
        link = self.link
        if not link._transaction.acquire(blocking=False):
            self.failure.emit('串口被其他事务占用')
            return
        ser = link.ser
        previous_timeout = ser.timeout
        parser = FrameParser()
        started = False
        frames_count = bytes_count = 0
        try:
            if link.baud != 460800:
                raise RuntimeError('实时模式需要D4实时码流及460800 bps连接；当前配置仅支持快照')
            ser.timeout = .3
            ser.reset_input_buffer()
            def write(data):
                with link._write_lock:
                    if ser.write(data) != len(data):
                        raise RuntimeError('串口短写')
                    ser.flush()
            for addr, expected in ((0x7f, 0x11), (0xa4, 0xd4), (0xa5, 4), (0xa9, 32)):
                write(bytes((15, addr)))
                if ser.read(2) != bytes((addr, expected)):
                    raise RuntimeError('设备身份不符，需要完整32组D4/rev4实时观察配置')
            if hasattr(ser, 'set_buffer_size'):
                ser.set_buffer_size(rx_size=262144, tx_size=65536)
            ser.timeout = .02  # SetCommState must finish before requesting a stream.
            write(bytes((0xb5, 1)))
            started = True
            link.capture_busy = True
            self.started_stream.emit()
            last_data = time.monotonic()
            while not self.stop_requested:
                raw = ser.read(max(1, min(8192, ser.in_waiting)))
                bytes_count += len(raw)
                frames = parser.feed(raw)
                if frames:
                    last_data = time.monotonic()
                    frames_count += len(frames)
                    self.batch.emit(dict(frames=frames, crc_errors=parser.errors, gaps=parser.gaps))
                if time.monotonic() - last_data > .8:
                    raise RuntimeError('实时音频断流；显示已冻结，请检查设备/连接')
        except Exception as exc:
            self.failure.emit(str(exc))
        finally:
            if started:
                try:
                    with link._write_lock:
                        ser.write(bytes((0xb5, 0)))
                        ser.flush()
                    # Complete the single in-flight frame, then leave readback clean.
                    deadline = time.monotonic() + .12
                    while time.monotonic() < deadline and ser.read(4096):
                        pass
                except Exception as exc:
                    self.failure.emit('停止流失败：' + str(exc))
            ser.timeout = previous_timeout
            link.capture_busy = False
            link._transaction.release()
            self.stats = dict(frames=frames_count, bytes=bytes_count,
                              crc_errors=parser.errors, gaps=parser.gaps)


class LiveAnalysis:
    def __init__(self):
        self.audio = np.zeros(0, dtype=np.float64)
        self.events = deque(maxlen=1024)
        self.active = {}
        self.now = 0.
        self.sample_rate = FS
        self.stride = 1
        self.expected = None
        self.discontinuities = 0
        self.losses = self.crc_errors = self.gaps = 0
        self.frames = 0
        self.last_received = None
        self.frequencies = self.db = np.zeros(0)

    def ingest(self, batch):
        if batch['crc_errors']>self.crc_errors or batch['gaps']>self.gaps:
            self.active.clear()
        self.crc_errors, self.gaps = batch['crc_errors'], batch['gaps']
        for f in batch['frames']:
            if f['losses']!=self.losses:self.active.clear()
            self.losses = f['losses']
            if f['kind'] == 1:
                self.stride=4 if f.get('format',1)==2 else 1
                self.sample_rate=FS/self.stride
                if self.expected is not None and f['timestamp'] != self.expected:
                    self.discontinuities += 1
                    self.audio = np.zeros(0)  # Never draw across an unobserved gap.
                    self.active.clear()  # State after a missing event cannot be asserted.
                x = np.frombuffer(f['payload'], dtype='<i2').astype(np.float64) / 32768
                self.audio = np.concatenate((self.audio, x))[-int(self.sample_rate * 4):]
                self.expected = (f['timestamp'] + len(x)*self.stride) & 0xffffffff
                self.now = (f['timestamp'] + len(x)*self.stride) / FS
                self.frames += 1
            else:
                note = f['payload'][0] & 127
                on = bool(f['payload'][0] & 128)
                t = f['timestamp'] / FS
                if on:
                    if note in self.active:
                        self.events.append((self.active[note], t, note))
                    self.active[note] = t
                elif note in self.active:
                    self.events.append((self.active.pop(note), t, note))
        self.last_received = time.monotonic()

    def spectrum(self):
        n = 1024 if self.stride==4 else 4096
        if len(self.audio) < n:
            self.frequencies = self.db = np.zeros(0)
            return
        window = np.hanning(n)
        x = self.audio[-n:]
        # Hann coherent-gain correction: a full-scale sinusoid is about 0 dBFS.
        magnitude = np.abs(np.fft.rfft(x * window)) * (2 / window.sum())
        magnitude[0] *= .5
        magnitude[-1] *= .5
        self.frequencies = np.fft.rfftfreq(n, 1 / self.sample_rate)
        self.db = 20 * np.log10(np.maximum(magnitude, 1e-6))


class LivePlot(QWidget):
    def __init__(self, model, mode, parent=None):
        super().__init__(parent)
        self.model, self.mode = model, mode
        self.gain = 4
        self.seconds = 2.
        self.setMinimumHeight(150)
        self.setMinimumWidth(240)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor('#111e2d'))
        left, top, right, bottom = 48, 30, self.width()-16, self.height()-28
        title = {'wave': '实际波形 · 效果后 PCM16', 'spectrum': '频谱 · 电脑FFT / dBFS',
                 'trajectory': '演奏轨迹 · FPGA已接受事件'}[self.mode]
        p.setPen(QColor('#d8e4ed')); p.drawText(12, 19, title)
        p.setPen(QColor('#304359'))
        for i in range(5):
            y = top + (bottom-top)*i/4
            p.drawLine(int(left), int(y), int(right), int(y))
        m = self.model
        if m.last_received is None:
            p.setPen(QColor('#8396ac'))
            p.drawText(self.rect(), Qt.AlignCenter, '等待真实设备数据')
            return
        if self.mode == 'wave':
            x = m.audio[-max(1, int(self.seconds*m.sample_rate)):]
            p.setPen(QPen(QColor('#62d6bb'), 1))
            cols = max(1, min(right-left, len(x)))
            if len(x):
                starts=np.arange(cols)*len(x)//cols
                low=np.minimum.reduceat(x,starts);high=np.maximum.reduceat(x,starts)
                ylow=((top+bottom)/2-np.clip(low*self.gain,-1,1)*(bottom-top)/2).astype(int)
                yhigh=((top+bottom)/2-np.clip(high*self.gain,-1,1)*(bottom-top)/2).astype(int)
                for i in range(cols):
                    p.drawLine(int(right-cols+i),int(yhigh[i]),int(right-cols+i),int(ylow[i]))
            p.setPen(QColor('#8396ac'))
            p.drawText(4, top+6, '+%g' % (1/self.gain))
            p.drawText(4, bottom, '−%g' % (1/self.gain))
            p.drawText(left, self.height()-7, '最近 %.3g 秒 · ×%d' % (self.seconds,self.gain))
        elif self.mode == 'spectrum':
            if not len(m.db): return
            p.setPen(QPen(QColor('#e9b864'), 1.4)); path = QPainterPath()
            chosen = (m.frequencies >= 20) & (m.frequencies <= min(20000,m.sample_rate/2))
            for i, (f, value) in enumerate(zip(m.frequencies[chosen], m.db[chosen])):
                x = left + (np.log10(f)-np.log10(20))/np.log10(min(20000,m.sample_rate/2)/20)*(right-left)
                y = bottom - np.clip((value+100)/100, 0, 1)*(bottom-top)
                if i == 0: path.moveTo(x,y)
                else: path.lineTo(x,y)
            p.drawPath(path);p.setPen(QColor('#8396ac'))
            p.drawText(4, top+6, '0 dB');p.drawText(4,bottom,'−100')
            p.drawText(left,self.height()-7,'20 Hz          1 kHz          %.2f kHz · 观察低通'%(min(20000,m.sample_rate/2)/1000))
        else:
            t0 = m.now - 8
            visible = [(a,b,n) for a,b,n in m.events if b>=t0] + [(a,m.now,n) for n,a in m.active.items()]
            notes = [n for a,b,n in visible]
            lo,hi = (min(notes)-2,max(notes)+2) if notes else (58,78)
            p.setPen(QColor('#8396ac'));p.drawText(4,top+6,str(hi));p.drawText(4,bottom,str(lo))
            p.setPen(QPen(QColor('#9bb5ff'),5))
            for a,b,n in visible:
                x1 = left+max(0,(a-t0)/8)*(right-left)
                x2 = left+min(1,(b-t0)/8)*(right-left)
                y = bottom-(n-lo)/(hi-lo)*(bottom-top)
                p.drawLine(int(x1),int(y),int(x2),int(y))
            p.setPen(QColor('#8396ac'));p.drawText(left,self.height()-7,'最近8秒 · 音符接受/释放；不是实体触点轨迹')
