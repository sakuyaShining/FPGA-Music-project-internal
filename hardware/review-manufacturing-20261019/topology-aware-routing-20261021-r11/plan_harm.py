"""Exact fanout candidates, local top paths, inner16 trees; offline only."""
import sys,json,math,hashlib,gc,re
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
OUT=BASE/'harm-trial';OUT.mkdir(exist_ok=False)
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT))
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union,nearest_points
from four_layer_geometry import copper,connected
from physical_geometry import actual_pad
from resume_offline import read_native
import grid_route as g
from skimage.graph import route_through_array
sys.path.insert(0,str(ROOT/'control-closure-20261021-r8'))
from mesh_fanout import route as mesh_route
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();cp=json.loads((ROOT/'ACTIVE-ROUTING-CANDIDATE.json').read_text(encoding='utf-8'));assert 'LocalLayout-20261021-r7' in cp['project'];PCB=Path(cp['project'])/'pcb/PCB1.epcb2';assert sha(PCB)==cp['pcb_sha256'];SRC=ROOT/cp['source_capture'];s=json.loads(SRC.read_text(encoding='utf-8'));raw=read_native(PCB)
s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in raw.items() if k=='VIA']
regions=json.loads((ROOT/'local-layout-20261021-r7/current-escape-regions.json').read_text(encoding='utf-8'));assert regions['source_pcb_sha256']==cp['pcb_sha256'];lookup={(r['ref'],r['pin']):r for r in regions['rows']}
selected=['HARM_CS_N'];assert not [p for p in s['lines'] if p['net'] in selected]
w={**s,'pads':list(s['pads']),'lines':list(s['lines']),'vias':list(s['vias'])}
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
quiet=unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+(.6 if p['net'].startswith('I2S_') else .5),resolution=24) for p in s['lines'] if p['layer']==2 and (p['net'].startswith('I2S_') or re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net']))])
def segment(net,layer,a,b):return dict(net=net,layer=layer,x1=a[0]/.0254,y1=a[1]/.0254,x2=b[0]/.0254,y2=b[1]/.0254,width=6)
from PIL import Image,ImageDraw

def polygons(q):
 if q.geom_type=='Polygon':yield q
 elif hasattr(q,'geoms'):
  for a in q.geoms:yield from polygons(a)

def raster_holes(geoms,bounds,inflate,shape):
 merged=unary_union([q.buffer(inflate,resolution=32) for q in geoms if not q.is_empty]);x0,y0,_,_=bounds;ny,nx=shape;im=Image.new('1',(nx,ny),0);draw=ImageDraw.Draw(im)
 for po in polygons(merged):
  draw.polygon([((x-x0)/g.GRID,(y-y0)/g.GRID) for x,y in po.exterior.coords],fill=1)
  for ring in po.interiors:draw.polygon([((x-x0)/g.GRID,(y-y0)/g.GRID) for x,y in ring.coords],fill=0)
 return g.np.asarray(im,dtype=g.np.bool_).copy()
def path_between(a,b,obstacle,grid,bounds):
 x0,y0,x1,y1=bounds;g.GRID=grid;shape=(round((y1-y0)/grid)+1,round((x1-x0)/grid)+1)
 blocked=raster_holes([obstacle,mount],bounds,.0762+.158+grid*math.sqrt(2),shape)
 start=(round((a[1]-y0)/grid),round((a[0]-x0)/grid));end=(round((b[1]-y0)/grid),round((b[0]-x0)/grid));assert not blocked[start] and not blocked[end],'Endpoint raster blocked'
 costs=g.np.where(blocked,g.np.inf,1.);points,cost=route_through_array(costs,start,end,fully_connected=False,geometric=True);assert g.np.isfinite(cost),'No finite route'
 pts=[a]+[(x0+x*grid,y0+y*grid) for y,x in points]+[b];reduced=[]
 for p in pts:
  if reduced and math.dist(p,reduced[-1])<1e-10:continue
  while len(reduced)>1:
   u,v=reduced[-2:]
   if abs((v[0]-u[0])*(p[1]-v[1])-(v[1]-u[1])*(p[0]-v[0]))<1e-9:reduced.pop()
   else:break
  reduced.append(p)
 smooth=[reduced[0]];i=0
 while i<len(reduced)-1:
  chosen=i+1
  for j in range(min(i+500,len(reduced)-1),i,-1):
   q=LineString([reduced[i],reduced[j]])
   if q.distance(obstacle)>=.0762+.158 and q.distance(mount)>=.0762+.15:chosen=j;break
  smooth.append(reduced[chosen]);i=chosen
 assert all(LineString([a,b]).distance(obstacle)>=.0762+.158-1e-8 for a,b in zip(smooth,smooth[1:]));return smooth
def via_safe(v,pads,foreign,drills):
 q=Point(v['x']*.0254,v['y']*.0254)
 if q.distance(foreign)-.3048<.158 or q.distance(quiet)-.3048<.158 or q.distance(mount)-.3048<.15:return False
 if q.distance(pads)-.1524<.25:return False
 return not any(q.distance(Point(p['x']*.0254,p['y']*.0254))-(12+p['hole'])*.0254/2<.35 for p in drills)
def fanout(data,net,pad):
 f,ps=copper(data,net);cu=unary_union(f[1]);allcu=unary_union([q for gs in f.values() for q in gs]);pads=unary_union(ps);x,y=pad['x']*.0254,pad['y']*.0254
 row=lookup.get((pad['ref'],pad['n']));candidates=[]
 if row:
  for q in row['candidates']:
   for dx,dy in [(0,0),(0,.025),(0,-.025),(.025,0),(-.025,0),(0,.075),(0,-.075)]:candidates.append((q['x_mm']+dx,q['y_mm']+dy))
 else:
  for r in [1.1,1.35,1.6,2.0]:
   candidates.extend((x+r*math.cos(a*math.pi/8),y+r*math.sin(a*math.pi/8)) for a in range(16))
 # Recompute current continuous via regions with the quiet-sensing and audio
 # projection guards; initial closest samples need not remain usable.
 window=box(x-4,y-4,x+4,y+4);start=Point(x,y);free=window.difference(cu.buffer(.0762+.158,resolution=32));component=next((q for q in polygons(free) if q.covers(start)),None)
 if component is not None:
  eligible=component.difference(allcu.buffer(.3048+.158,resolution=32)).difference(pads.buffer(.1524+.25,resolution=32)).difference(quiet.buffer(.3048+.158,resolution=32))
  drills=unary_union([Point(v['x']*.0254,v['y']*.0254).buffer((12+v['hole'])*.0254/2+.35,resolution=32) for v in data['vias']]);eligible=eligible.difference(drills).intersection(target_region)
  for q in polygons(eligible):
   inner=q.buffer(-.005,resolution=24)
   if inner.is_empty:continue
   pt=nearest_points(start,inner)[1];candidates.append((pt.x,pt.y));rp=inner.representative_point();candidates.append((rp.x,rp.y))
 errors=[]
 for tx,ty in candidates:
  if not target_region.covers(Point(tx,ty)):continue
  v=dict(net=net,x=tx/.0254,y=ty/.0254,diameter=24,hole=12)
  if not via_safe(v,pads,allcu,data['vias']):continue
  a=(x,y);b=(tx,ty);q=LineString([a,b])
  if q.distance(cu)>=.0762+.158:points=[a,b]
  else:
   try:points=path_between(a,b,cu,.01,(x-4,y-4,x+4,y+4))
   except Exception as e:
    try:points=mesh_route(a,b,cu,(x-4,y-4,x+4,y+4))
    except Exception as e2:errors.append(str(e2));continue
  ls=[segment(net,1,a,b) for a,b in zip(points,points[1:])];return ls,[v]
 raise RuntimeError(('No safe fanout',pad['ref'],pad['n'],errors[:3]))
routes=[];failed=[]
def save():
 (OUT/'plan.json').write_text(json.dumps(dict(source_pcb_sha256=cp['pcb_sha256'],source_capture=str(SRC),source_capture_sha256=sha(SRC),routes=routes,failed=failed,selected=selected,native_imported=False,manufacturing_release=False,requires_access_regression_and_native_drc=True,raster_polygon_holes_preserved=True,topology_aware_fanout=True,previous_script_sha256='0a2594521e1bb9c8eb8185fc188d1e9787e98bb2778e8a84a3af8b865cc407ec',dynamic_quiet_compatible_via_regions=True,bottom_audio_projection_guard_mm=.6,bottom_sense_projection_guard_mm=.5),indent=2),encoding='utf-8')
for net in selected:
 print('START',net,flush=True);trial={**w,'lines':list(w['lines']),'vias':list(w['vias'])};lines=[];vias=[];anchors=[]
 try:
  pads=[p for p in s['pads'] if p['net']==net]
  source_foreign,_=copper(trial,net);inner_obstacle=unary_union(source_foreign[16]+[quiet,mount])
  parts=sorted(polygons(box(.5,.5,139.5,99.5).difference(inner_obstacle.buffer(.0762+.1605,resolution=32))),key=lambda q:q.area,reverse=True)
  th=[Point(p['x']*.0254,p['y']*.0254) for p in pads if p['layer']==12]
  target_region=next((q for q in parts if all(q.covers(p) for p in th)),None)
  assert target_region is not None,'No shared through-hole component'
  print('TARGET REGION',target_region.area,flush=True)
  ordered=sorted(pads,key=lambda p:(sum(q['region_area_mm2'] for q in lookup.get((p['ref'],p['n']),{}).get('candidates',[])) if (p['ref'],p['n']) in lookup else 999,p['ref']))
  for p in ordered:
   if p['layer']==12:anchors.append((p['x']*.0254,p['y']*.0254));continue
   ls,vs=fanout(trial,net,p);lines+=ls;vias+=vs;trial['lines']+=ls;trial['vias']+=vs;anchors.append((vs[0]['x']*.0254,vs[0]['y']*.0254));print('FAN',net,p['ref'],p['n'],flush=True)
  f,ps=copper(trial,net);obstacle=unary_union(f[16]+[quiet]);used={0};edges=[]
  while len(used)<len(anchors):
   _,a,b=min((math.dist(anchors[a],anchors[b]),a,b) for a in used for b in range(len(anchors)) if b not in used);edges.append((a,b));used.add(b)
  x0=max(.5,min(a[0] for a in anchors)-8);y0=max(.5,min(a[1] for a in anchors)-8);x1=min(139.5,max(a[0] for a in anchors)+8);y1=min(99.5,max(a[1] for a in anchors)+8)
  for a,b in edges:
   pts=None
   for bounds in [(x0,y0,x1,y1),(.5,.5,139.5,99.5)]:
    try:pts=path_between(anchors[a],anchors[b],obstacle,.05,bounds);break
    except (ValueError,AssertionError):continue
   if pts is None:
    pts=mesh_route(anchors[a],anchors[b],obstacle,(.5,.5,139.5,99.5))
   assert pts,'No inner16 route in checked windows';lines +=[segment(net,16,a,b) for a,b in zip(pts,pts[1:])]
  assert connected(pads,lines,vias)['complete'];assert len(vias)<=len(pads)+2
  rt=dict(net=net,lines=lines,vias=vias,length_mm=sum(math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254 for p in lines),actual_four_layer_connected=True)
  routes.append(rt);w['lines']+=lines;w['vias']+=vias;print('CANDIDATE',net,len(vias),rt['length_mm'],flush=True)
 except Exception as e:failed.append(dict(net=net,error=repr(e)));print('REJECTED',net,repr(e),flush=True)
 save();gc.collect()
assert sha(PCB)==cp['pcb_sha256'];print('DONE',len(routes),'offline complete-net candidates',flush=True)
