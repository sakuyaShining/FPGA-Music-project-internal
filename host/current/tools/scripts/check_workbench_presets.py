"""Compare four real FPGA presets via the performance selector, fixed A4/12.

Clears added spectra for a fair factory-preset comparison; restores the original
preset as a pure preset. Unknown prior spectrum RAM cannot be read/restored.
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
from dsp_gui import PRESETS


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    app=QApplication([]);w=WorkbenchWindow(str(args.out/'display.json'))
    w.resize(1280,720);w.show();app.processEvents()
    if w.cmb_port.findText(args.port)<0:w.cmb_port.addItem(args.port)
    w.cmb_port.setCurrentText(args.port)
    errors=[];records=[];raw=bytearray();original=None;current_frames=[]
    report=dict(status='FAILED',note=69,velocity=12,
        spectrum_metric='relative L1 difference of peak-normalized FFT magnitude, 40-5000Hz',
        pair_threshold=.05,scope='four distinct observed PCM spectra; not full timbre/analog acceptance')
    def wait(predicate,seconds=3):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            app.processEvents()
            if predicate():return True
            QTest.qWait(10)
        return False
    try:
        with patch('dsp_gui.QMessageBox.warning',side_effect=lambda *a:errors.append(str(a[-1]))):
            w._toggle_conn()
        if w.live_worker is None:raise RuntimeError('串口无法打开：'+';'.join(errors))
        w.live_worker.failure.connect(errors.append)
        def collect(batch):
            raw.extend(b''.join(f['raw'] for f in batch['frames']))
            current_frames.extend(batch['frames'])
        w.live_worker.batch.connect(collect)
        if not wait(lambda:w.performance_ready or bool(errors)) or not w.performance_ready:
            raise RuntimeError('自动观察未就绪：'+';'.join(errors))
        original=w.connected_registers['PRESET']&3
        for preset,(name,_) in enumerate(PRESETS):
            before_gap=w.audio_page.live_model.discontinuities
            w.select_performance_preset(preset)
            if not wait(lambda:not w.applying and w.pending_preset is None):raise RuntimeError('应用超时')
            config=w.device_record
            if config.get('status')!='PARTIAL_PARAMETER_CONFIRMED':raise RuntimeError('应用失败：'+str(config))
            if config['readback']['PRESET']!=preset or config['readback']['SPEC_MODE']!=0:
                raise RuntimeError('预设/谱模式回读不符')
            if not wait(lambda:w.audio_page.live_model.discontinuities>before_gap):raise RuntimeError('缺口未标记')
            current_frames.clear()
            w.note_on(4)
            if w.held.get(4)!=69:raise RuntimeError('A4起音未发送')
            wait(lambda:False,.65)
            m=w.audio_page.live_model
            accepted=next((f['timestamp'] for f in current_frames if f['kind']==2 and f['payload'][0]==(0x80|69)),None)
            if accepted is None:raise RuntimeError('没有A4接受起音事件')
            chunks=[]
            for frame in current_frames:
                if frame['kind']!=1:continue
                stride=4 if frame['format']==2 else 1
                samples=np.frombuffer(frame['payload'],dtype='<i2')
                delta=(np.arange(len(samples),dtype=np.int64)*stride+frame['timestamp']-accepted)&0xffffffff
                chunks.append(samples[(delta<1024*4)])
            onset=np.concatenate(chunks) if chunks else np.zeros(0)
            if len(onset)!=1024:raise RuntimeError('缺少对齐起音的完整1024点观察窗')
            x=onset.astype(float)/32768
            rms=float(np.sqrt(np.mean(x*x)))
            if rms<=1e-5:raise RuntimeError('本次起音为静音，不能归一化后伪判音色差异')
            window=np.hanning(1024)
            amp=np.abs(np.fft.rfft(x*window))*2/window.sum()
            db=20*np.log10(np.maximum(amp,1e-6))
            frequencies=np.fft.rfftfreq(1024,1/m.sample_rate)
            record=dict(preset=preset,name=name,configuration=config,fs=m.sample_rate,
                spectrum_hz=frequencies.tolist(),spectrum_db=db.tolist(),
                pcm16=onset.tolist(),rms=rms,window='first 1024 observed samples after FPGA accepted on',
                accepted_on=69 in m.active,crc_errors=m.crc_errors,gaps=m.gaps,losses=m.losses,
                intentional_configuration_gaps=m.discontinuities)
            records.append(record)
            w.grab().save(str(args.out/('preset-%d.png'%preset)))
            w.note_off(4)
            if not wait(lambda:69 not in m.active):raise RuntimeError('A4释放未确认')
            wait(lambda:False,.35)
        pairs=[]
        for i in range(4):
            for j in range(i+1,4):
                f=np.array(records[i]['spectrum_hz']);band=(f>=40)&(f<=5000)
                a=10**(np.array(records[i]['spectrum_db'])[band]/20)
                b=10**(np.array(records[j]['spectrum_db'])[band]/20)
                a=a/a.max();b=b/b.max()
                difference=float(np.sum(np.abs(a-b))/max(np.sum(a),np.sum(b)))
                pairs.append(dict(a=PRESETS[i][0],b=PRESETS[j][0],difference=difference,
                                  distinct=difference>=report['pair_threshold']))
        report.update(profiles=records,pairs=pairs,errors=errors)
        valid=all(r['accepted_on'] and not any(r[k] for k in ('crc_errors','gaps','losses')) for r in records)
        report['status']='PASS' if valid and all(p['distinct'] for p in pairs) and not errors else 'FAILED'
    except Exception as exc:
        errors.append(str(exc));report.update(profiles=records,errors=errors)
    finally:
        if w.held:w._release_keys();wait(lambda:False,.25)
        if original is not None and w.performance_ready and not w.applying:
            w.select_performance_preset(original);wait(lambda:not w.applying)
            restored=w.device_record or {}
            if restored.get('status')=='PARTIAL_PARAMETER_CONFIRMED' and restored.get('readback',{}).get('PRESET')==original:
                report['restoration']='original preset restored; added spectrum cleared, unknown spectrum not restorable'
            else:
                report['restoration']='FAILED: device state unknown; no complete restoration claimed'
                report['status']='FAILED'
        if w.live_worker is not None and w.live_worker.isRunning():
            w.live_worker.stop();w.live_worker.wait(3000);app.processEvents()
        (args.out/'stream.bin').write_bytes(bytes(raw))
        (args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        w.editor._saved=w.editor.document();w.close()
    print(json.dumps({k:v for k,v in report.items() if k!='profiles'},ensure_ascii=False))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':sys.exit(main())
