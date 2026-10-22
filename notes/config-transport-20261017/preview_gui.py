from pathlib import Path
import sys,os,tempfile,json,hashlib
P=Path(__file__).resolve().parents[2];R=P/'experiments/config_transport_20261017'
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path[:0]=[str(R/'gui'),str(R/'scripts'),str(R)]
from PyQt5.QtWidgets import QApplication
from workbench import WorkbenchWindow
from check_transport_host import Device
from instrument_config import default_config
from device_config import apply_supported
app=QApplication([])
with tempfile.TemporaryDirectory() as directory:
    w=WorkbenchWindow(str(Path(directory)/'preferences.json'));w.timer.stop();w.show()
    w.setWindowTitle('离线界面预览 · 未连接硬件')
    d=Device();d.kind='真实串口';r=apply_supported(d,default_config())
    w._applied(r);w._open_advanced();dialog=w.advanced_dialog
    dialog.scope.setText('离线回执预览：新固件可应用频谱、持续/击发/混合及包络。仅本次通电有效；尚无本版本板级验证。')
    dialog.apply_button.setText('应用频谱与包络')
    dialog.status.setText('离线模拟回执 · '+dialog.status.text())
    dialog.resize(920,640);app.processEvents()
    path=R/'evidence/gui-config-preview.png';assert dialog.grab().save(str(path))
    (R/'evidence/gui-preview.json').write_text(json.dumps(dict(status='PASS offscreen rendering only',hardware_tested=False,image_sha256=hashlib.sha256(path.read_bytes()).hexdigest()),indent=2))
    dialog.close();w.editor._saved=w.editor.document();w.editor_panel.saved=w.editor_panel.document();w.close()
print('PASS isolated GUI preview; no serial opened')
