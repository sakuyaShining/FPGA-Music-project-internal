"""Real-board download, loop, rest, repeated note, stop and manual resume check."""
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
from live_visualizer import FS
from serial_link import SerialLink


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',default='COM6')
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    app=QApplication([]);w=WorkbenchWindow(str(args.out/'display.json'));w.show();app.processEvents()
    w.cmb_port.setCurrentText(args.port);frames=[];wire=bytearray();errors=[]
    report=dict(status='FAIL',score='60:1,0:1,64:1,64:1',bpm=240,
                scope='FPGA accepted events and internal PCM; not analog listening')
    def wait(predicate,seconds=3):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            app.processEvents()
            if predicate():return True
            QTest.qWait(2)
        return False
    def pause(seconds):wait(lambda:False,seconds)
    def collect(batch):
        frames.extend(batch['frames']);wire.extend(b''.join(f['raw'] for f in batch['frames']))
    try:
        with patch('dsp_gui.QMessageBox.warning',side_effect=lambda *a:errors.append(str(a[-1]))):w._toggle_conn()
        if w.live_worker is None:raise RuntimeError(str(errors))
        w.live_worker.batch.connect(collect);w.live_worker.failure.connect(errors.append)
        if not wait(lambda:w.performance_ready or errors) or not w.performance_ready:raise RuntimeError(str(errors))
        w.ed_score.setText(report['score']);w.spin_bpm.setValue(240)
        w.seq_download()
        if not wait(lambda:not w.sequence_busy):raise RuntimeError('Download timeout')
        report['download']=w.sequence_record
        assert report['download']['status']=='CONFIRMED' and not w.sequence_playing
        frames.clear();pause(.3)
        assert not any(f['kind']==2 and f['payload'][0]&128 for f in frames),'Download started sound'
        frames.clear();started=time.monotonic();w.seq_play()
        report['ui_call_seconds']=time.monotonic()-started
        assert report['ui_call_seconds']<.1,'UI blocked'
        if not wait(lambda:not w.sequence_busy):raise RuntimeError('Play timeout')
        report['play']=w.sequence_record
        assert report['play']['status']=='CONFIRMED' and w.sequence_playing
        pause(2.3)
        on=[f['payload'][0]&127 for f in frames if f['kind']==2 and f['payload'][0]&128]
        report['accepted_notes']=on
        pattern=[60,64,64]
        assert len(on)>=5 and any(all(note==pattern[(i+offset)%3] for i,note in enumerate(on)) for offset in range(3)),str(on)
        stamps=[f['timestamp'] for f in frames if f['kind']==2 and f['payload'][0]&128]
        intervals=[((b-a)&0xffffffff)/FS for a,b in zip(stamps,stamps[1:])]
        report['accepted_intervals_seconds']=intervals
        for index,interval in enumerate(intervals):
            expected=.5 if on[index]==60 else .25
            assert abs(interval-expected)<.003,'Tempo/rest mismatch: %r vs %r'%(interval,expected)
        pcm=[np.frombuffer(f['payload'],dtype='<i2') for f in frames if f['kind']==1]
        report['pcm_peak']=int(np.max(np.abs(np.concatenate(pcm).astype(np.int32)))) if pcm else 0
        assert report['pcm_peak']>10,'No real PCM'
        w.score_dialog.show();app.processEvents();w.score_dialog.grab().save(str(args.out/'score-dialog.png'))
        w.grab().save(str(args.out/'playing-main.png'))
        w.seq_stop()
        if not wait(lambda:not w.sequence_busy):raise RuntimeError('Stop timeout')
        assert not w.sequence_playing and w.sequence_record['status']=='CONFIRMED'
        report['stop']=w.sequence_record
        frames.clear();pause(.4)
        assert not any(f['kind']==2 and f['payload'][0]&128 for f in frames),'Score continued after stop'
        frames.clear();w.note_on(0);pause(.15);w.note_off(0);pause(.1)
        assert any(f['kind']==2 and f['payload'][0]==188 for f in frames),'Manual note did not resume'
        m=w.audio_page.live_model
        report['health']=dict(crc_errors=m.crc_errors,gaps=m.gaps,losses=m.losses,intentional_pauses=m.discontinuities)
        assert (m.crc_errors,m.gaps,m.losses)==(0,0,0)
        w.seq_play();assert wait(lambda:not w.sequence_busy) and w.sequence_playing
        w._toggle_conn();assert wait(lambda:w.link is None)
        probe=SerialLink(args.port,460800);probe.open()
        try:report['disconnected_seq_ctrl']=probe.read_reg(0x50)
        finally:probe.close()
        assert report['disconnected_seq_ctrl']==0,'Disconnect left sequencer running'
        report['status']='PASS'
    except Exception as exc:report['error']=str(exc)
    finally:
        if w.sequence_playing and not w.sequence_busy:
            w.seq_stop();wait(lambda:not w.sequence_busy)
        w._release_keys()
        if w.live_worker is not None and w.live_worker.isRunning():
            w._toggle_conn();wait(lambda:w.link is None)
        report['errors']=errors
        (args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        (args.out/'wire.bin').write_bytes(wire)
        w.editor._saved=w.editor.document();w.editor_panel.saved=w.editor_panel.document();w.close()
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
