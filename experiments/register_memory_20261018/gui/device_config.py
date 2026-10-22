"""Explicit partial v1.1 adapter; never claims a complete physical-unit config."""
import time
import sys
from pathlib import Path
_host = str(Path(__file__).resolve().parents[1]/'host')
if _host not in sys.path: sys.path.append(_host)
from PyQt5.QtCore import QThread, pyqtSignal
import dsp_host as dh
from instrument_config import validate_config

UNSUPPORTED = ['articulation (模式/包络/混合分组)', 'vibrato (物理单位)',
               'effects (物理单位)']


def configuration_capable(link):
    from config_transport_client import CAPABILITY
    return tuple(link.read_reg(0xd0+i) for i in range(6)) == CAPABILITY


def apply_supported(link, document, preset_only=False):
    doc = validate_config(document)
    if link.kind == '真实串口' and link.read_reg(0xd0) == 0x75:
        from config_transport_client import apply_document
        return apply_document(link, doc, preset_only=preset_only)
    record = dict(status='FAILED', source=link.kind, started=time.time(),
                  requested=doc, preset_only=preset_only, writes=[], readback={},
                  unsupported=list(UNSUPPORTED), audio_verified=False)
    record['sent_complete'] = False
    try:
        version = link.read_reg(dh.REG['PROTO_VER'])
        record['protocol_flag_observed'] = version
        if link.kind == '真实串口':
            for addr, expected in ((0xa4,0xd4), (0xa5,4), (0xa9,32)):
                if link.read_reg(addr) != expected:
                    raise RuntimeError('设备能力不符：需要D4/rev4/完整32组；未写入参数')
            record['capability_source'] = 'D4/rev4/完整32组固定诊断字段'
            if version != 0x11:
                record['warnings'] = ['PROTO_VER为可写RAM且当前标志异常；按固定D4/rev4能力适配，未改写标志']
        elif version != 0x11:
            raise RuntimeError('设备不支持协议v1.1完整谱提交；未写入参数')
        ctrl = link.read_reg(dh.REG['CTRL'])
        if ctrl is None:
            raise RuntimeError('CTRL回读超时；未写入参数')
        f = dh.Frames()
        f.w('CTRL', ctrl | 8, '保留控制位，选择寄存器预设')
        f.w('PRESET', doc['preset'], '下一次起音预设')
        spec = dh.cmd_spectrum('add' if preset_only else doc['spectrum_mode'],
                               [0]*16 if preset_only else doc['spectrum'])
        f.items.extend(spec.items)
        # Preserve the planned write list even when a short write fails midway.
        record['writes'] = list(f.items)
        if link.send(f) != 2*len(f.items):
            raise RuntimeError('参数短写；部分设备状态未知')
        record['sent_complete'] = True
        expected = {'CTRL': ctrl | 8, 'PRESET': doc['preset'],
                    'SPEC_MODE': 0 if preset_only or doc['spectrum_mode']=='add' else 1}
        for name, value in expected.items():
            actual = link.read_reg(dh.REG[name])
            record['readback'][name] = actual
            if actual != value:
                raise RuntimeError('%s回读不匹配：%r / %r' % (name, actual, value))
        record['status'] = 'PARTIAL_PARAMETER_CONFIRMED'
        record['spectrum_confirmation'] = '16项已发送，协议无整谱回读；待音频验证'
    except Exception as exc:
        record['error'] = str(exc)
    record['finished'] = time.time()
    return record


class ApplyWorker(QThread):
    result = pyqtSignal(object)

    def __init__(self, link, document, preset_only, parent=None):
        super().__init__(parent)
        self.link, self.document, self.preset_only = link, document, preset_only

    def run(self):
        lock = getattr(self.link, '_transaction', None)
        if lock is None:
            self.result.emit(apply_supported(self.link, self.document, self.preset_only))
        elif lock.acquire(blocking=False):
            try:
                self.result.emit(apply_supported(self.link, self.document, self.preset_only))
            finally:
                lock.release()
        else:
            self.result.emit(dict(status='FAILED', error='串口被其他事务占用', writes=[]))
