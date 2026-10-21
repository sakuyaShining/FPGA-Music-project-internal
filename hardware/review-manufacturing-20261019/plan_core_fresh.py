"""Plan pending core signals in a copper-free working copy of those nets.

Successful routes coexist with blank pending nets, rather than restoring old
unfinished fragments that obstruct the new routes. Native PCB is not mutated by
this planner. Any application must explicitly include the intentionally cleared
pending nets and pass a fresh native DRC; the 0-clearance checkpoint is retained.
"""
import gc
import hashlib
import json
import math
import re
import time
import sys
import grid_route as grid
from physical_geometry import actual_pad,connected_subset
from native_review import ROOT

drc=json.loads((ROOT/'pcb-drc.json').read_text(encoding='utf-8'))
pending=[n['name'] for c in drc if c['name']=='Connection Error' for n in c['list']]
protected={'GND','5V_IN','5V_FUSED','5V_PROTECTED','5V_PERIPH','3V3_IO','3V3_PERIPH','DAC_3V3',
           'DAC_CAPP','DAC_CAPM','DAC_VNEG','DAC_LDOO','DAC_L_RAW','DAC_R_RAW','AUX_L','AUX_R'}
nets=[n for n in pending if n not in protected and not re.fullmatch(r'L[0-5]_[EM]\d\d|RC[0-5]',n)]
assert nets
source_name='grid-source-core-fresh.json'
resume='--resume' in sys.argv[1:]
if resume:
    raw=(ROOT/source_name).read_bytes();source=json.loads(raw);saved=json.loads((ROOT/'grid-plan-core-fresh.json').read_text(encoding='utf-8'))
    assert saved['source_sha256']==hashlib.sha256(raw).hexdigest() and set(nets)==set(saved['nets'])
    current=grid.capture()
    canonical=lambda d:json.dumps({k:sorted(d[k],key=lambda p:p['id']) for k in ['pads','lines','vias']},sort_keys=True)
    assert canonical(current)==canonical(source),'Native copper/pads changed; do not resume old plan'
else:
    source=grid.capture();raw=json.dumps(source).encode();(ROOT/source_name).write_bytes(raw)
working={**source,'pads':list(source['pads']),'lines':[p for p in source['lines'] if p['net'] not in nets],
         'vias':[p for p in source['vias'] if p['net'] not in nets]}
def extent(net):
    ps=[p for p in source['pads'] if p['net']==net]
    return (max(p['x'] for p in ps)-min(p['x'] for p in ps)+max(p['y'] for p in ps)-min(p['y'] for p in ps))*grid.MM
order=sorted(nets,key=lambda n:(extent(n),n));routes=saved['routes'] if resume else [];failed=saved['failed_planning'] if resume else []
if resume:
    working['lines']+=[p for r in routes for p in r['lines']];working['vias']+=[p for r in routes for p in r['vias']]
    attempted={r['net'] for r in routes}|{r['net'] for r in failed};order=[n for n in order if n not in attempted]
grid.pad_shape=actual_pad;grid.GAP=.17
print('FRESH CORE',len(nets),'nets; remove only their unfinished copper in virtual copy',flush=True)
print('ORDER',order,flush=True)
def save():
    success=[p['net'] for p in routes]
    estimate=sum(c.get('count',0) for c in drc)-sum(n.get('count',len(n.get('list',[]))) for c in drc for n in c.get('list',[]) if n['name'] in nets)
    for n in set(nets)-set(success):
        ps=[p for p in source['pads'] if p['net']==n]
        estimate+=connected_subset(ps,[],[]).get('pad_islands',len(ps))
    data={'nets':nets,'expected_completed_nets':success,'intentionally_cleared_unfinished_nets':[n for n in nets if n not in success],
          'routes':routes,'lines':[p for r in routes for p in r['lines']],'vias':[p for r in routes for p in r['vias']],
          'failed_planning':failed,'estimated_remaining_connection_objects':estimate,
          'source_file':source_name,'source_sha256':hashlib.sha256(raw).hexdigest(),'requires_native_drc_and_ground_rebuild':True}
    (ROOT/'grid-plan-core-fresh.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    print('SAVED PARTIAL PLAN',len(success),'complete nets;',len(nets)-len(success),'still blank; estimated errors',estimate,flush=True)
for net in order:
    started=time.monotonic()
    try:
        route=grid.plan(working,net)
        continuity=connected_subset([p for p in source['pads'] if p['net']==net],route['lines'],route['vias'])
        if not continuity['complete']:raise RuntimeError('Independent pad continuity failed')
        routes.append(route);working['lines']+=route['lines'];working['vias']+=route['vias']
        print('PLANNED',net,len(route['lines']),len(route['vias']),round(time.monotonic()-started,1),'seconds',flush=True)
    except Exception as error:
        failed.append({'net':net,'error':str(error)})
        print('PENDING',net,type(error).__name__,str(error),round(time.monotonic()-started,1),'seconds',flush=True)
    save();gc.collect()
print('FINAL FRESH PLAN',len(routes),'completed nets;',len(failed),'pending',flush=True)
