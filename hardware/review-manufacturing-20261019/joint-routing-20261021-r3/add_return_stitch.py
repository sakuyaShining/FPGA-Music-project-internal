"""Check a nearby grounded layer-transition stitch for the local BUS_RETURN via."""
import hashlib,json,math,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');sys.path.insert(0,str(ROOT))
import shapely
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
import grid_route as grid
from physical_geometry import actual_pad,connected_subset
from resume_offline import read_native
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
path=OUT/'local-compatible-power-bus-plan.json';plan=read(path)
assert plan['both_nets_complete'] and plan['independent_geometry_pass']
PCB=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019/pcb/PCB1.epcb2')
assert sha(PCB)==plan['native_pcb_sha256']
data=read(Path(plan['source_file']));native=read_native(PCB);ids={p['id'] for p in data['lines']}
for (k,i),p in native.items():
    if k=='LINE' and p.get('layerId') in [1,2] and i not in ids:
        data['lines'].append(dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']))
for p in data['vias']:
    n=native['VIA',p['id']];p['diameter']=n['viaDiameter'];p['hole']=n['holeDiameter']
data['lines']=[p for p in data['lines'] if p['id'] not in plan['remove_line_ids']]+plan['additive_power_lines']+plan['bus_lines']
data['vias']+=plan['additive_power_vias']+plan['bus_vias']
# The new 0.5mm branch also connects EN to VIN. Remove the superseded thin
# three-segment link rather than retain a redundant little copper loop.
redundant=[p for p in data['lines'] if p.get('id') and p['net']=='5V_PERIPH' and p['layer']==1 and
    all(115<x*.0254<119 for x in [p['x1'],p['x2']]) and all(60<y*.0254<62 for y in [p['y1'],p['y2']])]
assert len(redundant)==3
redundant_ids={p['id'] for p in redundant}
data['lines']=[p for p in data['lines'] if p.get('id') not in redundant_ids]
for net in ['5V_PERIPH','BUS_RETURN']:
    assert connected_subset([p for p in data['pads'] if p['net']==net],[p for p in data['lines'] if p['net']==net],[p for p in data['vias'] if p['net']==net])['complete'],net
plan['remove_line_ids']+=sorted(redundant_ids)
plan['removed_lines']+=redundant
plan['removed_redundant_supply_link_ids']=sorted(redundant_ids)
grid.pad_shape=actual_pad
anchor=next(p for p in data['lines'] if p.get('id')=='d19a9f38e480abf5')
end=(anchor['x2'],anchor['y2'])
f,pads,k=grid.geometries(data,'GND');cu={l:unary_union(f[l]) for l in [1,2]};both=unary_union(f[1]+f[2]);ko=unary_union(k)
allpads=unary_union(pads);signal=plan['bus_vias'][0];sx,sy=signal['x']*.0254,signal['y']*.0254
candidates=[]
for radius in [.85,1.,1.15]:
    for degrees in range(0,360,15):
        x=sx+radius*math.cos(math.radians(degrees));y=sy+radius*math.sin(math.radians(degrees))
        q=Point(x,y);segment=LineString([(x,y),(end[0]*.0254,end[1]*.0254)])
        if q.distance(both)-.6096/2<.17 or segment.distance(cu[2])-.2032/2<.17:continue
        if q.distance(allpads)<.3048/2+.25:continue
        if q.distance(ko)<.6096/2+.15 or segment.distance(ko)<.2032/2+.15:continue
        if any(math.hypot(x-v['x']*.0254,y-v['y']*.0254)-(.3048+v['hole']*.0254)/2<.35 for v in data['vias']):continue
        candidates.append((radius+segment.length,x,y))
assert candidates,'No local return stitch with explicit bottom-GND connection'
_,x,y=min(candidates)
via=dict(net='GND',x=x/.0254,y=y/.0254,diameter=.6096/.0254,hole=.3048/.0254)
line=dict(net='GND',layer=2,x1=via['x'],y1=via['y'],x2=end[0],y2=end[1],width=.2032/.0254)
q=Point(x,y);segment=LineString([(x,y),(end[0]*.0254,end[1]*.0254)])
gaps=dict(via_copper_mm=q.distance(both)-.6096/2,track_copper_mm=segment.distance(cu[2])-.2032/2,
    via_to_pad_copper_mm=q.distance(unary_union(pads)))
assert gaps['via_copper_mm']>=.158 and gaps['track_copper_mm']>=.158,gaps
assert gaps['via_to_pad_copper_mm']>=.3048/2+.25,gaps
assert q.distance(ko)>=.6096/2+.15 and segment.distance(ko)>=.2032/2+.15
for v in data['vias']:
    assert math.hypot(via['x']-v['x'],via['y']-v['y'])*.0254-(via['hole']+v['hole'])*.0254/2>=.3499
distance=min(math.hypot(via['x']-v['x'],via['y']-v['y'])*.0254 for v in plan['bus_vias'])
assert distance<=1.2
plan.update(ground_lines=[line],ground_vias=[via],ground_anchor_native_line=anchor['id'],
    checked_valid_stitch_candidates=len(candidates),
    new_bus_via_to_ground_stitch_mm=distance,ground_stitch_geometry=gaps,
    upstream_candidate_sha256=sha(path),requires_rebuilt_ground_pour_and_native_drc=True,
    return_path_limit='Nearby stitch tied explicitly to saved bottom GND spine; top plane contact and full return geometry must be inspected after native rebuild. Does not certify I2S return paths.')
(OUT/'local-power-bus-with-return-plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
print(json.dumps(dict(ground_stitch_distance_mm=distance,gaps=gaps,manufacturing_release=False),indent=2))
