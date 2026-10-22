"""Record read-only host/device preflight; does not open UART or program FPGA."""
from pathlib import Path
import datetime,hashlib,json,subprocess,zipfile
P=Path(__file__).resolve().parents[2];R=P/'experiments/board_audio_20261017'
N=P/'notes/board-audio-hardware-20261017';N.mkdir(exist_ok=True)
S=N/datetime.datetime.now().strftime('%Y%m%d-%H%M%S');S.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
delivery=json.loads((R/'delivery.json').read_text(encoding='utf-8'))
verified={}
for group in ('source_files','evidence'):
    for rel,digest in delivery[group].items():
        assert sha(R/rel)==digest,(group,rel)
        verified[rel]=digest
for rel,digest in delivery['design_documents'].items():assert sha(P/rel)==digest,rel
package=json.loads((R/'package/manifest.json').read_text(encoding='utf-8'))
assert sha(R/'package/manifest.json')==delivery['package_manifest_sha256']
for rel,digest in package['files'].items():assert sha(R/'package'/rel)==digest,rel
backup_paths=[R/'delivery.json',R/'project/CURRENT.md',R/'project/state.json',R/'package/manifest.json',*(R/'package'/rel for rel in package['files']),*(P/rel for rel in delivery['design_documents'])]
manifest={p.relative_to(P).as_posix():sha(p) for p in backup_paths}
with zipfile.ZipFile(S/'before-hardware.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in backup_paths:z.write(p,p.relative_to(P).as_posix())
with zipfile.ZipFile(S/'before-hardware.zip') as z:
    assert z.testzip() is None
    for rel,digest in manifest.items():assert hashlib.sha256(z.read(rel)).hexdigest()==digest
(S/'backup-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
def capture(name,args):
    p=subprocess.run(args,cwd=S,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
    (S/(name+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8')
    return dict(command=args,returncode=p.returncode,log_sha256=sha(S/(name+'.log')))
cli='D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/Programmer/bin/programmer_cli.exe'
commands={}
commands['usb-ports']=capture('usb-ports',['powershell','-NoProfile','-Command',"Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB*' -or $_.Class -eq 'Ports' } | Select-Object Status,Class,FriendlyName,InstanceId | ConvertTo-Json -Depth 3"])
commands['serial-ports']=capture('serial-ports',['C:/Program Files/python/python.exe','-m','serial.tools.list_ports','-v'])
commands['programmer-help']=capture('programmer-help',[cli,'--help'])
commands['cables']=capture('cables',[cli,'--scan-cables'])
record=dict(status='read-only preflight recorded; inspect device results before hardware actions',time=datetime.datetime.now().astimezone().isoformat(),source_delivery_sha256=sha(R/'delivery.json'),verified_files=len(verified),package=package,backup_zip_sha256=sha(S/'before-hardware.zip'),commands=commands,serial_opened=False,fpga_programmed=False,flash_read_or_written=False)
(S/'preflight.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
(N/'LATEST.txt').write_text(str(S),encoding='utf-8')
print(json.dumps(dict(directory=str(S),verified_files=len(verified),returncodes={k:v['returncode'] for k,v in commands.items()},programmed=False)))
