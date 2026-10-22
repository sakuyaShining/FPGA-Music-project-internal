"""New configuration GUI path: simulated register transport only."""
import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.append(str(Path(__file__).resolve().parents[1]))
from check_transport_host import Device
from PyQt5.QtWidgets import QApplication
from instrument_config import default_config
from device_config import apply_supported,configuration_capable
from workbench import WorkbenchWindow

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_route_full_configuration_and_preset_restore(self):
        for preset_only in (False,True):
            d=Device();d.kind='真实串口'
            self.assertTrue(configuration_capable(d))
            result=apply_supported(d,default_config(),preset_only)
            self.assertEqual(result['status'],'VOLATILE_CONFIG_CONFIRMED')
            self.assertEqual(result['preset_only'],preset_only)
            self.assertFalse(any(a==0x59 for a,_ in d.ops))
    def test_new_device_failure_never_falls_back_to_partial_writes(self):
        d=Device();d.kind='真实串口';doc=default_config();doc['vibrato']['enabled']=True
        r=apply_supported(d,doc)
        self.assertEqual(r['status'],'FAILED');self.assertFalse(d.ops)
    def test_feedback_states_confirmation_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            w=WorkbenchWindow(str(Path(directory)/'preferences.json'));w.timer.stop()
            d=Device();d.kind='真实串口';r=apply_supported(d,default_config())
            w._applied(r)
            self.assertIn('断电不保留',w.device_status.text())
            self.assertIn('设备已完整确认',w.advanced_dialog.status.text())
            self.assertNotIn('其他草稿字段未应用',w.advanced_dialog.status.text())
            failed=dict(status='FAILED',commit_state='confirmed',cleanup_error='release unconfirmed')
            w._applied(failed);self.assertIn('release unconfirmed',w.device_status.text())
            w.editor._saved=w.editor.document();w.editor_panel.saved=w.editor_panel.document();w.close();w.deleteLater();self.app.processEvents()
    def test_connection_uses_capability_instead_of_unavailable_live_stream(self):
        # A SerialLink fixture avoids opening a physical port.
        from serial_link import SerialLink
        from dsp_gui import MainWindow
        link=SerialLink.__new__(SerialLink);d=Device()
        link.read_reg=d.read_reg
        with tempfile.TemporaryDirectory() as directory:
            w=WorkbenchWindow(str(Path(directory)/'preferences.json'));w.timer.stop()
            def connect(_):w.link=link
            with patch.object(MainWindow,'_toggle_conn',connect),patch.object(w,'_toggle_live') as live:
                w._toggle_conn();self.assertFalse(live.called)
            self.assertTrue(w.performance_ready);self.assertTrue(w.config_device)
            self.assertEqual(w.advanced_dialog.apply_button.text(),'应用频谱与包络')
            w.link=None;w.editor._saved=w.editor.document();w.editor_panel.saved=w.editor_panel.document();w.close();w.deleteLater();self.app.processEvents()

if __name__=='__main__':unittest.main()
