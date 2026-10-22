"""Synthesis only; no GPIO constraints, PnR or download."""
from pathlib import Path
import subprocess,sys,json,time,hashlib
R=Path(__file__).resolve().parent
profile=sys.argv[1];assert profile in ('bridge','owned_joint','owned_serial')
D=R/'synthesis'/profile
gw='D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe'
start=time.time()
with (D/'synthesis-console.txt').open('w',encoding='utf-8') as log:
    p=subprocess.Popen([gw,'synth.tcl'],cwd=D,stdout=log,stderr=subprocess.STDOUT)
    try:code=p.wait(timeout=240)
    except subprocess.TimeoutExpired:p.kill();p.wait();code='TIMEOUT'
result=dict(exit_code=code,elapsed_seconds=time.time()-start,inputs_sha256=hashlib.sha256((D/'inputs.json').read_bytes()).hexdigest(),pnr_run=False)
(D/'run.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result));print((D/'synthesis-console.txt').read_text(encoding='utf-8',errors='replace')[-1000:])
if code!=0:sys.exit(1)
