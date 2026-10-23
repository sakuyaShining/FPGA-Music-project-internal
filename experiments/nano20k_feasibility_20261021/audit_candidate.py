"""Record actual build outcomes; a failed router is never qualified by net count."""
from common import *
import re,sys,xml.etree.ElementTree as ET
from audit_timing import audit,rows
label=sys.argv[1];assert re.fullmatch(r'build_nominal_v\d+',label)
up=json.loads((R/'upstream.json').read_text(encoding='utf-8'));U=Path(up['root'])
assert sha(U/'delivery.json')==up['delivery_sha256']
for rel,h in up['files'].items():assert sha(U/rel)==h,rel
changed=[];frozen=[]
for rel,h in up['files'].items():
    if Path(rel).parts[0] in ('engine','rtl'):
        if sha(R/rel)!=h:changed.append(rel)
        else:frozen.append(rel)
assert changed==['rtl/joint_timing_top.v'],changed
for rel in ('constraints/sdram_board.cst','constraints/sdram_board.sdc','reference/stress.sdc'):
    assert sha(R/rel)==sha(U/rel),rel
models={};paths=[Path(__file__).resolve(),R/'common.py',R/'audit_timing.py',R/'upstream.json']
for name in ('scan-model','joint-model'):
    p=E/(name+'.json');d=json.loads(p.read_text(encoding='utf-8'));assert d['status'].startswith('PASS')
    for rel,h in d['inputs'].items():assert sha(R/rel)==h,(name,rel)
    models[name]=d['status'];paths.append(p)
builds={}
for D in sorted(R.glob('build_nominal_v*')):
    p=D/'run.json'
    if not p.exists():continue
    d=json.loads(p.read_text(encoding='utf-8'))
    for name,v in d['inputs'].items():assert sha(D/name)==v['sha256'],(D.name,name)
    if D.name==label:
        for name,v in d['inputs'].items():assert sha(R/v['source'])==v['sha256'],name
    assert sha(D/'board.gprj')==d['project_sha256'] and sha(D/'build.tcl')==d['tcl_sha256']
    log=(D/'console.log').read_text(encoding='utf-8',errors='replace')
    errors=[l for l in log.splitlines() if re.search(r'(\bERROR\s*\(|Error:)',l)]
    report=D/'impl/pnr/board.rpt.txt';metrics={}
    if report.exists():
        s=report.read_text(encoding='utf-8')
        for name in ('Logic','Register','CLS','BSRAM','DSP'):
            m=re.search(r'^\s*'+name+r'\s*\|\s*([\d.]+)/([\d.]+)',s,re.M)
            if m:metrics[name]=dict(used=float(m[1]),capacity=float(m[2]))
        paths.append(report)
    if d['returncode']==0 and d['status'].startswith('build completed'):
        static=audit(D.name,'nominal')
    else:
        interrupted=D/'interruption.json'
        if interrupted.exists():
            marker=json.loads(interrupted.read_text(encoding='utf-8'))
            assert marker['status'].startswith('NOT ACCEPTED'),marker
            paths.append(interrupted)
        else:
            assert errors or d['returncode']==124,(D.name,d)
        static=dict(static_pass=False,slack_ns=None,bench_gate=False)
    builds[D.name]=dict(status=d['status'],returncode=d['returncode'],errors=errors,resource=metrics,static=static)
    paths += [p,D/'console.log']
assert label in builds
current=builds[label]
result=dict(status='PASS evidence identities; actual build status is recorded separately',selected=label,models=models,
    changed_upstream=changed,frozen_upstream_sources=frozen,builds=builds,
    full_joint_static_pass=current['static']['static_pass'],bench_gate=False,hardware_programmed=False,
    inputs={p.relative_to(R).as_posix():sha(p) for p in paths})
(E/'candidate-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(dict(selected=label,build=current['status'],errors=current['errors'],resource=current['resource'],static_pass=result['full_joint_static_pass'],bench_gate=False)))
