"""Independent actual-copper checks for the offline mixed four-layer plan."""
import json,sys,math,hashlib
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;OUT=BASE/'four-layer-mixed'
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');sys.path.insert(0,str(ROOT))
import shapely
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
from physical_geometry import actual_pad
from resume_offline import read_native
from current_state import current_checkpoint
_,cp,SRC=current_checkpoint(ROOT);PCB=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019/pcb/PCB1.epcb2')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();assert sha(PCB)==cp['pcb_sha256']
original=read_native(PCB);plan=json.loads((OUT/'plan.json').read_text());w=json.loads((OUT/'working-final.json').read_text());source=json.loads(SRC.read_text());layers=[1,15,16,2]
oldlines={i:p for (k,i),p in original.items() if k=='LINE' and p.get('layerId') in [1,2]};oldvias={i:p for (k,i),p in original.items() if k=='VIA'}
# Raster anchors are never physical objects and must never be native pads.
pads=[p for p in source['pads'] if not p['id'].startswith('anchor-')]
ko=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
objects=[]
for p in pads:objects.append((p['net'],set(layers) if p['layer']==12 else {p['layer']},actual_pad(p),'pad',p))
for p in w['lines']:objects.append((p['net'],{p['layer']},LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,resolution=32),'line',p))
for p in w['vias']:objects.append((p['net'],set(layers),Point(p['x']*.0254,p['y']*.0254).buffer(p['diameter']*.0254/2,resolution=32),'via',p))
cache={}
def foreign(net,l):
 if (net,l) not in cache:cache[net,l]=unary_union([g for n,ls,g,k,p in objects if n!=net and l in ls])
 return cache[net,l]
checks=[];errors=[]
for route in plan['routes']:
 net=route['net'];minimum=99.;newlines=0;newvias=0
 try:
  for p in route['lines']:
   if p.get('id') in oldlines:continue
   newlines+=1;q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)])
   gap=q.distance(foreign(net,p['layer']))-p['width']*.0254/2;minimum=min(minimum,gap)
   assert gap>=.158,(net,'line',gap,p)
   assert q.distance(ko)>=p['width']*.0254/2+.15,(net,'mount')
  for p in route['vias']:
   if p.get('id') in oldvias:continue
   newvias+=1;q=Point(p['x']*.0254,p['y']*.0254)
   gap=min(q.distance(foreign(net,l))-p['diameter']*.0254/2 for l in layers);minimum=min(minimum,gap)
   assert gap>=.158,(net,'via',gap,p)
   assert q.distance(unary_union([actual_pad(a) for a in pads]))-p['hole']*.0254/2>=.25,(net,'hole-pad')
   assert q.distance(ko)>=p['diameter']*.0254/2+.15,(net,'mount-via')
   for old in w['vias']:
    if old is p or old==p:continue
    drillgap=q.distance(Point(old['x']*.0254,old['y']*.0254))-(old['hole']+p['hole'])*.0254/2
    assert drillgap>=.3499,(net,'drill',drillgap)
  checks.append(dict(net=net,geometry_pass=True,new_lines_checked=newlines,new_vias_checked=newvias,min_foreign_gap_mm=minimum))
 except Exception as e:errors.append(dict(net=net,error=repr(e)));checks.append(dict(net=net,geometry_pass=False,error=repr(e)))
# Preserve a continuous-reference corridor under actual bottom I2S tracks.
i2s=unary_union([LineString([(p['startX']*.0254,p['startY']*.0254),(p['endX']*.0254,p['endY']*.0254)]).buffer(p['width']*.0254/2,resolution=32) for p in oldlines.values() if p['netName'].startswith('I2S_') and p['layerId']==2])
returnchecks=[dict(net=r['net'],min_inner_to_bottom_i2s_gap_mm=min((LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).distance(i2s)-p['width']*.0254/2 for p in r['lines'] if p['layer']==16),default=None)) for r in plan['routes']]
assert all(p['min_inner_to_bottom_i2s_gap_mm'] is None or p['min_inner_to_bottom_i2s_gap_mm']>=.5999 for p in returnchecks)
selected={r['net'] for r in plan['routes']};retained_line_ids={p['id'] for p in w['lines'] if p['net'] not in selected};retained_via_ids={p['id'] for p in w['vias'] if p['net'] not in selected}
assert retained_line_ids=={i for i,p in oldlines.items() if p['netName'] not in selected}
assert retained_via_ids=={i for i,p in oldvias.items() if p['netName'] not in selected}
result=dict(native_pcb_sha256=sha(PCB),native_unchanged=True,plan_sha256=sha(OUT/'plan.json'),checks=checks,errors=errors,combined_geometry_pass=not errors,inner_i2s_reference_corridor=returnchecks,requires_native_ground_pour_stackup_and_sensor_capacitance_review=True,manufacturing_release=False)
(OUT/'independent-geometry.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(geometry_pass=not errors,errors=errors,net_count=len(plan['routes'])),indent=2))
