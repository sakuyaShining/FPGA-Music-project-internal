"""Bounded new layer-assignment experiment; no native write or new vias."""
from pathlib import Path
import json,sys,copy,hashlib,math,re
B=Path(__file__).resolve().parent;R=B.parent;O=B/'inv2-coupled'
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path[:0]=[str(R),str(B)]
import grid_route as g
from four_layer_geometry import copper,connected
from native_plane_geometry import poured_planes
from resume_offline import read_native
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
rd=lambda p:json.loads(p.read_text(encoding='utf8'))
cp=rd(R/'REGIONAL-WORK-IN-PROGRESS.json');pcb=Path(cp['project'])/'pcb/PCB1.epcb2'
sha=hashlib.sha256(pcb.read_bytes()).hexdigest();assert sha==cp['pcb_sha256']=='6509803e7afca781b7f71ad69183cc10d8f6413312701eb16a2cdc46dfe83afd'
source=rd(O/'checkpoint-capture.json');oldesc=rd(B/'address-extended-escapes.json');nets=['L1_M06','L1_M07'];work=copy.deepcopy(source)
remove=[p for p in work['lines'] if p['net'] in nets and p['layer']==2];work['lines']=[p for p in work['lines'] if p not in remove]
work['lines']+=[p for p in oldesc['lines'] if p['net']=='ADDR0'];work['vias']+=[p for p in oldesc['vias'] if p['net']=='ADDR0']
pad=next(p for p in source['pads'] if p['ref']=='U2' and p['n']=='10');v=dict(net='ADDR0',x=pad['x'],y=pad['y']-1.375/.0254,diameter=24,hole=12)
escape=dict(net='ADDR0',layer=1,x1=pad['x'],y1=pad['y'],x2=v['x'],y2=v['y'],width=6)
work['vias'].append(v);work['lines'].append(escape);work['routing_allow_new_vias']=True
rawanalog=lambda net:bool(re.fullmatch(r'RC[0-5]',net) or re.match(r'L[0-5]_',net))
# Avoid crossing active digital copper with the newly assigned sensitive route.
# Existing sensor copper remains physical obstacles on its actual layer.
digital=lambda net:bool(net not in ['GND','3V3_IO','3V3_PERIPH','5V_IN','5V_FUSED','5V_PROTECTED','5V_PERIPH','BUS_RETURN'] and not rawanalog(net))
quiet_geoms=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+.5,quad_segs=16) for p in work['lines'] if digital(p['net'])]+[Point(p['x']*.0254,p['y']*.0254).buffer(p['diameter']*.0254/2+.5,quad_segs=16) for p in work['vias'] if digital(p['net'])]
quiet=unary_union(quiet_geoms)
planes=poured_planes(read_native(pcb));g.WIDTH=.2032;g.GAP=.18;g.SEARCH_MARGINS=[5];g.VIA_COST_MM=8
original_geometries=g.geometries
def geom(data,net):
 f,pads=copper(data,net)
 # Search layer1 represents physical16; search layer2 represents physical2.
 # Vias are existing endpoints only. No artificial short on any other layer.
 return {1:f[16]+quiet_geoms,2:f[2]+quiet_geoms},pads,[box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]]
g.geometries=geom
results=[];new=[];newvias=[];failure=None
try:
 for net in nets:
  endpoints=[{**p,'layer':12} for p in source['vias'] if p['net']==net]
  assert len(endpoints)==2
  fullforeign,_=copper(work,net)
  work['routing_extra_via_obstacles']=fullforeign[1]+fullforeign[15]
  route=g.search(work,net,endpoints[0],endpoints[1],5)
  if not route:raise RuntimeError('No path '+net)
  lines=[{**p,'layer':16 if p['layer']==1 else 2} for p in route['lines']]
  work['lines']+=lines;new+=lines;work['vias']+=route['vias'];newvias+=route['vias']
  proof=connected([p for p in work['pads'] if p['net']==net],[p for p in work['lines'] if p['net']==net],[p for p in work['vias'] if p['net']==net]);assert proof['complete']
  excluded=unary_union([Point(v['x']*.0254,v['y']*.0254).buffer(1) for v in endpoints]);projection=[]
  for p in lines:
   q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).difference(excluded);ref=2 if p['layer']==16 else 16
   projection.append(dict(layer=p['layer'],reference=ref,length_mm=q.length,covered_mm=q.intersection(planes[ref]).length))
  results.append(dict(net=net,continuity=proof,layers=sorted({p['layer'] for p in lines}),new_segments=len(lines),new_vias=len(route['vias']),length_mm=sum(math.dist((p['x1'],p['y1']),(p['x2'],p['y2']))*.0254 for p in lines),source_reference_projection=projection))
  print('RECOVERED',net,results[-1]['layers'],results[-1]['length_mm'],flush=True)
except Exception as e:failure=repr(e);print('STOP',failure,flush=True)
finally:g.geometries=original_geometries
out=dict(source_pcb_sha256=sha,method='Joint two-sensor trunk assignment to physical16/2 with legal new through-vias; preserve top stubs and 8mil; reserve all seven ADDR0 exits; active digital copper guard .5mm plus routing gap; all top/15 copper blocks new vias; no native mutation',remove_lines=remove,lines=new,vias=newvias,address0_escape=escape,address0_via=v,results=results,failure=failure,complete_pair=len(results)==2,native_imported=False,manufacturing_release=False,next_action='Only if pair recovered, validate final four-layer geometry plus new ADDR0 fanout, actual reference after native pours and complete address backbone before any adoption; otherwise change affected layout/whole bundle, never repeat same search.')
(B/'address-layer-reassignment-with-vias.json').write_text(json.dumps(out,indent=2),encoding='utf8')
assert hashlib.sha256(pcb.read_bytes()).hexdigest()==sha
print('NATIVE_UNCHANGED',out['complete_pair'],flush=True)
