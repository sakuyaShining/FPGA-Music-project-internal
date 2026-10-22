"""Plan a measured local fanout repair, retaining the partial disable bus.

U6.15's left-shifted via blocks U6.16. Move that local escape upward, retain
L5_M13's pin fanout but reroute its trunk, and connect L5_M15. All other copper
and all devices remain unchanged. The global MUX_DISABLE bus remains pending.
"""
import hashlib
import json
import time
import grid_route as grid
from reserve_escape import reserve
from physical_geometry import actual_pad
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
from native_review import ROOT

source=grid.capture();raw=json.dumps(source).encode();source_name='grid-source-mux5-escape.json'
(ROOT/source_name).write_bytes(raw)
net='MUX_DISABLE';removed_lines={'12e0b116ca1fc447','e29944aec46559cd','d224ae91b62f8bc9'};removed_via='5e5db714adb7c54c'
assert removed_lines<={p['id'] for p in source['lines'] if p['net']==net}
assert removed_via in {p['id'] for p in source['vias'] if p['net']==net}
reroute={'L5_M13','L5_M15'};nets=sorted(reroute|{net})
working={**source,'pads':list(source['pads']),
         'lines':[p for p in source['lines'] if p['net'] not in reroute and p['id'] not in removed_lines],
         'vias':[p for p in source['vias'] if p['net'] not in reroute and p['id']!=removed_via]}
disable_pad=next(p for p in source['pads'] if p['ref']=='U6' and p['n']=='15')
disable_line={'net':net,'layer':1,'x1':disable_pad['x'],'y1':disable_pad['y'],'x2':disable_pad['x'],'y2':82.825/grid.MM,'width':8}
disable_via={'net':net,'x':disable_pad['x'],'y':82.825/grid.MM,'diameter':24,'hole':12}
working['lines'].append(disable_line);working['vias'].append(disable_via)
escape=reserve(source,working,'L5_M13')
pad=next(p for p in source['pads'] if p['ref']=='U6' and p['n']=='16')
fan_line={'net':pad['net'],'layer':1,'x1':pad['x'],'y1':pad['y'],'x2':116.625/grid.MM,'y2':82.325/grid.MM,'width':6}
fan_via={'net':pad['net'],'x':fan_line['x2'],'y':fan_line['y2'],'diameter':24,'hole':12,'routing_retained':True}
working['lines'].append(fan_line);working['vias'].append(fan_via)
working['pads']=[{**p,'routing_pad_exclude':True} if p['id']==pad['id'] else p for p in working['pads']]
working['pads'].append({**pad,'id':'anchor-'+pad['id'],'ref':'FANOUT-U6','layer':12,'x':fan_via['x'],'y':fan_via['y'],'rotation':0,'shape':['ELLIPSE',24,24,0]})
routes=[]
for n in ['L5_M15','L5_M13']:
    r=grid.plan(working,n);routes.append(r);working['lines']+=r['lines'];working['vias']+=r['vias']
    print('PLANNED',n,len(r['lines']),len(r['vias']),flush=True)
lines=[p for p in source['lines'] if p['net']==net and p['id'] not in removed_lines]+[disable_line,fan_line]+escape['lines']+[p for r in routes for p in r['lines']]
vias=[p for p in source['vias'] if p['net']==net and p['id']!=removed_via]+[disable_via,fan_via]+escape['vias']+[p for r in routes for p in r['vias']]
combined={**source,'lines':[p for p in source['lines'] if p['net'] not in nets]+lines,'vias':[p for p in source['vias'] if p['net'] not in nets]+vias}
grid.pad_shape=actual_pad
minimum=999.
for n,ls,vs in [(net,[disable_line],[disable_via]),(pad['net'],[fan_line],[fan_via])]:
    foreign,_,ko=grid.geometries(combined,n);cu={l:unary_union(foreign[l]) for l in [1,2]};both=unary_union(foreign[1]+foreign[2])
    for p in ls:minimum=min(minimum,LineString([(p['x1']*grid.MM,p['y1']*grid.MM),(p['x2']*grid.MM,p['y2']*grid.MM)]).distance(cu[p['layer']])-p['width']*grid.MM/2)
    for p in vs:minimum=min(minimum,Point(p['x']*grid.MM,p['y']*grid.MM).distance(both)-p['diameter']*grid.MM/2)
assert minimum>=.158,('Unsafe manual fanout',minimum)
routes.append({'net':'fanout-geometry-proof','edges':[{'min_foreign_copper_gap_mm':minimum}]})
result={'nets':nets,'expected_completed_nets':['L5_M13','L5_M15'],'intentionally_partial_net':net,'lines':lines,'vias':vias,'routes':routes,
        'source_file':source_name,'source_sha256':hashlib.sha256(raw).hexdigest(),'requires_native_drc_and_ground_rebuild':True}
path=ROOT/'grid-plan-mux5-escape.json';path.write_text(json.dumps(result,indent=2),encoding='utf-8')
print('PLAN SAVED',path,'fanout minimum clearance',minimum,flush=True)
