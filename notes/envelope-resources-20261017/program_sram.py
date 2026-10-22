"""Bound to the audited configuration diagnostic. SRAM Program operation2 only."""
from pathlib import Path
import json,hashlib,subprocess,datetime
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent;R=P/'experiments/envelope_resources_20261017'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
a=read(R/'evidence/board-build-audit.json');assert a['status'].startswith('PASS') and a['slack_ns']['Setup']>=0 and a['slack_ns']['Hold']>=0
for group in ('core','serial','gui'):assert read(R/'evidence'/('matrix-'+group+'.json'))['status'].startswith('PASS')
assert read(R/'evidence/shared-envelope.json')['status'].startswith('PASS')
b=read(R/'build_board/run.json')
for name,item in b['inputs'].items():assert sha(R/item['source'])==sha(R/'build_board'/name)==item['sha256']
manifest=read(R/'package/manifest.json');assert manifest['device']=='GW2AR-LV18QN88C8/I7'
for name,h in manifest['files'].items():assert sha(R/'package'/name)==h
fs=R/'package/config-sram.fs';assert sha(fs)==a['bitstream_sha256']
S=N/('hardware-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));S.mkdir()
cli='D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/Programmer/bin/programmer_cli.exe'
def command(name,args):
 out=subprocess.run(args,cwd=S,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
 text=out.stdout+out.stderr;(S/(name+'.log')).write_text(text,encoding='utf-8');print(text,flush=True);assert out.returncode==0,(name,out.returncode);return text
helptext=command('programmer-help',[cli,'--help']);assert '2: SRAM Program;' in helptext
cables=command('cables',[cli,'--scan-cables']);assert 'USB Debugger A/0/' in cables
scan=command('jtag-scan',[cli,'--scan']);assert 'Family: GW2AR' in scan and '0x0000081B' in scan and '1 device(s) found!' in scan
record=dict(time=datetime.datetime.now().astimezone().isoformat(),operation=2,mode='SRAM only',bitstream_sha256=sha(fs),board_audit_sha256=sha(R/'evidence/board-build-audit.json'),script_sha256=sha(Path(__file__).resolve()),flash_read_or_written=False,status='attempt recorded before invoking programmer')
args=[cli,'--device','GW2AR-18C','--operation_index','2','--chain_size','1','--chain_index','0','--channel','0','--fsFile',str(fs)];record['command']=args
(S/'program-attempt.json').write_text(json.dumps(record,indent=2),encoding='utf-8');(N/'latest-hardware.txt').write_text(str(S),encoding='utf-8')
log=command('program-sram',args);assert 'failed' not in log.lower() and 'error' not in log.lower()
record.update(status='SRAM command exited0; UART configuration/audio identity still required',program_log_sha256=sha(S/'program-sram.log'))
(S/'program-result.json').write_text(json.dumps(record,indent=2),encoding='utf-8');print('SRAM operation2 completed; Flash untouched')
