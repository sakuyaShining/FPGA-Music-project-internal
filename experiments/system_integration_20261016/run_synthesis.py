"""Run Gowin synthesis only. Nonzero resource failures are retained as failures."""
from pathlib import Path
import subprocess,sys,json,time,hashlib
R=Path(__file__).resolve().parent
profile=sys.argv[1];assert profile in ('sensor','joint','joint_serial')
D=R/'synthesis'/profile
gw='D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe'
started=time.time()
with (D/'synthesis-console.txt').open('w',encoding='utf-8') as log:
    process=subprocess.Popen([gw,'synth.tcl'],cwd=D,stdout=log,stderr=subprocess.STDOUT)
    try:code=process.wait(timeout=240)
    except subprocess.TimeoutExpired:
        process.kill();process.wait();code='TIMEOUT'
text=(D/'synthesis-console.txt').read_text(encoding='utf-8',errors='replace')
record=dict(exit_code=code,elapsed_seconds=time.time()-started,inputs_manifest_sha256=hashlib.sha256((D/'inputs.json').read_bytes()).hexdigest(),pnr_run=False)
(D/'run.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record));print(text[-1600:])
if code!=0:sys.exit(1)
