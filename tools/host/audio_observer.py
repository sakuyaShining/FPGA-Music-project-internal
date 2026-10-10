"""Read existing full32 FPGA diagnostic samples; no software synthesis or FFT."""
import time
from datetime import datetime, timezone

SAMPLE_RATE = 27000000 / 512
FRAME_BYTES = 6145


class CaptureError(RuntimeError):
    def __init__(self, message, raw=b''):
        super().__init__(message)
        self.raw = raw


def decode_stream(raw):
    if len(raw) != FRAME_BYTES or raw[0] != 0xA8:
        raise CaptureError('完整样本流无效：%d / %d 字节' % (len(raw), FRAME_BYTES), raw)
    samples = []
    for i in range(1, len(raw), 3):
        value = int.from_bytes(raw[i:i+3], 'little')
        samples.append(value - (1 << 24) if value & (1 << 23) else value)
    return samples


def capture_serial(ser, fx=True):
    """Caller owns the serial transaction exclusively, including timeout changes."""
    old_timeout = ser.timeout
    raw = b''
    start = time.monotonic()
    try:
        ser.timeout = 0.5
        ser.reset_input_buffer()
        def write(a, v):
            if ser.write(bytes((a, v))) != 2:
                raise CaptureError('串口命令短写', raw)
            ser.flush()
        def read(a):
            write(0x0F, a)
            response = ser.read(2)
            if len(response) != 2 or response[0] != a:
                raise CaptureError('寄存器0x%02X应答无效' % a, response)
            return response[1]
        identity = {a: read(a) for a in (0x7F, 0xA4, 0xA5, 0xA9)}
        if identity != {0x7F: 0x11, 0xA4: 0xD3, 0xA5: 2, 0xA9: 32}:
            raise CaptureError('当前设备不支持已知full32采样协议：%s' % identity)
        write(0x80, 3 if fx else 1)
        deadline = time.monotonic() + 2
        while True:
            status = read(0x80)
            if status & 3 == 2:
                break
            if time.monotonic() >= deadline:
                raise CaptureError('FPGA采样未完成')
            time.sleep(0.01)
        count = read(0x81) | (read(0x82) << 8)
        if count != 2048 or bool(status & 4) != bool(fx):
            raise CaptureError('采样长度或取样节点不符')
        capture_id = read(0xA3)
        # Configure Windows UART before transmission starts (04 transport fix).
        ser.timeout = 5
        write(0x0F, 0xA8)
        raw = ser.read(FRAME_BYTES)
        samples = decode_stream(raw)
        return dict(samples=samples, raw=raw, sample_rate=SAMPLE_RATE,
                    captured_at=datetime.now(timezone.utc).isoformat(),
                    elapsed_s=time.monotonic()-start, capture_id=capture_id,
                    source='FPGA效果后内部24bit' if fx else 'FPGA合成干声24bit',
                    identity={hex(k): v for k, v in identity.items()})
    except CaptureError:
        raise
    except Exception as exc:
        raise CaptureError(str(exc), raw) from exc
    finally:
        ser.timeout = old_timeout


from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QCheckBox, QVBoxLayout, QHBoxLayout, QComboBox


class CaptureWorker(QThread):
    result = pyqtSignal(object)
    failure = pyqtSignal(object)
    def __init__(self, link, fx, parent=None):
        super().__init__(parent)
        self.link, self.fx = link, fx
    def run(self):
        try:
            self.result.emit(self.link.capture_audio(self.fx))
        except Exception as exc:
            self.failure.emit(exc)


class Waveform(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.samples = []
        self.gain = 1
        self.setMinimumHeight(260)
    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor('#111e2d'))
        w, h = self.width(), self.height()
        left, right, top, bottom = 58, w-18, 24, h-34
        p.setPen(QColor('#8396ac'))
        for label, fraction in [('+%g' % (1/self.gain), 0), ('0', 0.5), ('−%g' % (1/self.gain), 1)]:
            y = top + int((bottom-top)*fraction)
            p.drawText(10, y+5, label)
            p.setPen(QColor('#304359')); p.drawLine(left, y, right, y)
            p.setPen(QColor('#8396ac'))
        p.drawText(left, h-10, '0 ms')
        p.drawText(max(left, right-95), h-10, '38.84 ms')
        if not self.samples:
            p.drawText(self.rect(), Qt.AlignCenter, '尚无采样数据 · 不代表静音')
            return
        # Display-only projection of raw FPGA samples; fixed full scale.
        p.setPen(QPen(QColor('#62d6bb'), 1))
        columns = max(1, min(right-left, len(self.samples)))
        for col in range(columns):
            values = self.samples[col*len(self.samples)//columns:(col+1)*len(self.samples)//columns]
            lo, hi = min(values), max(values)
            x = left + int(col*(right-left)/columns)
            def y(value):
                scaled = max(-1, min(1, value*self.gain/(1 << 23)))
                return top + int((1-scaled)*(bottom-top)/2)
            p.drawLine(x, y(hi), x, y(lo))


class AudioPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        heading = QLabel('音乐可视化 · FPGA真实音频快照')
        heading.setObjectName('PageTitle'); layout.addWidget(heading)
        hint = QLabel('电脑显示FPGA采样。此页观察内部数字音频，不证明DAC、喇叭或外部引脚电气输出。')
        hint.setWordWrap(True); layout.addWidget(hint)
        controls = QHBoxLayout()
        self.capture = QPushButton('采集一次'); controls.addWidget(self.capture)
        self.fx = QCheckBox('效果后音频'); self.fx.setChecked(True); controls.addWidget(self.fx)
        self.export = QPushButton('导出快照'); self.export.setEnabled(False); controls.addWidget(self.export)
        self.test_note = QPushButton('发送A4测试音'); controls.addWidget(self.test_note)
        self.zoom = QComboBox()
        for gain in (1, 4, 16): self.zoom.addItem('显示放大 ×%d' % gain, gain)
        controls.addWidget(self.zoom)
        controls.addStretch(); layout.addLayout(controls)
        self.status = QLabel('未采集 · 仅支持真实full32诊断设备，模拟设备不产生音频')
        self.status.setWordWrap(True); layout.addWidget(self.status)
        self.wave = Waveform(); layout.addWidget(self.wave)
        self.zoom.currentIndexChanged.connect(self._zoom_changed)
        self.metadata = QLabel('固定满幅纵轴，24bit内部样本；快照不是连续示波器。')
        self.metadata.setWordWrap(True); layout.addWidget(self.metadata)
        pending = QLabel('演奏轨迹：等待FPGA执行结果与时间戳接口。\n频谱：等待FPGA频谱结果接口；当前不以电脑FFT冒充。\n可发送A4测试音后采集，再点击释放。命令发送成功不等于音频已输出；需观察实际采样。')
        pending.setWordWrap(True); layout.addWidget(pending); layout.addStretch()
        self.snapshot = None
    def _zoom_changed(self):
        self.wave.gain = self.zoom.currentData()
        self.wave.update()
    def show_snapshot(self, data):
        self.snapshot = data
        self.wave.samples = data['samples']; self.wave.update()
        self.export.setEnabled(True)
        self.status.setText('最近成功快照（非持续实时） · %s · %s' % (data['captured_at'], data['source']))
        self.metadata.setText('2048点 · %.3f Hz · 38.84 ms窗口 · 本次事务%.3f s · capture ID %d\n配置标签不等于码流指纹；电脑仅解析和绘制，未计算FFT。' %
                              (data['sample_rate'], data['elapsed_s'], data['capture_id']))
