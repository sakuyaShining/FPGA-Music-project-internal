"""Realize continuous legal via pockets; sampled rays alone are not the routing boundary."""
from pathlib import Path
import sys,json,math,hashlib,re
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,str(ROOT/'inv2-comparison-20261021-r16'))
from exchange import read
from four_layer_geometry import copper,connected
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
sys.path.insert(0,str(ROOT/'control-closure-20261021-r8'))
from mesh_fanout import route as mesh_route
cp,pcb,s=read();screen=json.loads((OUT/'plan.json').read_text(encoding='utf8'));power=screen['power_rework']
assert cp['pcb_sha256']==screen['source_pcb_sha256']
s['lines']=[p for p in s['lines'] if p['id']!=power['remove_line_id']]+power['replacement_lines']
cap=json.loads((OUT/'via-escape-capacity.json').read_text(encoding='utf8'))
assert cap['source_pcb_sha256']==cp['pcb_sha256']
f,pads=copper(s,'INV2');foreign={l:unary_union(q) for l,q in f.items()};allforeign=unary_union(list(foreign.values()));allpads=unary_union(pads)
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
quiet=unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+(.6 if p['net'].startswith('I2S_') else .5),quad_segs=32) for p in s['lines'] if p['layer']==2 and (p['net'].startswith('I2S_') or re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net']))])
obs={1:unary_union([foreign[1],mount]),16:unary_union([foreign[16],mount,quiet])};bounds=(37,39,61,56)
terms=[p for p in s['pads'] if p['net']=='INV2'];fanouts=[]
for t,c in zip(terms,cap['terminals']):
    assert t['ref']==c['ref'];start=(t['x']*.0254,t['y']*.0254);options=[]
    for xy in c['legal_area_representatives_mm']:
        if math.dist(start,xy)>5:continue
        direct=LineString([start,xy])
        try:path=[start,xy] if direct.distance(obs[1])>=.0762+.165 else mesh_route(start,xy,obs[1],bounds)
        except AssertionError:continue
        options.append(dict(xy_mm=xy,path=path,length_mm=sum(math.dist(a,b) for a,b in zip(path,path[1:]))))
    assert options,('No realizable top fanout',t['ref']);fanouts.append(options)
    print('TOP OPTIONS',t['ref'],[(p['xy_mm'],p['length_mm']) for p in options],flush=True)
best=None;trials=[]
for a in fanouts[0]:
    for b in fanouts[1]:
        direct=LineString([a['xy_mm'],b['xy_mm']])
        try:path=[a['xy_mm'],b['xy_mm']] if direct.distance(obs[16])>=.0762+.165 else mesh_route(a['xy_mm'],b['xy_mm'],obs[16],bounds)
        except AssertionError as e:trials.append(dict(a=a['xy_mm'],b=b['xy_mm'],failure=str(e)));continue
        length=a['length_mm']+b['length_mm']+sum(math.dist(u,v) for u,v in zip(path,path[1:]));trials.append(dict(a=a['xy_mm'],b=b['xy_mm'],length_mm=length))
        if best is None or length<best['length_mm']:best=dict(a=a,b=b,path=path,length_mm=length)
assert best is not None and best['length_mm']<=30,trials
lines=[];vias=[]
def add(layer,pts):
    for a,b in zip(pts,pts[1:]):
        if math.dist(a,b)>1e-7:lines.append(dict(net='INV2',layer=layer,x1=a[0]/.0254,y1=a[1]/.0254,x2=b[0]/.0254,y2=b[1]/.0254,width=6))
for p in [best['a'],best['b']]:
    add(1,p['path']);x,y=p['xy_mm'];vias.append(dict(net='INV2',x=x/.0254,y=y/.0254,diameter=24,hole=12))
add(16,best['path'])
mintrack=min(LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).distance(obs[p['layer']])-.0762 for p in lines)
minvia=min(Point(v['x']*.0254,v['y']*.0254).distance(allforeign)-.3048 for v in vias)
minholepad=min(Point(v['x']*.0254,v['y']*.0254).distance(allpads)-.1524 for v in vias)
minoldhole=min(math.dist((v['x'],v['y']),(p['x'],p['y']))*.0254-(v['hole']+p['hole'])*.0254/2 for v in vias for p in s['vias'])
assert mintrack>=.158 and minvia>=.158 and minholepad>=.25 and minoldhole>=.35,(mintrack,minvia,minholepad,minoldhole)
proof=connected(terms,lines,vias);assert proof['complete']
result=dict(source_pcb_sha256=cp['pcb_sha256'],net='INV2',source_files=cp['files'],lines=lines,vias=vias,length_mm=best['length_mm'],power_rework=power,continuity=proof,minimum_clearances_mm=dict(track_including_quiet=mintrack,via_foreign_copper=minvia,hole_pad=minholepad,old_drill=minoldhole),trials=trials,components_moved=[],source_sensor_RC_and_SENSE_copper_preserved=True,new_signal_vias=2,new_power_vias=0,requires_actual_ground_reference_validation=True,native_imported=False,manufacturing_release=False)
(OUT/'candidate.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
assert hashlib.sha256(pcb.read_bytes()).hexdigest()==cp['pcb_sha256']
print(json.dumps({k:v for k,v in result.items() if k not in ['lines','source_files','power_rework','trials']},indent=2),flush=True)
