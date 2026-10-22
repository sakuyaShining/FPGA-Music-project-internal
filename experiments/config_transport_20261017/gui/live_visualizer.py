"""Desktop analysis of real FPGA PCM and acknowledged musical events."""
import binascii
import struct
import time
import queue
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
    configuration = pyqtSignal(object)
    sequence_result = pyqtSignal(object)
    observation_gap = pyqtSignal()
    device_state = pyqtSignal(object)

    def __init__(self, link, parent=None, prepare_performance=False):
        super().__init__(parent)
        self.link = link
        self.stop_requested = False
        self.stats = {}
        self.commands = queue.Queue(maxsize=1)
        self.prepare_performance = prepare_performance

    def configure(self, document, preset_only=False):
        self.commands.put_nowait(dict(kind='configuration',document=document,preset_only=preset_only))

    def sequence(self,notes=None,bpm=120,play=False):
        self.commands.put_nowait(dict(kind='sequence',notes=notes,bpm=bpm,play=play))

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
            # A4/A5/A9 are hardwired capabilities. PROTO_VER is RAM in the
            # existing RTL and can be overwritten despite its read-only label;
            # it must not alone reject an otherwise verified live session.
            for addr, expected in ((0xa4, 0xd4), (0xa5, 4), (0xa9, 32)):
                response = b''
                for attempt in range(3):
                    if self.stop_requested: return
                    write(bytes((15, addr)))
                    response = ser.read(2)
                    if len(response)==2: break
                if len(response)<2:
                    raise RuntimeError('设备未响应：请确认板子已开机、UART端口正确，且已下载460800实时程序')
                if response != bytes((addr, expected)):
                    raise RuntimeError('设备身份不符：0x%02X返回%s，预期%02X%02X；需要D4/rev4完整32组实时程序' %
                        (addr,response.hex(),addr,expected))
            if self.prepare_performance:
                import dsp_host as dh
                state = {}
                for name in ('PROTO_VER', 'CTRL', 'PRESET', 'FX_CTRL', 'SPEC_MODE','SEQ_CTRL','SCORE_LEN'):
                    value = link.read_reg(dh.REG[name])
                    if value is None:
                        raise RuntimeError('连接初始化失败：%s回读超时' % name)
                    state[name] = value
                # Test-mode oscillators bypass normal performance. Select the
                # readable preset and disable test mode, retaining expression bits.
                control = (state['CTRL'] & ~1) | 8
                if control != state['CTRL']:
                    f = dh.Frames(); f.w('CTRL', control, '连接后进入演奏模式')
                    link.send(f)
                    if link.read_reg(dh.REG['CTRL']) != control:
                        raise RuntimeError('无法确认设备进入演奏模式')
                    state['CTRL'] = control
                self.device_state.emit(state)
            if hasattr(ser, 'set_buffer_size'):
                ser.set_buffer_size(rx_size=262144, tx_size=65536)
            ser.timeout = .02  # SetCommState must finish before requesting a stream.
            write(bytes((0xb5, 1)))
            started = True
            link.capture_busy = True
            self.started_stream.emit()
            last_data = time.monotonic()
            while not self.stop_requested:
                if not self.commands.empty():
                    command = self.commands.get_nowait()
                    write(bytes((0xb5, 0)))
                    deadline = time.monotonic() + .4
                    last_tail = time.monotonic()
                    while time.monotonic() < deadline:
                        tail = ser.read(4096)
                        if tail:last_tail=time.monotonic()
                        frames = parser.feed(tail)
                        if frames:
                            self.batch.emit(dict(frames=frames, crc_errors=parser.errors, gaps=parser.gaps))
                        # USB/FTDI may insert an empty read inside a fragmented
                        # frame. Only declare RX drained after a complete frame
                        # AND a quiet interval, never after the first empty read.
                        if not tail and not parser.buffer and time.monotonic()-last_tail>=.08:
                            break
                    if parser.buffer or ser.in_waiting:
                        raise RuntimeError('停止流未排空；取消配置，设备状态未知')
                    if command['kind']=='sequence':
                        from score_control import apply_sequence
                        result=apply_sequence(link,command['notes'],command['bpm'],command['play'])
                        self.sequence_result.emit(result)
                    else:
                        from device_config import apply_supported
                        result = apply_supported(link, command['document'], command['preset_only'])
                        self.configuration.emit(result)
                    parser.sequence = None
                    self.observation_gap.emit()
                    if self.stop_requested:
                        break
                    write(bytes((0xb5, 1)))
                    last_data = time.monotonic()
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
                        if ser.write(bytes((0x50,0)))!=2:raise RuntimeError('停止曲谱短写')
                        ser.write(bytes((0xb5,0)))
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
        self.hold_onset = False
        self.audio_blocks = deque(maxlen=12)
        self.onset_stamp = None
        self.onset_note = None
        self.onset_audio = np.zeros(0)

    def _capture_onset(self):
        if self.onset_stamp is None or len(self.onset_audio):return
        n=1024 if self.stride==4 else 4096
        chunks=[]
        for stamp,stride,x in self.audio_blocks:
            if stride!=self.stride:continue
            delta=(stamp+np.arange(len(x),dtype=np.int64)*stride-self.onset_stamp)&0xffffffff
            chunks.append(x[delta<n*stride])
        samples=np.concatenate(chunks) if chunks else np.zeros(0)
        if len(samples)>=n:self.onset_audio=samples[:n].copy()

    def mark_gap(self):
        self.discontinuities += 1
        self.audio = np.zeros(0)
        self.frequencies = self.db = np.zeros(0)
        self.expected = None
        self.active.clear()
        self.audio_blocks.clear()
        self.onset_stamp = self.onset_note = None
        self.onset_audio = np.zeros(0)

    def ingest(self, batch):
        if batch['crc_errors']>self.crc_errors or batch['gaps']>self.gaps:
            self.active.clear()
            self.audio_blocks.clear();self.onset_stamp=None;self.onset_audio=np.zeros(0)
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
                    self.audio_blocks.clear();self.onset_stamp=None;self.onset_audio=np.zeros(0)
                x = np.frombuffer(f['payload'], dtype='<i2').astype(np.float64) / 32768
                self.audio_blocks.append((f['timestamp'],self.stride,x))
                self.audio = np.concatenate((self.audio, x))[-int(self.sample_rate * 4):]
                self.expected = (f['timestamp'] + len(x)*self.stride) & 0xffffffff
                self.now = (f['timestamp'] + len(x)*self.stride) / FS
                self.frames += 1
                self._capture_onset()
            else:
                note = f['payload'][0] & 127
                on = bool(f['payload'][0] & 128)
                t = f['timestamp'] / FS
                if on:
                    self.onset_stamp=f['timestamp'];self.onset_note=note
                    self.onset_audio=np.zeros(0);self._capture_onset()
                    if note in self.active:
                        self.events.append((self.active[note], t, note))
                    self.active[note] = t
                elif note in self.active:
                    self.events.append((self.active.pop(note), t, note))
        self.last_received = time.monotonic()

    def spectrum(self):
        n = 1024 if self.stride==4 else 4096
        source=self.onset_audio if self.hold_onset else self.audio
        if len(source) < n:
            self.frequencies = self.db = np.zeros(0)
            return
        window = np.hanning(n)
        x = source[-n:]
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
        self.overlays = {}
        self.setMinimumHeight(150)
        self.setMinimumWidth(240)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor('#111e2d'))
        left, top, right, bottom = 48, 30, self.width()-16, self.height()-28
        title = {'wave': '实际波形 · 效果后 PCM16', 'spectrum': '频谱 · 电脑FFT / dBFS',
                 'trajectory': '演奏轨迹 · FPGA已接受事件'}[self.mode]
        if self.mode=='spectrum':
            if self.model.hold_onset:
                title='已冻结起音谱 · %s' % ('等待按键' if self.model.onset_note is None else 'MIDI %d'%self.model.onset_note)
            else:
                title='实时频谱 · 第%d帧 / dBFS' % self.model.frames
        if self.property('friendlyLabels'):
            title={'trajectory':'按键记录','wave':'声音波形','spectrum':
                '已冻结频谱 · 起音对比' if self.model.hold_onset else '实时频谱 · 第%d帧'%self.model.frames}[self.mode]
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
            for slot, (freqs, values) in self.overlays.items():
                overlay = QPainterPath(); first = True
                for f, value in zip(freqs, values):
                    if not 20 <= f <= min(20000,m.sample_rate/2): continue
                    x = left + (np.log10(f)-np.log10(20))/np.log10(min(20000,m.sample_rate/2)/20)*(right-left)
                    y = bottom - np.clip((value+100)/100,0,1)*(bottom-top)
                    if first: overlay.moveTo(x,y); first=False
                    else: overlay.lineTo(x,y)
                p.setPen(QPen(QColor('#9bb5ff' if slot=='A' else '#62d6bb'),1,Qt.DashLine))
                p.drawPath(overlay)
            if self.overlays:
                p.setPen(QColor('#d8e4ed'))
                p.drawText(left+100,top+16,'虚线：冻结实测 '+ '/'.join(self.overlays))
            p.setPen(QColor('#8396ac'))
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
