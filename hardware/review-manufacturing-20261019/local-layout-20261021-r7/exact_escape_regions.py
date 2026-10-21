"""Continuous local escape regions; avoid treating raster aliasing as enclosure."""
import sys,json,hashlib,math
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
assert not (BASE/'native-candidate-checkpoint.json').exists(), 'Accepted r7 stage is frozen; continue in a new source-bound stage instead of replaying it'
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT))
from four_layer_geometry import copper
from physical_geometry import actual_pad
from resume_offline import read_native
from shapely.geometry import box,Point,LineString
from shapely.ops import unary_union,nearest_points
cp=json.loads((ROOT/'ACTIVE-ROUTING-CANDIDATE.json').read_text(encoding='utf-8'));s=json.loads((ROOT/cp['source_capture']).read_text(encoding='utf-8'));PCB=Path(cp['project'])/'pcb/PCB1.epcb2';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();assert sha(PCB)==cp['pcb_sha256'];raw=read_native(PCB)
s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in raw.items() if k=='VIA']
def polygons(g):
 if g.geom_type=='Polygon':yield g
 elif hasattr(g,'geoms'):
  for q in g.geoms:yield from polygons(q)
rows=[]
for net in cp['pending_nets']:
 f,ps=copper(s,net);top=unary_union(f[1]);both=unary_union([q for gs in f.values() for q in gs]);padcu=unary_union(ps)
 for p in s['pads']:
  if p['net']!=net or p['layer']!=1 or not p['ref'].startswith('U'):continue
  x,y=p['x']*.0254,p['y']*.0254;window=box(x-4,y-4,x+4,y+4);start=Point(x,y)
  free=window.difference(top.buffer(.0762+.158,resolution=32));component=next((q for q in polygons(free) if q.covers(start)),None)
  if component is None:rows.append(dict(net=net,ref=p['ref'],pin=p['n'],error='center blocked'));continue
  eligible=component.difference(both.buffer(.3048+.158,resolution=32)).difference(padcu.buffer(.1524+.25,resolution=32))
  candidates=[]
  for q in polygons(eligible):
   if q.area<1e-9:continue
   inner=q.buffer(-.003,resolution=16)
   if inner.is_empty:continue
   candidate=nearest_points(start,inner)[1]
   candidates.append(dict(x_mm=candidate.x,y_mm=candidate.y,distance_mm=start.distance(candidate),region_area_mm2=q.area))
  candidates=sorted(candidates,key=lambda p:p['distance_mm'])[:8]
  blockers=[]
  for t in s['lines']:
   if t['layer']!=1 or t['net']==net:continue
   q=LineString([(t['x1']*.0254,t['y1']*.0254),(t['x2']*.0254,t['y2']*.0254)]).buffer(t['width']*.0254/2+.0762+.158,resolution=32)
   edge=component.boundary.intersection(q.buffer(.001)).length
   if edge>.02:blockers.append(dict(id=t['id'],net=t['net'],boundary_contact_mm=edge))
  row=dict(net=net,ref=p['ref'],pin=p['n'],x_mm=x,y_mm=y,component_area_mm2=component.area,touches_local_boundary=component.distance(window.boundary)<.001,via_regions_area_mm2=eligible.area,candidates=candidates,track_boundaries=sorted(blockers,key=lambda p:-p['boundary_contact_mm'])[:8]);rows.append(row)
  print(net,p['ref'],p['n'],'area',round(component.area,3),'via regions',round(eligible.area,5),'candidates',len(candidates),flush=True)
assert sha(PCB)==cp['pcb_sha256'];(BASE/'exact-escape-regions.json').write_text(json.dumps(dict(source_pcb_sha256=cp['pcb_sha256'],gap_mm=.158,via_annulus_mm=.6096,drill_mm=.3048,local_margin_mm=4,rows=rows),indent=2),encoding='utf-8')
