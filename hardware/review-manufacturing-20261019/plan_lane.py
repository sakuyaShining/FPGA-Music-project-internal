"""Plan unfinished MUX channels in one lane before rerouting its RC node."""
import hashlib
import json
import re
import sys
import time
from native_review import ROOT
from grid_route import capture,plan
from reserve_escape import reserve,grid_mux_fanouts

lane=int(sys.argv[1]);assert 0<=lane<6
drc=json.loads((ROOT/'pcb-drc.json').read_text(encoding='utf-8'))
pending=sorted(y['name'] for x in drc if x['name']=='Connection Error' for y in x['list'] if re.fullmatch(f'L{lane}_M[0-9][0-9]',y['name']))
preferred=sys.argv[2:]
if '--all' in preferred:
    pending=[f'L{lane}_M{i:02}' for i in range(16)]
    preferred.remove('--all')
assert set(preferred)<=set(pending)
pending=preferred+[n for n in pending if n not in preferred]
if not pending:print('No unfinished MUX nets in lane',lane);sys.exit(0)
source=capture();raw=json.dumps(source).encode();(ROOT/'grid-route-source.json').write_bytes(raw)
nets=pending+[f'RC{lane}']
working={**source,'lines':[p for p in source['lines'] if p['net'] not in nets],'vias':[p for p in source['vias'] if p['net'] not in nets]}
routes=[]
escape=reserve(source,working,f'RC{lane}')
print('RESERVED RC FANOUTS',escape['reserved_real_pad_fanouts'],flush=True)
fanouts=grid_mux_fanouts(working,pending)
print('NEW MUX FANOUTS',fanouts['new_fanouts'],flush=True)
hard=[n for n in pending if any(p['net']==n and p['ref'] in ['U1','U2','U3','U4','U5','U6'] and not p.get('routing_pad_exclude') for p in working['pads'])]
route_order=hard+[n for n in pending if n not in hard]+[f'RC{lane}']
print('ROUTE ORDER',route_order,flush=True)
for net in route_order:
    start=time.monotonic();route=plan(working,net);routes.append(route)
    working['lines']+=route['lines'];working['vias']+=route['vias']
    print('PLANNED',net,len(route['lines']),'segments',len(route['vias']),'vias',round(time.monotonic()-start,1),'seconds',flush=True)
routes.append(escape)
routes.append(fanouts)
result={'nets':nets,'routes':routes,'lines':[p for r in routes for p in r['lines']],'vias':[p for r in routes for p in r['vias']],
        'source_sha256':hashlib.sha256(raw).hexdigest(),'requires_native_drc_and_ground_rebuild':True}
path=ROOT/f'grid-plan-lane{lane}.json';path.write_text(json.dumps(result,indent=2),encoding='utf-8');print('PLAN SAVED',path,flush=True)
