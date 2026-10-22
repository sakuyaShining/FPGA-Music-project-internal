from pathlib import Path
import hashlib,json,subprocess
R=Path(__file__).resolve().parent;E=R/'evidence'
IV='D:/iverilog/bin/iverilog.exe';VVP='D:/iverilog/bin/vvp.exe'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def sources():return list((R/'engine/src').glob('*.v'))+list((R/'engine/rtl').glob('*.v'))+list((R/'rtl').glob('*.v'))
def run(cmd,label,timeout=240):
 out=subprocess.run(cmd,cwd=R,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
 (E/(label+'.log')).write_text(out.stdout+out.stderr,encoding='utf-8')
 assert out.returncode==0,(label,out.stdout,out.stderr)
 return out.stdout
