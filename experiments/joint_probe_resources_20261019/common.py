from pathlib import Path
import subprocess,hashlib,json
R=Path(__file__).resolve().parent;E=R/'evidence';E.mkdir(exist_ok=True)
IV='D:/iverilog/bin/iverilog.exe';VVP='D:/iverilog/bin/vvp.exe'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def sources():return list((R/'engine/src').glob('*.v'))+list((R/'engine/rtl').glob('*.v'))+list((R/'rtl').glob('*.v'))
def run(cmd,name,cwd=None,timeout=240):
    # Preserve the exact compiler/simulator inputs and detect mid-run edits.
    paths=[Path(p) for p in cmd[1:] if not p.startswith(('-','+')) and Path(p).is_file() and
           (cmd[0]!=IV or Path(p).suffix in ('.v','.vh','.hex'))]
    if cmd[0]==IV:
        paths+=list((R/'engine/src').glob('*.hex'))+list((R/'engine/src').glob('*.vh'))+list(R.glob('*.hex'))+list(R.glob('*.vh'))
    before={str(p.resolve()):sha(p) for p in paths}
    out=subprocess.run(cmd,cwd=cwd or R,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
    assert all(sha(Path(p))==h for p,h in before.items()),('inputs changed during execution',name)
    (E/(name+'-inputs.json')).write_text(json.dumps(dict(command=cmd,cwd=str(cwd or R),inputs=before,returncode=out.returncode),indent=2),encoding='utf-8')
    log=out.stdout+out.stderr;(E/(name+'.log')).write_text(log,encoding='utf-8');assert out.returncode==0,(name,log)
    if name.startswith('run'):print(log.strip(),flush=True)
    return log
