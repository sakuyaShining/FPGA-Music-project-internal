from pathlib import Path
import subprocess,hashlib,json
R=Path(__file__).resolve().parent;E=R/'evidence';E.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
IV='D:/iverilog/bin/iverilog.exe';VVP='D:/iverilog/bin/vvp.exe'
def sources():return list((R/'src').glob('*.v'))+[p for p in (R/'rtl').glob('*.v') if p.name!='board_mute_top.v']
def run(cmd,name,cwd=R,timeout=240):
    out=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
    log=out.stdout+out.stderr;(E/(name+'.log')).write_text(log,encoding='utf-8');assert out.returncode==0,(name,log)
    if name.startswith('run'):print(log.strip(),flush=True)
    return log
