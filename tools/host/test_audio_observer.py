"""Protocol identity, short-stream evidence, timeout ordering and exclusion."""
import unittest
import threading
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from audio_observer import CaptureError, capture_serial, decode_stream, FRAME_BYTES
from serial_link import SerialLink


class FakeSerial:
    def __init__(self, short=False, supported=True):
        self._timeout = 0.5
        self.operations = []
        self.pending = b''
        self.raw = bytes((0xA8,)) + b'\xff\xff\x7f\x00\x00\x80' + bytes(2046*3)
        self.short, self.supported = short, supported
    @property
    def timeout(self): return self._timeout
    @timeout.setter
    def timeout(self, value):
        self.operations.append(('timeout', value)); self._timeout = value
    def reset_input_buffer(self): self.operations.append(('reset',))
    def flush(self): pass
    def write(self, buf):
        self.operations.append(('write', bytes(buf)))
        a, v = buf
        if a == 15:
            regs = {0x7F: 0x11, 0xA4: 0xD3 if self.supported else 0, 0xA5: 2,
                    0xA9: 32, 0x80: 6, 0x81: 0, 0x82: 8, 0xA3: 9}
            self.pending = self.raw[:-1] if v == 0xA8 and self.short else self.raw if v == 0xA8 else bytes((v, regs[v]))
        return len(buf)
    def read(self, size):
        self.operations.append(('read', size)); response = self.pending[:size]; self.pending = self.pending[size:]; return response


class ObserverTests(unittest.TestCase):
    def test_signed_full_frame_and_configuration_before_request(self):
        port = FakeSerial()
        data = capture_serial(port)
        self.assertEqual(data['samples'][:2], [(1 << 23)-1, -(1 << 23)])
        self.assertEqual(len(data['samples']), 2048)
        request = port.operations.index(('write', b'\x0f\xa8'))
        self.assertEqual(port.operations[request-1], ('timeout', 5))
        self.assertEqual(port.operations[request+1], ('read', FRAME_BYTES))
        self.assertEqual(port.operations[-1], ('timeout', 0.5))
    def test_short_stream_keeps_exact_bytes(self):
        port = FakeSerial(short=True)
        with self.assertRaises(CaptureError) as caught:
            capture_serial(port)
        self.assertEqual(caught.exception.raw, port.raw[:-1])
        self.assertEqual(port.timeout, 0.5)
    def test_unsupported_device_never_starts_capture(self):
        port = FakeSerial(supported=False)
        with self.assertRaises(CaptureError): capture_serial(port)
        self.assertNotIn(('write', b'\x80\x03'), port.operations)
    def test_invalid_marker(self):
        with self.assertRaises(CaptureError): decode_stream(bytes(FRAME_BYTES))
    def test_transaction_excludes_other_thread_reads_and_disconnect(self):
        link = SerialLink('TEST'); link.ser = FakeSerial()
        link._transaction.acquire()
        outcomes = []
        def competing():
            outcomes.append(link.read_reg(0xA4))
            try: link.close()
            except RuntimeError: outcomes.append('blocked')
        worker = threading.Thread(target=competing); worker.start(); worker.join()
        link._transaction.release()
        self.assertEqual(outcomes, [None, 'blocked'])
        self.assertEqual(link.ser.operations, [])


class ObserverUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
    def test_empty_and_simulated_device_never_show_synthetic_audio(self):
        from dsp_gui import MainWindow, SimLink
        window = MainWindow()
        window.pages.setCurrentIndex(3)
        window.link = SimLink(); window.link.open()
        window._capture_audio()
        self.assertIsNone(window.audio_page.snapshot)
        self.assertEqual(window.audio_page.wave.samples, [])
        self.assertIn('模拟设备', window.audio_page.status.text())
        window.link = None; window.close()
    def test_failure_retains_previous_snapshot_and_labels_history(self):
        from dsp_gui import MainWindow
        from unittest.mock import patch
        window = MainWindow()
        data = dict(samples=[0]*2048, raw=b'', sample_rate=52734.375,
                    elapsed_s=0.7, capture_id=1, source='FPGA测试夹具', captured_at='fixture')
        window.audio_page.show_snapshot(data)
        with patch.object(window, '_archive_audio') as archive:
            window._audio_failed(CaptureError('短流', b'bad'))
            self.assertEqual(archive.call_args.args[1], b'bad')
        self.assertIs(window.audio_page.snapshot, data)
        self.assertIn('历史', window.audio_page.status.text())
        window.close()


if __name__ == '__main__': unittest.main()
