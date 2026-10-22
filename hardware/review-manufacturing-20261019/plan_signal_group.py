"""Plan selected non-power nets together while preserving short real fanouts."""
import hashlib
import json
import sys
import time
from grid_route import capture,plan
from reserve_escape import reserve
from native_review import ROOT

label=sys.argv[1];nets=sys.argv[2:]
assert label.replace('-','').isalnum() and nets and len(set(nets))==len(nets)
assert not set(nets)&{'GND','5V_PERIPH','5V_IN','3V3_IO','3V3_PERIPH','DAC_3V3'}
source=capture();raw=json.dumps(source).encode();(ROOT/'grid-route-source.json').write_bytes(raw)
working={**source,'pads':list(source['pads']),'lines':[p for p in source['lines'] if p['net'] not in nets],
         'vias':[p for p in source['vias'] if p['net'] not in nets]}
escapes=[reserve(source,working,net) for net in nets]
print('RESERVED',[(r['net'],r['reserved_real_pad_fanouts']) for r in escapes],flush=True)
routes=[]
for net in nets:
    started=time.monotonic();route=plan(working,net);routes.append(route)
    working['lines']+=route['lines'];working['vias']+=route['vias']
    print('PLANNED',net,len(route['lines']),'segments',len(route['vias']),'vias',round(time.monotonic()-started,1),'seconds',flush=True)
routes+=escapes
result={'nets':nets,'routes':routes,'lines':[p for r in routes for p in r['lines']],
        'vias':[p for r in routes for p in r['vias']], 'source_sha256':hashlib.sha256(raw).hexdigest(),
        'requires_native_drc_and_ground_rebuild':True}
path=ROOT/f'grid-plan-{label}.json';path.write_text(json.dumps(result,indent=2),encoding='utf-8')
print('PLAN SAVED',path,flush=True)
