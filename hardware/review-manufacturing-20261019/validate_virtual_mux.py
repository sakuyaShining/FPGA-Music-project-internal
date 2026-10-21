"""Check selected SES copper against current actual native copper before import."""
import hashlib
import json
import sys
from pathlib import Path
import grid_route as grid
from shapely.geometry import Point,LineString,box
from shapely.affinity import scale,rotate,translate
from shapely.ops import unary_union
from native_review import ROOT
from ses_selected_copper import parse
from physical_geometry import connected_subset

mode=sys.argv[1]
if mode in ['signals','core','controls-ui','scan-bus','shared-bus','display-side','audio-inv']:lane=mode;label=mode
else:lane=int(mode);assert 0<=lane<6;label=f'lane{lane}'
directory=Path(json.loads((ROOT/f'virtual-{label}-latest.json').read_text())['directory'])
nets=json.loads((directory/'attempt.json').read_text())['selected']
candidate=parse((directory/'result.ses').read_text(encoding='utf-8'),set(nets))
narrow=sum(p['width']<6 for p in candidate['lines'])
for p in candidate['lines']:p['width']=max(6,p['width'])
seen=set();unique=[]
for v in candidate['vias']:
    key=(v['net'],round(v['x'],3),round(v['y'],3),round(v['diameter'],3),round(v['hole'],3))
    if key not in seen:unique.append(v);seen.add(key)
candidate['vias']=unique
assert set(p['net'] for p in candidate['lines'])==set(nets)
source=grid.capture();raw=json.dumps(source).encode();source_name=f'grid-source-ses-{label}.json'
(ROOT/source_name).write_bytes(raw)
incomplete=[]
for net in nets:
    continuity=connected_subset([p for p in source['pads'] if p['net']==net],
                    [p for p in candidate['lines'] if p['net']==net],[p for p in candidate['vias'] if p['net']==net])
    if not continuity['complete']:incomplete.append(net)
if incomplete:raise RuntimeError('Incomplete exchange nets; native unchanged: '+', '.join(incomplete))
def actual_pad(p):
    kind,w,h,*rest=p['shape'];w*=grid.MM;h*=grid.MM
    if kind=='ELLIPSE':g=scale(Point(0,0).buffer(1,resolution=32),xfact=w/2,yfact=h/2,origin=(0,0))
    elif kind=='OVAL':
        radius=min(w,h)/2
        ends=[(-(w-h)/2,0),((w-h)/2,0)] if w>h else [(0,-(h-w)/2),(0,(h-w)/2)]
        g=LineString(ends).buffer(radius,resolution=32)
    else:g=box(-w/2,-h/2,w/2,h/2)
    return translate(rotate(g,p['rotation'],origin=(0,0)),p['x']*grid.MM,p['y']*grid.MM)
grid.pad_shape=actual_pad
combined={**source,'lines':[p for p in source['lines'] if p['net'] not in nets]+candidate['lines'],
          'vias':[p for p in source['vias'] if p['net'] not in nets]+candidate['vias']}
routes=[];violations=[]
for net in nets:
    foreign,allpads,keepouts=grid.geometries(combined,net)
    copper={layer:unary_union(foreign[layer]) for layer in [1,2]};both=unary_union(foreign[1]+foreign[2]);ko=unary_union(keepouts)
    lines=[p for p in candidate['lines'] if p['net']==net];vias=[p for p in candidate['vias'] if p['net']==net];minimum=999.
    for p in lines:
        shape=LineString([(p['x1']*grid.MM,p['y1']*grid.MM),(p['x2']*grid.MM,p['y2']*grid.MM)])
        gap=shape.distance(copper[p['layer']])-p['width']*grid.MM/2;minimum=min(minimum,gap)
        if gap<.158:violations.append((net,'track_foreign_copper',gap,p))
        if shape.distance(ko)<p['width']*grid.MM/2+.15:violations.append((net,'mount_keepout',p))
    for p in vias:
        shape=Point(p['x']*grid.MM,p['y']*grid.MM);gap=shape.distance(both)-p['diameter']*grid.MM/2;minimum=min(minimum,gap)
        if gap<.158:violations.append((net,'via_foreign_copper',gap,p))
        if shape.distance(ko)<p['diameter']*grid.MM/2+.15:violations.append((net,'via_mount_keepout',p))
    routes.append({'net':net,'lines':lines,'vias':vias,'edges':[{'min_foreign_copper_gap_mm':minimum}]})
audit={'nets':nets,'neckdown_segments_widened_to_6mil':narrow,'violations':violations,'min_gaps_mm':[(p['net'],p['edges'][0]['min_foreign_copper_gap_mm']) for p in routes],
       'native_imported':False,'requires_full_native_drc':True}
(ROOT/f'ses-{label}-geometry-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print('MINIMUM GAPS',audit['min_gaps_mm'],'VIOLATIONS',len(violations),flush=True)
if violations:raise RuntimeError('Selected SES failed continuous clearance/keepout review; native unchanged')
result={**candidate,'nets':nets,'routes':routes,'source_file':source_name,'source_sha256':hashlib.sha256(raw).hexdigest()}
path=ROOT/f'grid-plan-ses-{label}.json';path.write_text(json.dumps(result,indent=2),encoding='utf-8')
print('PLAN SAVED',path,flush=True)
