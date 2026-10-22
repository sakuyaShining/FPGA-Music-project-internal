"""Audit preserved evidence; PASS is not a routing/timing qualification."""
from common import *
import xml.etree.ElementTree as ET
paths=[Path(__file__).resolve(),R/'common.py',R/'upstream.json']
up=json.loads((R/'upstream.json').read_text(encoding='utf-8'))
for prefix in ('','board_'):
    U=Path(up[prefix+'root']);assert sha(U/'delivery.json')==up[prefix+'delivery_sha256']
    for rel,h in up[prefix+'files'].items():assert sha(U/rel)==h,(prefix,rel)
records={}
for name in ('candidate-audit','timing-audit','scan-model','joint-model','resource-map'):
    p=E/(name+'.json');d=json.loads(p.read_text(encoding='utf-8'));paths.append(p)
    for rel,h in d['inputs'].items():assert sha(R/rel)==h,(name,rel)
    records[name]=d
assert records['candidate-audit']['status'].startswith('PASS')
assert records['scan-model']['status'].startswith('PASS') and records['joint-model']['status'].startswith('PASS')
assert records['resource-map']['status'].startswith('PASS')
assert records['candidate-audit']['selected']=='build_nominal_v4'
builds=records['candidate-audit']['builds'];assert len(builds)==5
for k in ('build_nominal_v0','build_nominal_v1','build_nominal_v2','build_nominal_v4'):
    assert builds[k]['returncode']!=0 and builds[k]['errors'] and not builds[k]['static']['static_pass']
assert (R/'build_nominal_v3/interruption.json').exists()
assert not records['timing-audit']['bench_gate']
syn=R/'build_nominal_v4/impl/gwsynthesis/board_syn_rsc.xml';root=ET.parse(syn).getroot();paths.append(syn)
summary={k:root.get(k) for k in ('T_Register','T_Lut','T_Alu','T_Bsram','T_Ssram','T_MULTALU18X18')}
assert summary['T_Register']=='10760(40)' and summary['T_Bsram']=='32(0)'
generated=E/'generated-identity.json';g=json.loads(generated.read_text(encoding='utf-8'));paths.append(generated)
for rel,h in g['inputs'].items():assert sha(R.parents[1]/rel)==h,rel
for rel,h in g['outputs'].items():assert sha(R/rel)==h,rel
board=E/'board-status.json';paths.extend([board,E/'board-status.log'])
b=json.loads(board.read_text(encoding='utf-8'));assert not b['hardware_programmed'] and not b['audio_triggered']
result=dict(status='PASS recorded evidence identities; routing remains FAIL',selected='build_nominal_v4',
    latest_synthesis=summary,builds=builds,full_joint_timing_pass=False,bench_gate=False,
    hardware_programmed=False,board_status=b['status'],changed_upstream=records['candidate-audit']['changed_upstream'],
    inherited_engine_files=sum(1 for p in (R/'engine').rglob('*') if p.is_file()),
    inputs={p.relative_to(R).as_posix():sha(p) for p in paths})
(E/'history-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('inputs','builds')}))
