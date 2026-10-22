"""Recheck timed-out regctl test 5 without replacing first full-run evidence."""
import json,shutil,subprocess,sys,time
from pathlib import Path

root=Path(__file__).resolve().parents[2]
tree=root/'sim_build/board_diag_20261009/diagnostic_v3'
original=tree/'sim_build/regress/09_regctl'
target=tree/'sim_build/regress/09_regctl_recheck'
if target.exists():raise SystemExit('Recheck already exists; preserve evidence')
shutil.copytree(original,target)
(target/'rc_seq.txt').unlink()
started=time.monotonic()
with (target/'sim-test5.log').open('wb') as log:
    try:
        result=subprocess.run(['D:/iverilog/bin/vvp.exe','sim.vvp','+test=5'],cwd=target,
                              stdout=log,stderr=subprocess.STDOUT,timeout=2400)
    except subprocess.TimeoutExpired:
        raise SystemExit('Recheck timeout 2400s; evidence retained')
output=(target/'sim-test5.log').read_text(encoding='utf-8',errors='replace')
rows=(target/'rc_seq.txt').read_text().splitlines()
complete=result.returncode==0 and 'rc_seq.txt' in output and '[TIMEOUT]' not in output
complete=complete and len(rows)==12000 and all(len(row.split())==3 for row in rows)
meta=dict(returncode=result.returncode,rows=len(rows),complete=complete,
          seconds=round(time.monotonic()-started,3),timeout_seconds=2400)
(target/'run.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
print(meta,flush=True)
if not complete:raise SystemExit('Incomplete simulation; judge not invoked')
judge=subprocess.run([sys.executable,str(tree/'tools/scripts/reg_ctl_check.py'),
                      '--simdir',str(target)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(target/'judge.log').write_bytes(judge.stdout)
print(judge.stdout.decode('utf-8',errors='replace'),flush=True)
raise SystemExit(judge.returncode)
