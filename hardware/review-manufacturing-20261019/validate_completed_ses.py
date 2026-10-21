"""Keep only complete SES nets that clear all copper retained in the native PCB.

Removing a rejected candidate restores that net's actual old native copper as an
obstacle. Iterate until the accepted subset is stable; never import partial nets.
"""
import hashlib
import json
import sys
from pathlib import Path
import grid_route as grid
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
from physical_geometry import actual_pad,connected_subset
from native_review import ROOT

label=sys.argv[1]
directory=Path(json.loads((ROOT/f'virtual-{label}-latest.json').read_text())['directory'])
candidate=json.loads((directory/'complete-copper.json').read_text(encoding='utf-8'))
source=grid.capture();raw=json.dumps(source).encode();source_name=f'grid-source-complete-{label}.json'
(ROOT/source_name).write_bytes(raw)
for p in candidate['lines']:p['width']=max(6,p['width'])
unique={}
for p in candidate['vias']:unique.setdefault((p['net'],round(p['x'],3),round(p['y'],3)),p)
candidate['vias']=list(unique.values())
nets=set(candidate['nets']);rejected=[];grid.pad_shape=actual_pad
while nets:
    combined={**source,'lines':[p for p in source['lines'] if p['net'] not in nets]+[p for p in candidate['lines'] if p['net'] in nets],
              'vias':[p for p in source['vias'] if p['net'] not in nets]+[p for p in candidate['vias'] if p['net'] in nets]}
    routes=[];bad=set();errors=[]
    for net in sorted(nets):
        lines=[p for p in candidate['lines'] if p['net']==net];vias=[p for p in candidate['vias'] if p['net']==net]
        continuity=connected_subset([p for p in source['pads'] if p['net']==net],lines,vias)
        if not continuity['complete']:bad.add(net);errors.append((net,'not_connected'));continue
        foreign,allpads,keepouts=grid.geometries(combined,net);cu={l:unary_union(foreign[l]) for l in [1,2]};both=unary_union(foreign[1]+foreign[2]);ko=unary_union(keepouts);minimum=999.
        for p in lines:
            shape=LineString([(p['x1']*grid.MM,p['y1']*grid.MM),(p['x2']*grid.MM,p['y2']*grid.MM)])
            gap=shape.distance(cu[p['layer']])-p['width']*grid.MM/2;minimum=min(minimum,gap)
            if gap<.158 or shape.distance(ko)<p['width']*grid.MM/2+.15:bad.add(net);errors.append((net,'track',gap))
        for p in vias:
            shape=Point(p['x']*grid.MM,p['y']*grid.MM);gap=shape.distance(both)-p['diameter']*grid.MM/2;minimum=min(minimum,gap)
            if gap<.158 or shape.distance(ko)<p['diameter']*grid.MM/2+.15:bad.add(net);errors.append((net,'via',gap))
        routes.append({'net':net,'lines':lines,'vias':vias,'edges':[{'min_foreign_copper_gap_mm':minimum}]})
    if not bad:break
    rejected.append({'nets':sorted(bad),'conflicts':errors});nets-=bad
    print('REJECTED',sorted(bad),'REMAIN',len(nets),flush=True)
audit={'accepted_nets':sorted(nets),'rejected_rounds':rejected,'native_imported':False,'requires_native_drc':True}
(ROOT/f'ses-complete-{label}-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
if not nets:raise RuntimeError('No complete clearance-safe subset; native unchanged')
result={'nets':sorted(nets),'routes':routes,'lines':[p for p in candidate['lines'] if p['net'] in nets],
        'vias':[p for p in candidate['vias'] if p['net'] in nets],'source_file':source_name,'source_sha256':hashlib.sha256(raw).hexdigest()}
path=ROOT/f'grid-plan-complete-{label}.json';path.write_text(json.dumps(result,indent=2),encoding='utf-8')
print('PLAN SAVED',path,'ACCEPTED',sorted(nets),flush=True)
