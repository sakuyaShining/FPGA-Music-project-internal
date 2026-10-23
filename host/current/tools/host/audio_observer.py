"""Read existing full32 FPGA diagnostic samples; no software synthesis; desktop FFT is explicitly authorized for live mode."""
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
from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QCheckBox, QVBoxLayout, QHBoxLayout, QComboBox, QSlider


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
        from live_visualizer import LiveAnalysis, LivePlot
        from PyQt5.QtWidgets import QGroupBox, QSizePolicy
        self.live_model = LiveAnalysis()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        heading = QLabel('演奏工作区 · 实时音乐可视化')
        heading.setObjectName('PageTitle'); layout.addWidget(heading)
        toolbar = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItem('实时三视图 · D4 / 460800 bps', 460800)
        self.mode.addItem('历史快照诊断 · D3 / 115200', 115200)
        self.mode.setCurrentIndex(1)
        self.live_button = QPushButton('开始实时观察')
        self.live_button.setObjectName('Primary')
        self.live_status = QLabel('等待设备 · 连接后选择开始观察')
        self.live_status.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        self.live_status.setMinimumWidth(0)
        toolbar.addWidget(self.mode);toolbar.addWidget(self.live_button);toolbar.addWidget(self.live_status,1)
        layout.addLayout(toolbar)
        self.trajectory = LivePlot(self.live_model, 'trajectory')
        self.trajectory.setMinimumHeight(115)
        layout.addWidget(self.trajectory, 2)
        plots = QHBoxLayout()
        self.live_wave = LivePlot(self.live_model, 'wave')
        self.live_spectrum = LivePlot(self.live_model, 'spectrum')
        plots.addWidget(self.live_wave,1);plots.addWidget(self.live_spectrum,1)
        layout.addLayout(plots, 3)
        view = QHBoxLayout()
        self.timescale = QComboBox()
        for label, seconds in [('波形 2秒 · 演奏包络',2.),('波形 200毫秒',.2),('波形 20毫秒 · 音色细节',.02)]:
            self.timescale.addItem(label,seconds)
        self.zoom = QComboBox()
        for gain in (1,4,16):self.zoom.addItem('显示放大 ×%d'%gain,gain)
        self.zoom.setCurrentIndex(1)
        self.zoom.currentIndexChanged.connect(self._zoom_changed)
        self.timescale.currentIndexChanged.connect(lambda: setattr(self.live_wave,'seconds',self.timescale.currentData()))
        view.addWidget(self.timescale);view.addWidget(self.zoom);view.addStretch()
        layout.addLayout(view)
        self.snapshot_panel = QGroupBox('快照诊断 · 原有功能')
        diag = QVBoxLayout(self.snapshot_panel)
        controls = QHBoxLayout()
        self.capture = QPushButton('采集一次');controls.addWidget(self.capture)
        self.fx = QCheckBox('效果后音频');self.fx.setChecked(True);controls.addWidget(self.fx)
        self.export = QPushButton('导出快照');self.export.setEnabled(False);controls.addWidget(self.export)
        self.test_note = QPushButton('发送A4测试音');controls.addWidget(self.test_note)
        diag.addLayout(controls)
        self.follow = QCheckBox('定时快照（每秒一次，有采样间隙）');diag.addWidget(self.follow)
        self.status = QLabel('未采集 · 快照不是实时音频');self.status.setWordWrap(True);diag.addWidget(self.status)
        self.wave = Waveform();self.wave.setMinimumHeight(100);diag.addWidget(self.wave)
        self.metadata = QLabel('');self.metadata.setWordWrap(True);diag.addWidget(self.metadata)
        layout.addWidget(self.snapshot_panel)
        # The performance dock stays below the plots, with no scrolling page wrapper.
        keyboard = QHBoxLayout();self.play_buttons=[]
        for letter in 'ZXCVBNM,':
            button=QPushButton(letter);button.setFocusPolicy(Qt.NoFocus);button.setMinimumHeight(45)
            self.play_buttons.append(button);keyboard.addWidget(button)
        layout.addLayout(keyboard)
        settings = QHBoxLayout()
        self.oct_down=QPushButton('低八度');self.oct_up=QPushButton('高八度')
        self.velocity=QSlider(Qt.Horizontal);self.velocity.setRange(1,15);self.velocity.setValue(12)
        self.velocity_label=QLabel('力度12/15');self.panic=QPushButton('释放全部音符')
        for widget in (self.oct_down,self.oct_up,self.velocity_label,self.velocity,self.panic):settings.addWidget(widget)
        layout.addLayout(settings)
        self.play_state=QLabel('键盘 Z X C V B N M , · 多音演奏 · 蓝色轨迹来自FPGA接受事件')
        self.play_state.setWordWrap(True);layout.addWidget(self.play_state)
        for control in (self.timescale,self.zoom,self.velocity):control.setFocusPolicy(Qt.NoFocus)
        self.snapshot=None
        self.mode.currentIndexChanged.connect(self.set_mode)
        self.set_mode()

    def set_mode(self):
        live = self.mode.currentData()==460800
        self.snapshot_panel.setVisible(not live)
        for widget in (self.trajectory,self.live_wave,self.live_spectrum,self.timescale,self.live_button):widget.setVisible(live)
        self.live_status.setText('需连接D4/rev4实时配置' if live else '快照模式 · 不表示持续实时')

    def refresh_live(self):
        m=self.live_model;m.spectrum()
        for plot in (self.trajectory,self.live_wave,self.live_spectrum):plot.update()
        if m.last_received is not None:
            age=time.monotonic()-m.last_received
            self.live_status.setText('%s · 已接收%.1f秒音频 · %d帧 · CRC %d / 缺帧 %d / 中断 %d / FPGA损失 %d' %
                ('实时' if age<.5 else '已冻结',m.frames*512/m.sample_rate,m.frames,m.crc_errors,m.gaps,m.discontinuities,m.losses))

    def _zoom_changed(self):
        self.wave.gain = self.zoom.currentData()
        self.live_wave.gain = self.zoom.currentData()
        self.wave.update()
    def show_snapshot(self, data):
        self.snapshot = data
        self.wave.samples = data['samples']; self.wave.update()
        self.export.setEnabled(True)
        self.status.setText('最近成功快照（非持续实时） · %s · %s' % (data['captured_at'], data['source']))
        self.metadata.setText('2048点 · %.3f Hz · 38.84 ms窗口 · 本次事务%.3f s · capture ID %d\n配置标签不等于码流指纹；电脑仅解析和绘制，未计算FFT。' %
                              (data['sample_rate'], data['elapsed_s'], data['capture_id']))
