"""Supplement case 5: capture onset, transition and final silence separately."""
from pathlib import Path
import datetime,hashlib,importlib.util,json,time,math
import serial
from serial.tools import list_ports
P=Path(__file__).resolve().parents[2];R=P/'experiments/board_audio_20261017';N=Path(__file__).resolve().parent
S=Path((N/'LATEST.txt').read_text(encoding='utf-8'));D=S/'short-note-windows';D.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
checker=R/'package/board_check.py';manifest=json.loads((R/'package/manifest.json').read_text(encoding='utf-8'))
assert sha(checker)==manifest['files']['board_check.py']
spec=importlib.util.spec_from_file_location('frozen_checker',checker);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
ports=[p for p in list_ports.comports() if p.vid==0x0403 and p.pid==0x6010 and p.serial_number=='2025030317B'];assert len(ports)==1
record=dict(status='in progress',time=datetime.datetime.now().astimezone().isoformat(),script_sha256=sha(Path(__file__).resolve()),checker_sha256=sha(checker),hardware_tested=True,flash_read_or_written=False,windows=[])
with serial.Serial(ports[0].device,115200,timeout=.2,write_timeout=1) as transport:
    b=mod.Board(transport);record['identity']=b.identify()
    try:
        for label,delay in [('onset',0.0),('transition',.065),('quiet',.25)]:
            before=b.status();assert before['ready'] and not before['fault'] and not before['bound']
            baseline=b.snapshot();assert baseline['active']==0
            t0=time.monotonic();b.start_case(5);confirmed=time.monotonic();time.sleep(delay)
            trigger=time.monotonic();values=b.capture();received=time.monotonic()
            raw=D/(label+'.s24le');raw.write_bytes(b''.join((v&0xffffff).to_bytes(3,'little') for v in values))
            stats=mod.analyze(values)
            if stats['peak']==0:stats['peak_hz']=None
            chunks=[math.sqrt(sum(v*v for v in values[i:i+256])/256) for i in range(0,2048,256)]
            item=dict(label=label,host_delay_after_confirmation=delay,confirmation_seconds=confirmed-t0,request_seconds_after_confirmation=trigger-confirmed,receive_seconds_after_confirmation=received-confirmed,audio=stats,chunk_rms=chunks,raw_file=raw.name,raw_sha256=sha(raw),snapshot=b.snapshot())
            record['windows'].append(item)
            b.write(0xc2,0);time.sleep(.12);item['after']=b.snapshot();item['status_after']=b.status()
            assert item['after']['active']==0 and not item['status_after']['armed'] and not item['status_after']['fault']
            assert ((item['after']['on']-baseline['on'])&0xffff)==1 and ((item['after']['off']-baseline['off'])&0xffff)==1
            assert item['after']['period_min']==item['after']['period_max']==512
            if label=='onset':assert stats['nonzero']>0,'onset was not captured'
            if label=='quiet':assert stats['peak']==0,'short-note audio remained after release'
        record['status']='PASS observed onset and post-release silence; transition timing is host approximate'
    except Exception as exc:
        record['status']='FAIL';record['error']=str(exc);raise
    finally:
        b.write(0xc2,0);time.sleep(.12);record['final_status']=b.status();record['final_snapshot']=b.snapshot()
        (D/'result.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k not in ('identity','final_snapshot')},indent=2))
