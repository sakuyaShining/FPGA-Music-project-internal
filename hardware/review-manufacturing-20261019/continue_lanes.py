"""Bounded, sequential local planning/native application for pending MUX lanes."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from native_review import ROOT

OUT=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')
planner='C:/Users/Sakuya/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
results=[]
for lane in [int(x) for x in sys.argv[1:]] or list(range(1,6)):
    preferred=[];attempted=set();success=False
    for attempt in range(6):
        order=tuple(preferred)
        if order in attempted:break
        attempted.add(order)
        log=OUT/f'lane{lane}-attempt{attempt}.log'
        with log.open('w',encoding='utf-8') as stream:
            p=subprocess.run([planner,'-X','utf8',str(ROOT/'plan_lane.py'),str(lane),*preferred],stdout=stream,stderr=subprocess.STDOUT)
        tail=log.read_text(encoding='utf-8')
        print('\n'.join(tail.splitlines()[-7:]),flush=True)
        if p.returncode==0:success=True;break
        failed=re.findall(r'Locally sealed escape: (L\d_M\d\d)',tail)
        if not failed:break
        net=failed[-1];preferred=[net]+[n for n in preferred if n!=net]
    if not success:
        results.append({'lane':lane,'status':'planning_failed_no_native_change','log':str(log)})
        continue
    plan=ROOT/f'grid-plan-lane{lane}.json'
    if not plan.exists():
        results.append({'lane':lane,'status':'no_pending_nets'});continue
    subprocess.run([sys.executable,'-X','utf8',str(ROOT/'apply_grid_plan.py'),str(plan)],check=True)
    subprocess.run([sys.executable,'-X','utf8',str(ROOT/'check_route_stage.py'),f'grid-lane{lane}'],check=True)
    drc=json.loads((ROOT/'pcb-drc.json').read_text(encoding='utf-8'))
    foreign=[x for c in drc if c['name']=='Clearance Error' for x in c['list'] if 'Copper Region(Filled)' not in x['name']]
    if foreign:raise RuntimeError('New physical clearance error; inspect saved evidence before next stage')
    pending=[x['name'] for c in drc if c['name']=='Connection Error' for x in c['list']]
    target=json.loads(plan.read_text(encoding='utf-8'))['nets']
    unresolved=sorted(set(target)&set(pending))
    results.append({'lane':lane,'status':'applied_and_checked','still_unconnected_target_nets':unresolved,
                    'native_drc':[(c['name'],c.get('count')) for c in drc]})
    (ROOT/'lane-pipeline-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
(ROOT/'lane-pipeline-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print('LANE PIPELINE',results,flush=True)
