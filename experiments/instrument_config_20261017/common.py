from pathlib import Path
import subprocess,hashlib,json
R=Path(__file__).resolve().parent;E=R/'evidence';E.mkdir(exist_ok=True)
IV='D:/iverilog/bin/iverilog.exe';VVP='D:/iverilog/bin/vvp.exe'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def sources():return list((R/'src').glob('*.v'))+list((R/'rtl').glob('*.v'))
def run(cmd,name,cwd=None,timeout=240):
    out=subprocess.run(cmd,cwd=cwd or R,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
    log=out.stdout+out.stderr;(E/(name+'.log')).write_text(log,encoding='utf-8');assert out.returncode==0,(name,log)
    if name.startswith('run'):print(log.strip(),flush=True)
    return log
