"""Qualify evidence identities, never reclassify rejected builds as timing PASS."""
from common import *
import re,xml.etree.ElementTree as ET
from audit_timing import rows
up=json.loads((R/'upstream.json').read_text(encoding='utf-8'))
for prefix in ('','board_'):
    U=Path(up[prefix+'root']);assert sha(U/'delivery.json')==up[prefix+'delivery_sha256']
    for rel,h in up[prefix+'files'].items():assert sha(U/rel)==h,(prefix,rel)
checks={};input_files=[R/'upstream.json',Path(__file__).resolve(),R/'common.py',R/'audit_timing.py']
for name in ('joint-model','delta-model','sensor-model','native-model','pitch-model','engine-compatibility'):
    p=E/(name+'.json');d=json.loads(p.read_text(encoding='utf-8'));assert d['status'].startswith('PASS')
    for rel,h in d['inputs'].items():assert sha(R/rel)==h,(name,rel)
    checks[name]=d['status'];input_files.append(p)
legacy=json.loads((E/'engine-compatibility.json').read_text(encoding='utf-8'))
for name,d in legacy['results'].items():
    p=E/(name+'-compat.tsv');assert sha(p)==d['trace_sha256']==d['reference_sha256']
    with p.open(encoding='utf-8') as f:
        for i,line in enumerate(f,1):assert int(line.split()[0])==i,(p.name,i)
    input_files.append(p)
history={}
for rev in range(6):
    D=R/('build_nominal_v%d'%rev);p=D/'run.json';d=json.loads(p.read_text(encoding='utf-8'))
    assert d['returncode']!=0 and d['status']=='FAILED build',rev
    for name,v in d['inputs'].items():assert sha(D/name)==v['sha256'],(rev,name)
    assert sha(D/'board.gprj')==d['project_sha256'] and sha(D/'build.tcl')==d['tcl_sha256']
    if rev in (4,5):
        for name,v in d['inputs'].items():assert sha(R/v['source'])==v['sha256'],(rev,name)
    log=(D/'console.log').read_text(encoding='utf-8',errors='replace')
    errors=[l for l in log.splitlines() if re.search(r'\bERROR\s*\(',l)];assert errors,rev
    text=(D/'impl/gwsynthesis/board_syn.rpt.html').read_text(encoding='utf-8');metrics={}
    for k in ('Logic','BSRAM'):
        m=re.search('>'+k+r'</td>\s*<td>(\d+)',text);assert m,k;metrics[k]=int(m[1])
    root=ET.parse(D/'impl/gwsynthesis/board_syn_rsc.xml').getroot()
    metrics['Register']=int(root.get('T_Register').split('(')[0])
    history[str(rev)]=dict(status='FAIL retained',errors=errors,synthesis_resource=metrics,top_hierarchy=root.attrib)
    input_files.extend([p,D/'console.log',D/'impl/gwsynthesis/board_syn.rpt.html',D/'impl/gwsynthesis/board_syn_rsc.xml'])
assert 'PA2122' in '\n'.join(history['0']['errors'])
assert 'CT1113' in '\n'.join(history['1']['errors'])
assert all('PR0003' in '\n'.join(history[str(i)]['errors']) for i in (2,3,4,5))
last=R/'build_nominal_v5';pins=rows((last/'impl/pnr/board.pin.html').read_text(encoding='utf-8'))
sip=[v for v in pins if len(v)>7 and (v[0].startswith('O_sdram') or v[0].startswith('IO_sdram'))]
assert len(sip)==55 and all(v[2].startswith('p') for v in sip)
board=json.loads((E/'board-readonly.json').read_text(encoding='utf-8'))
assert board['status'].startswith('PASS') and not board['result']['bitstream_programmed_by_this_script']
assert sha(Path(board['script_path']))==board['script_sha256']
timing=json.loads((E/'timing-audit.json').read_text(encoding='utf-8'))
assert timing['status'].startswith('FAIL') and not timing['bench_gate']
assert timing['selected']['nominal']['slack_ns'] is None and timing['selected']['stress']['slack_ns'] is None
for rel,h in timing['inputs'].items():assert sha(R/rel)==h,rel
input_files += [E/'timing-audit.json',E/'board-readonly.json',E/'board-readonly.log',last/'impl/pnr/board.pin.html']
result=dict(status='PASS scoped functional/evidence identity audit; joint placement remains FAIL',checks=checks,
    rejected_builds=history,latest_synthesis=history['5']['synthesis_resource'],
    new_pitch_registers=142,full_joint_timing_pass=False,bench_gate=False,new_hardware_tested=False,
    inputs={p.relative_to(R).as_posix():sha(p) for p in input_files})
(E/'history-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('inputs','rejected_builds','checks')}))
