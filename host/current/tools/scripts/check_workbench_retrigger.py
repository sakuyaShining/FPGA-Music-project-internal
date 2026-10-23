"""Real UART rapid re-press check, comparing event-aligned early PCM energy.

Does not synthesize audio. Current sound is preserved unless --all-presets is
explicit; that option selects factory sounds and clears unknown spectrum RAM.
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
from piano_keyboard import INDEX
from live_visualizer import FS


def measurements(frames, note):
    starts=[f['timestamp'] for f in frames if f['kind']==2 and f['payload'][0]==(128|note)]
    stops=[f['timestamp'] for f in frames if f['kind']==2 and f['payload'][0]==note]
    if len(starts)!=2 or len(stops)!=2:
        raise RuntimeError('Expected exactly two accepted on/off pairs: %r / %r'%(starts,stops))
    results=[]
    # 8..48 ms: past attack, before the deliberate 160ms release.
    low=round(.008*FS);high=low+512*4
    for stamp in starts:
        pieces=[]
        for f in frames:
            if f['kind']!=1:continue
            if f['format']!=2:raise RuntimeError('Expected decimate4 PCM16')
            samples=np.frombuffer(f['payload'],dtype='<i2')
            delta=(np.arange(len(samples),dtype=np.int64)*4+f['timestamp']-stamp)&0xffffffff
            pieces.append(samples[(delta>=low)&(delta<high)])
        x=np.concatenate(pieces) if pieces else np.zeros(0)
        if len(x)!=512:raise RuntimeError('Incomplete event-aligned observation window: %d'%len(x))
        results.append(float(np.sqrt(np.mean((x.astype(float)/32768)**2))))
    return dict(accepted_on=starts,accepted_off=stops,rms=results,
        gap_ms=((starts[1]-stops[0])&0xffffffff)*1000/FS,ratio=results[1]/max(results[0],1e-12))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',default='COM6')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--all-presets',action='store_true')
    parser.add_argument('--hold-ms',type=int,default=160,choices=range(60,501),metavar='60..500')
    parser.add_argument('--offset',type=int,default=0,choices=range(25),metavar='0..24')
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    app=QApplication([]);w=WorkbenchWindow(str(args.out/'display.json'))
    w.show();app.processEvents();w.cmb_port.setCurrentText(args.port)
    errors=[];frames=[];wire=bytearray();trials=[];original=None
    report=dict(status='FAILED',window='512 PCM16 samples, 8ms after accepted on',
        note=60+args.offset,velocity=12,hold_ms=args.hold_ms,threshold_ratio=.65,
        scope='early PCM energy on rapid repeated note; not analog listening acceptance')
    def wait(predicate,seconds=3):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            app.processEvents()
            if predicate():return True
            QTest.qWait(1)
        return False
    def collect(batch):
        frames.extend(batch['frames']);wire.extend(b''.join(f['raw'] for f in batch['frames']))
    def pause(seconds):wait(lambda:False,seconds)
    try:
        with patch('dsp_gui.QMessageBox.warning',side_effect=lambda *a:errors.append(str(a[-1]))):w._toggle_conn()
        if w.live_worker is None:raise RuntimeError('Port did not open: '+str(errors))
        w.live_worker.batch.connect(collect);w.live_worker.failure.connect(errors.append)
        if not wait(lambda:w.performance_ready or errors) or not w.performance_ready:raise RuntimeError(str(errors))
        report['identity']=dict(w.connected_registers)
        original=w.connected_registers['PRESET']&3
        for preset in (range(4) if args.all_presets else [original]):
            if args.all_presets:
                w.select_performance_preset(preset)
                if not wait(lambda:not w.applying and w.pending_preset is None):raise RuntimeError('Apply timed out')
                if w.device_record['status']=='FAILED':raise RuntimeError(str(w.device_record))
            for gap in (.005,.020,.060):
                pause(1.5)  # Allow release to finish before the first baseline note.
                frames.clear();before=w.audio_page.live_model
                counts=(before.gaps,before.crc_errors,before.losses,before.discontinuities)
                w.note_on(INDEX[args.offset]);pause(args.hold_ms/1000);w.note_off(INDEX[args.offset]);pause(gap)
                w.note_on(INDEX[args.offset]);pause(args.hold_ms/1000);w.note_off(INDEX[args.offset]);pause(.150)
                result=measurements(frames,60+args.offset)
                result.update(preset=preset,requested_gap_ms=gap*1000)
                result['transport_clean']=counts==(before.gaps,before.crc_errors,before.losses,before.discontinuities)
                result['pass']=result['transport_clean'] and min(result['rms'])>1e-5 and result['ratio']>=.65
                trials.append(result)
                print(json.dumps(result),flush=True)
        report['status']='PASS' if trials and all(t['pass'] for t in trials) else 'FAIL'
    except Exception as exc:report['error']=str(exc)
    finally:
        w._release_keys()
        if args.all_presets and original is not None and w.performance_ready:
            wait(lambda:not w.audio_page.live_model.active)
            w.select_performance_preset(original);wait(lambda:not w.applying and w.pending_preset is None)
        if w.live_worker is not None and w.live_worker.isRunning():
            w._toggle_conn();wait(lambda:w.live_worker is None or not w.live_worker.isRunning())
            app.processEvents()
        report['trials']=trials;report['errors']=errors
        (args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        (args.out/'wire.bin').write_bytes(wire)
        w.editor._saved=w.editor.document();w.editor_panel.saved=w.editor_panel.document();w.close()
    print('RESULT retrigger='+report['status'],flush=True)
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
