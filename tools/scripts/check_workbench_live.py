"""Explicit real-board check of auto-connect, PCM and one owned test note.

Never downloads firmware. Output directory must be new; original failures remain.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools/host'),str(ROOT/'tools/scripts')]
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QPA_FONTDIR','C:/Windows/Fonts')
import numpy as np
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest
from workbench import WorkbenchWindow


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--port',required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(argv);args.out.mkdir(parents=True,exist_ok=False)
    app=QApplication([]);w=WorkbenchWindow(str(args.out/'display.json'))
    w.show();app.processEvents()
    if w.cmb_port.findText(args.port)<0:w.cmb_port.addItem(args.port)
    w.cmb_port.setCurrentText(args.port)
    errors=[];frames=[];wire=bytearray();note_owned=False
    started=time.monotonic()
    report=dict(status='FAILED',port=args.port,scope='实际FPGA内部PCM和接受事件；不验收DAC/触控')
    def wait(predicate,seconds):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            app.processEvents()
            if predicate():return True
            QTest.qWait(10)
        return False
    try:
        # Record open errors without leaving a modal dialog blocking automation.
        with patch('dsp_gui.QMessageBox.warning',side_effect=lambda *a:errors.append(str(a[-1]))):
            w._toggle_conn()
        if w.live_worker is None:
            raise RuntimeError('无法连接：'+ ';'.join(errors))
        w.live_worker.failure.connect(errors.append)
        def collect(batch):
            frames.extend(batch['frames'])
            wire.extend(b''.join(f['raw'] for f in batch['frames']))
        w.live_worker.batch.connect(collect)
        if not wait(lambda:w.performance_ready or bool(errors),3) or not w.performance_ready:
            raise RuntimeError('自动数据流未就绪：'+ ';'.join(errors))
        report['auto_ready_seconds']=time.monotonic()-started
        w.note_on(0);note_owned=0 in w.held
        if not note_owned:raise RuntimeError('起音未发送')
        wait(lambda:False,.7)
        samples=w.audio_page.live_model.audio.copy()
        w.grab().save(str(args.out/'connected-performance.png'))
        w.note_off(0);note_owned=0 in w.held
        wait(lambda:False,.6)
        m=w.audio_page.live_model
        events=[{'note':f['payload'][0]&127,'on':bool(f['payload'][0]&128)}
                for f in frames if f['kind']==2]
        checks=dict(auto_stream=m.frames>0,on_accepted={'note':60,'on':True} in events,
            off_accepted={'note':60,'on':False} in events,
            pcm_nonzero=bool(len(samples) and np.max(np.abs(samples))>0),
            transport_complete=(m.crc_errors,m.gaps,m.discontinuities,m.losses)==(0,0,0,0))
        report.update(checks=checks,events=events,frames=m.frames,readback=w.connected_registers,
            crc_errors=m.crc_errors,gaps=m.gaps,discontinuities=m.discontinuities,losses=m.losses,
            peak=float(np.max(np.abs(samples))) if len(samples) else 0)
        w._toggle_conn()
        checks['one_click_disconnect']=wait(lambda:w.link is None,3)
        report['status']='PASS' if all(checks.values()) and not errors else 'FAILED'
    except Exception as exc:
        errors.append(str(exc))
    finally:
        if note_owned:w.note_off(0)
        if w.live_worker is not None and w.live_worker.isRunning():
            w.live_worker.stop();w.live_worker.wait(3000);app.processEvents()
        report['errors']=errors
        (args.out/'stream.bin').write_bytes(bytes(wire))
        (args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        w.editor._saved=w.editor.document();w.close()
    if sys.stdout is not None:print(json.dumps(report,ensure_ascii=False))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':sys.exit(main())
