"""Run the frozen package checker on the detected FTDI channel B, sequentially."""
from pathlib import Path
import datetime,hashlib,json,subprocess,sys
from serial.tools import list_ports
P=Path(__file__).resolve().parents[2];R=P/'experiments/board_audio_20261017'
N=Path(__file__).resolve().parent;S=Path((N/'LATEST.txt').read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
program=json.loads((S/'program-result.json').read_text(encoding='utf-8'))
assert program['operation']==2 and sha(R/'package/board-audio-sram.fs')==program['bitstream_sha256']
manifest=json.loads((R/'package/manifest.json').read_text(encoding='utf-8'))
checker=R/'package/board_check.py';assert sha(checker)==manifest['files']['board_check.py']
ports=[p for p in list_ports.comports() if p.vid==0x0403 and p.pid==0x6010 and p.serial_number=='2025030317B']
assert len(ports)==1,[(p.device,p.hwid) for p in list_ports.comports()]
case=int(sys.argv[1]) if len(sys.argv)>1 else None
assert case is None or case in range(1,7)
D=S/(('case'+str(case)) if case else 'identity')
assert not D.exists(),'preserve earlier result: use a new result directory'
D.mkdir()
args=[sys.executable,str(checker),'--port',ports[0].device]
if case:args+=['--case',str(case),'--output',str(D)]
record=dict(time=datetime.datetime.now().astimezone().isoformat(),command=args,port_hwid=ports[0].hwid,script_sha256=sha(Path(__file__).resolve()),checker_sha256=sha(checker),bitstream_sha256=program['bitstream_sha256'],case=case,status='attempt recorded before opening UART',flash_read_or_written=False)
(D/'attempt.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
out=subprocess.run(args,cwd=P,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
log=out.stdout+out.stderr;(D/'console.log').write_text(log,encoding='utf-8')
record.update(returncode=out.returncode,console_sha256=sha(D/'console.log'),status='checker returned '+str(out.returncode))
if (D/'result.json').exists():record['result_sha256']=sha(D/'result.json')
(D/'run.json').write_text(json.dumps(record,indent=2),encoding='utf-8');print(log,flush=True)
raise SystemExit(out.returncode)
