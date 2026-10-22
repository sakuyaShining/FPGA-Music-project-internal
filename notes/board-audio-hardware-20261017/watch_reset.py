"""Observe a user S1 reset during repeating bounded dual-layer tests."""
from pathlib import Path
import datetime,hashlib,importlib.util,json,time
import serial
from serial.tools import list_ports
P=Path(__file__).resolve().parents[2];R=P/'experiments/board_audio_20261017';N=Path(__file__).resolve().parent
S=Path((N/'LATEST.txt').read_text(encoding='utf-8'));D=S/'physical-reset';D.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
checker=R/'package/board_check.py';manifest=json.loads((R/'package/manifest.json').read_text(encoding='utf-8'));assert sha(checker)==manifest['files']['board_check.py']
spec=importlib.util.spec_from_file_location('frozen_checker',checker);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
ports=[p for p in list_ports.comports() if p.vid==0x0403 and p.pid==0x6010 and p.serial_number=='2025030317B'];assert len(ports)==1
record=dict(status='waiting for physical S1',time=datetime.datetime.now().astimezone().isoformat(),script_sha256=sha(Path(__file__).resolve()),checker_sha256=sha(checker),hardware_tested=True,flash_read_or_written=False,observations=[],uart_errors=[])
with serial.Serial(ports[0].device,115200,timeout=.1,write_timeout=1) as transport:
    b=mod.Board(transport);record['identity']=b.identify();t0=time.monotonic();deadline=t0+75;started=False;last_held=None
    try:
        baseline=b.snapshot();assert baseline['active']==0 and baseline['ack']>0
        while time.monotonic()<deadline:
            try:
                st=b.status();snap_time=time.monotonic();snap=b.snapshot()
            except RuntimeError as exc:
                record['uart_errors'].append(dict(seconds=time.monotonic()-t0,error=str(exc)))
                transport.reset_input_buffer();time.sleep(.1);b.identify();continue
            item=dict(seconds=snap_time-t0,status=st,snapshot=snap);record['observations'].append(item)
            if started and st['case']==0 and not st['armed'] and snap['ack']==0:
                record['reset_observed']=item;record['last_held_before_reset']=last_held
                assert last_held is not None,'no dual-layer held sample before reset'
                while not b.status()['ready']:
                    assert time.monotonic()<deadline;time.sleep(.05)
                time.sleep(.15);values=b.capture();raw=D/'post-reset.s24le';raw.write_bytes(b''.join((v&0xffffff).to_bytes(3,'little') for v in values))
                record['post_reset_audio']=mod.analyze(values)
                if record['post_reset_audio']['peak']==0:record['post_reset_audio']['peak_hz']=None
                record['raw_sha256']=sha(raw);record['post_reset_snapshot']=b.snapshot();record['post_reset_status']=b.status()
                assert max(map(abs,values))==0,'PCM not silent after reset'
                assert record['post_reset_snapshot']['active']==0 and record['post_reset_snapshot']['ack']==0
                assert not record['post_reset_status']['armed'] and not record['post_reset_status']['bound'] and not record['post_reset_status']['fault']
                record['held_sample_age_seconds']=item['seconds']-last_held['seconds']
                record['held_immediately_before_reset_observed']=record['held_sample_age_seconds']<4.5
                record['status']='PASS physical reset recovery and silent PCM; sampled overlap only'
                print(record['status'],flush=True);break
            assert not st['fault'],'board fault during reset observation'
            if st['bound'] and st['running'] and bin(snap['active']).count('1')==2:last_held=item
            if st['ready'] and not st['running'] and not st['bound']:
                b.start_case(3);started=True;print('dual-layer burst started; S1 may be pressed while audible',flush=True)
            time.sleep(.03)
        else:record['status']='NOT VERIFIED: no physical reset observed before deadline'
    except Exception as exc:
        record['status']='FAIL';record['error']=str(exc);raise
    finally:
        try:
            transport.reset_input_buffer();b.write(0xc2,0);time.sleep(.12);record['final_status']=b.status();record['final_snapshot']=b.snapshot()
        finally:(D/'result.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k not in ('observations','last_held_before_reset','reset_observed')},indent=2))
