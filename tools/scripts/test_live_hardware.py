"""Real D4 GUI/UART acceptance. Never programs a board or overwrites prior evidence."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools/host'),str(ROOT/'tools/scripts')]
import numpy as np
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
from dsp_gui import MainWindow
from serial_link import SerialLink
from live_visualizer import FrameParser, FS


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',default='COM6');parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--seconds',type=int,default=30)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    app=QApplication([]);w=MainWindow();w.pages.setCurrentIndex(3);w.audio_page.mode.setCurrentIndex(0)
    w.resize(1280,720);w.show();w.activateWindow();w.setFocus()
    w.link=SerialLink(args.port,460800);w.link.open()
    w.badge.setText('真实串口');w.lab_detail.setText(w.link.detail)
    raw=(args.out/'stream.bin').open('wb');
    wire=(args.out/'wire.bin').open('wb')
    original_read=w.link.ser.read
    def observed_read(size=1):
        data=original_read(size);wire.write(data);return data
    w.link.ser.read=observed_read
    frames=[];errors=[];paint_times=[]
    w._toggle_live()
    w.live_worker.batch.connect(lambda b: (frames.extend(b['frames']),raw.write(b''.join(f['raw'] for f in b['frames']))))
    w.live_worker.failure.connect(errors.append)
    started=time.monotonic()
    # Exercise actual key handlers, including release while the RX stream is active.
    actions=[(300,Qt.Key_B,True),(550,Qt.Key_N,True),(900,Qt.Key_B,False),(1300,Qt.Key_N,False),
             (1700,Qt.Key_Z,True),(1720,Qt.Key_X,True),(1740,Qt.Key_C,True),
             (2050,Qt.Key_Z,False),(2070,Qt.Key_X,False),(2090,Qt.Key_C,False)]
    for at,key,on in actions:
        QTimer.singleShot(at,lambda k=key,on=on: QTest.keyPress(w,k) if on else QTest.keyRelease(w,k))
    def capture():
        w.grab().save(str(args.out/'live-layout.png'))
        m=w.audio_page.live_model
        (args.out/'view-at-capture.json').write_text(json.dumps(dict(frames=m.frames,active=list(m.active),
            events=list(m.events),spectrum_bins=len(m.db),audio_samples=len(m.audio))),encoding='utf-8')
    QTimer.singleShot(850,capture)
    def finished():
        raw.close();wire.flush()
        m=w.audio_page.live_model
        af=[f for f in frames if f['kind']==1];ef=[f for f in frames if f['kind']==2]
        discontinuities=sum(b['timestamp']!=(a['timestamp']+512*4)&0xffffffff for a,b in zip(af,af[1:]))
        expected=[(69,True),(72,True),(69,False),(72,False),(60,True),(62,True),(64,True),
                  (60,False),(62,False),(64,False)]
        actual=[(f['payload'][0]&127,bool(f['payload'][0]&128)) for f in ef]
        report=dict(status='FAIL',seconds=time.monotonic()-started,errors=errors,
            audio_frames=len(af),events=actual,discontinuities=discontinuities,
            losses=m.losses,crc_errors=m.crc_errors,gaps=m.gaps,
            nonzero=sum(np.count_nonzero(np.frombuffer(f['payload'],dtype='<i2')) for f in af),
            held=list(w.held.values()),worker_stats=w.live_worker.stats)
        # Readbacks only after stopping; active group bits must be clear.
        w.link.ser.reset_input_buffer()
        import dsp_host as dh
        w.link.send(dh.cmd_note('off:69'))
        w.link.ser.write(bytes((0x83,1)));w.link.ser.flush()
        active=[w.link.read_reg(a) for a in range(0x89,0x8d)]
        report['active_bytes']=active
        good=(not errors and len(af)>args.seconds*23 and not discontinuities and not m.losses
              and not m.crc_errors and not m.gaps and actual==expected and report['nonzero']>0
              and not w.held and active==[0,0,0,0])
        wire.close()
        report['status']='PASS' if good else 'FAIL'
        (args.out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report));w.link.close();w.link=None;w.close();app.exit(0 if good else 1)
    w.live_worker.finished.connect(finished)
    QTimer.singleShot(args.seconds*1000,w._stop_live)
    return app.exec_()


if __name__=='__main__':raise SystemExit(main())
