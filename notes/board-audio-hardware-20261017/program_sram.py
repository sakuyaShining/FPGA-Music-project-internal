"""This entry only permits the verified audio diagnostic's SRAM Program (2)."""
from pathlib import Path
import datetime,hashlib,json,subprocess
P=Path(__file__).resolve().parents[2];R=P/'experiments/board_audio_20261017'
N=Path(__file__).resolve().parent;S=Path((N/'LATEST.txt').read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
preflight=json.loads((S/'preflight.json').read_text(encoding='utf-8'))
assert preflight['commands']['cables']['returncode']==0
assert 'USB Debugger A/0/' in (S/'cables.log').read_text(encoding='utf-8')
assert '2: SRAM Program;' in (S/'programmer-help.log').read_text(encoding='utf-8')
assert sha(R/'delivery.json')==preflight['source_delivery_sha256']
delivery=json.loads((R/'delivery.json').read_text(encoding='utf-8'))
for group in ('source_files','evidence'):
    for rel,digest in delivery[group].items():assert sha(R/rel)==digest,(group,rel)
manifest=json.loads((R/'package/manifest.json').read_text(encoding='utf-8'))
assert manifest['device']=='GW2AR-LV18QN88C8/I7' and manifest['profile']==0x72
for rel,digest in manifest['files'].items():assert sha(R/'package'/rel)==digest,rel
cli='D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/Programmer/bin/programmer_cli.exe'
def command(name,args):
    out=subprocess.run(args,cwd=S,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
    log=out.stdout+out.stderr;(S/(name+'.log')).write_text(log,encoding='utf-8')
    print(log,flush=True)
    assert out.returncode==0,(name,out.returncode)
    return log
scan=command('jtag-scan',[cli,'--scan'])
assert 'Family: GW2AR' in scan and '0x0000081B' in scan and '1 device(s) found!' in scan
assert not (S/'program-attempt.json').exists(),'use a fresh preflight directory for a new attempt'
fs=R/'package/board-audio-sram.fs'
args=[cli,'--device','GW2AR-18C','--operation_index','2','--chain_size','1','--chain_index','0','--channel','0','--fsFile',str(fs)]
record=dict(time=datetime.datetime.now().astimezone().isoformat(),command=args,operation=2,mode='SRAM only',bitstream_sha256=sha(fs),preflight_sha256=sha(S/'preflight.json'),script_sha256=sha(Path(__file__).resolve()),flash_read_or_written=False,status='attempt recorded before invoking programmer')
(S/'program-attempt.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
log=command('program-sram',args)
assert 'failed' not in log.lower() and 'error' not in log.lower(),log
record['status']='SRAM command exited 0; UART profile identity still required'
record['program_log_sha256']=sha(S/'program-sram.log')
(S/'program-result.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print('SRAM operation completed; Flash untouched')
