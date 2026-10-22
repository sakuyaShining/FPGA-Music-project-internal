"""Read state/PCM after the user's S1 action; never arms audio."""
from pathlib import Path
import datetime,hashlib,importlib.util,json,time
import serial
from serial.tools import list_ports
P=Path(__file__).resolve().parents[2];R=P/'experiments/board_audio_20261017';N=Path(__file__).resolve().parent
S=Path((N/'LATEST.txt').read_text(encoding='utf-8'));D=S/'after-user-reset';D.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
checker=R/'package/board_check.py';manifest=json.loads((R/'package/manifest.json').read_text(encoding='utf-8'));assert sha(checker)==manifest['files']['board_check.py']
spec=importlib.util.spec_from_file_location('frozen_checker',checker);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
ports=[p for p in list_ports.comports() if p.vid==0x0403 and p.pid==0x6010 and p.serial_number=='2025030317B'];assert len(ports)==1
record=dict(time=datetime.datetime.now().astimezone().isoformat(),script_sha256=sha(Path(__file__).resolve()),checker_sha256=sha(checker),hardware_tested=True,user_report='已按下',audio_armed_by_this_script=False,flash_read_or_written=False)
try:
    with serial.Serial(ports[0].device,115200,timeout=.2,write_timeout=1) as transport:
        b=mod.Board(transport);transport.reset_input_buffer();record['identity']=b.identify()
        deadline=time.monotonic()+3
        while not b.status()['ready']:
            assert time.monotonic()<deadline;time.sleep(.1)
        record['state']=b.status();record['snapshot']=b.snapshot();values=b.capture()
        raw=D/'capture.s24le';raw.write_bytes(b''.join((v&0xffffff).to_bytes(3,'little') for v in values));record['raw_sha256']=sha(raw);record['audio']=mod.analyze(values)
        if record['audio']['peak']==0:record['audio']['peak_hz']=None
        st=record['state'];snap=record['snapshot']
        assert st['case']==0 and not st['armed'] and not st['running'] and not st['bound'] and not st['fault'],'reset state was not observed'
        assert snap['ack']==snap['on']==snap['off']==snap['active']==0,'event counters were not reset'
        assert snap['period_min']==snap['period_max']==512 and max(map(abs,values))==0
        record['status']='PASS S1 reset state and silent PCM after user action; held overlap not captured'
except Exception as exc:
    record['status']='FAIL';record['error']=str(exc);raise
finally:(D/'result.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record,indent=2))
