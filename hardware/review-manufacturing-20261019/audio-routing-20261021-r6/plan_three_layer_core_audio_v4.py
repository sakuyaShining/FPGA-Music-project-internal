"""Source-bound top-only I2S trial. No native edits or new vias."""
import sys,json,math,hashlib,copy,gc,time
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;OUT=BASE/'three-layer-core-v4';OUT.mkdir(exist_ok=False)
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
from shapely.geometry import LineString,box
from shapely.ops import unary_union
sys.path.insert(0,str(ROOT));import grid_route as g
from physical_geometry import actual_pad,connected_subset
from resume_offline import read_native
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();cp=json.loads((ROOT/'ACTIVE-ROUTING-CANDIDATE.json').read_text());SRC=ROOT/cp['source_capture'];PCB=Path(cp['project'])/'pcb/PCB1.epcb2';assert sha(PCB)==cp['pcb_sha256']
s=json.loads(SRC.read_text());raw=read_native(PCB);s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]];s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in raw.items() if k=='VIA']
nets=['I2S_LRCK','I2S_DIN','I2S_BCK'];w={**s,'lines':[p for p in s['lines'] if p['net'] not in nets],'vias':[p for p in s['vias'] if p['net'] not in nets]}
g.pad_shape=actual_pad;g.GRID=.05;g.GAP=.165;g.WIDTH=.1524;g.VIA_COST_MM=100;g.SEARCH_MARGINS=[8,22,50]
raster=g.raster;g.raster=lambda gs,b,i,s:raster(gs,b,i+g.GRID*math.sqrt(2),s)
guards=[]
for p in s['pads']:
 if p['net'] not in cp['pending_nets'] or p['layer']!=1 or min(p['shape'][1:3])*.0254>.65:continue
 angle=math.radians(p['rotation']);axis=(math.cos(angle),math.sin(angle)) if p['shape'][1]>=p['shape'][2] else (-math.sin(angle),math.cos(angle));x,y=p['x']*.0254,p['y']*.0254
 guards.append(LineString([(x-axis[0]*1.7,y-axis[1]*1.7),(x+axis[0]*1.7,y+axis[1]*1.7)]).buffer(.0762))
orig=g.geometries
def geom(data,net):
 f,ps,ko=orig(data,net);f[1]+=guards;f[2].append(box(-2,-2,142,102));return f,ps,ko
g.geometries=geom
# Global compiled minimum-cost path avoids the legacy first-success bounding
# window and 1.5M-node cap. Four-neighbor paths cannot cut diagonal corners.
from skimage.graph import route_through_array
import skimage

# The inner signal layer is adjacent to bottom-side high-impedance sensing
# traces. Avoid their XY projection by 0.5 mm; top-side sensing is shielded
# from this signal layer by the uninterrupted inner15 GND plane.
import re
quiet=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+.5,resolution=16) for p in s['lines'] if p['layer']==2 and (re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net']))]
def global_outer_search(data,net,start,end,margin):
 from skimage.graph import MCP_Geometric
 # The middle cost sheet contains isolated checkerboard via portals only.
 # With 6-neighbor connectivity it cannot carry lateral copper: every visit
 # must change outer layer at the *same XY*. It is a graph device, not a PCB layer.
 f,ps,ko=orig(data,net);f[1]+=guards;f[16]=[g.pad_shape(p) for p in data['pads'] if p['layer']==12 and p['net']!=net]+[g.Point(v['x']*.0254,v['y']*.0254).buffer(v['diameter']*.0254/2,resolution=16) for v in data['vias'] if v['net']!=net]+[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,resolution=16) for p in data['lines'] if p['layer']==16 and p['net']!=net]+quiet;bounds=(10.45,20.45,125.55,75.55);x0,y0,x1,y1=bounds
 nx=round((x1-x0)/g.GRID)+1;ny=round((y1-y0)/g.GRID)+1
 blocked=[g.raster(f[l]+ko,bounds,g.WIDTH/2+g.GAP,(ny,nx)) for l in [1,16,2]]
 inner=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,resolution=16) for p in data['lines'] if p.get('layer') in [15,16] and p['net']!=net]
 via_block=g.raster(f[1]+f[16]+f[2]+inner,bounds,g.VIA_D/2+g.GAP,(ny,nx))|g.raster(ps,bounds,g.VIA_H/2+.25,(ny,nx))|g.raster(ko,bounds,g.VIA_D/2+.15,(ny,nx))
 own=[g.Point(v['x']*.0254,v['y']*.0254).buffer(v['hole']*.0254/2) for v in data['vias']+data.get('reserved_drills',[]) if v['net']==net]
 via_block|=g.raster(own,bounds,g.VIA_H/2+.35,(ny,nx))
 yy,xx=g.np.ogrid[:ny,:nx];portals=(~via_block)&(~blocked[0])&(~blocked[1])&(~blocked[2])&((xx+yy)%2==0)
 portals&=((x0+xx*g.GRID)>=.7)&((x0+xx*g.GRID)<=139.3)&((y0+yy*g.GRID)>=.7)&((y0+yy*g.GRID)<=99.3)
 costs=g.np.full((5,ny,nx),g.np.inf,dtype=g.np.float64);costs[0][~blocked[0]]=1.;costs[2][~blocked[1]]=1.;costs[4][~blocked[2]]=1.;costs[1][portals]=1.;costs[3][portals]=1.
 sx,sy=start['x']*.0254,start['y']*.0254;tx,ty=end['x']*.0254,end['y']*.0254
 sxg,syg=round((sx-x0)/g.GRID),round((sy-y0)/g.GRID);txg,tyg=round((tx-x0)/g.GRID),round((ty-y0)/g.GRID)
 starts=[(l,syg,sxg) for l in ([0,2,4] if start['layer']==12 else [0 if start['layer']==1 else 4]) if g.np.isfinite(costs[l,syg,sxg])]
 ends=[(l,tyg,txg) for l in ([0,2,4] if end['layer']==12 else [0 if end['layer']==1 else 4]) if g.np.isfinite(costs[l,tyg,txg])]
 assert starts and ends,(net,'No unblocked endpoint')
 solver=MCP_Geometric(costs,fully_connected=False,sampling=(g.VIA_COST_MM/2,g.GRID,g.GRID));distance,_=solver.find_costs(starts,ends,find_all_ends=False);goal=min(ends,key=lambda p:distance[p]);assert g.np.isfinite(distance[goal]),'Global physical graph disconnected'
 total=float(distance[goal]);path=solver.traceback(goal);cu={l:unary_union(f[l]) for l in [1,16,2]};mount=unary_union(ko);lines=[];vias=[]
 def flush(points,layer):
  reduced=[]
  for point in points:
   if reduced and math.dist(point,reduced[-1])<1e-9:continue
   while len(reduced)>1:
    a,b=reduced[-2:];cross=(b[0]-a[0])*(point[1]-b[1])-(b[1]-a[1])*(point[0]-b[0])
    if abs(cross)<1e-8:reduced.pop()
    else:break
   reduced.append(point)
  if not reduced:return
  smooth=[reduced[0]];i=0
  while i<len(reduced)-1:
   chosen=i+1
   for j in range(min(i+500,len(reduced)-1),i,-1):
    q=LineString([reduced[i],reduced[j]])
    if q.distance(cu[layer])>=g.WIDTH/2+g.GAP and q.distance(mount)>=g.WIDTH/2+.15:chosen=j;break
   smooth.append(reduced[chosen]);i=chosen
  lines.extend(dict(net=net,layer=layer,x1=a[0]/.0254,y1=a[1]/.0254,x2=b[0]/.0254,y2=b[1]/.0254,width=6) for a,b in zip(smooth,smooth[1:]) if math.dist(a,b)>1e-9)
 layer_map={0:1,2:16,4:2};layer=layer_map[path[0][0]];points=[(sx,sy)];last_via_xy=None
 for i,(sheet,y,x) in enumerate(path):
  pt=(x0+x*g.GRID,y0+y*g.GRID)
  if sheet in [1,3]:
   assert 0<i<len(path)-1 and path[i-1][0]!=path[i+1][0] and path[i-1][1:]==path[i+1][1:]==(y,x),'Invalid lateral via portal'
   points.append(pt);flush(points,layer)
   # A through via spans all copper layers. Consecutive vertical portals at
   # one XY are one physical hole, even though the routing cost charges more.
   if last_via_xy!=(y,x):vias.append(dict(net=net,x=pt[0]/.0254,y=pt[1]/.0254,diameter=24,hole=12));last_via_xy=(y,x)
   points=[pt]
  else:
   layer=layer_map[sheet];points.append(pt)
   if i and path[i-1][1:]!=(y,x):last_via_xy=None
 points.append((tx,ty));flush(points,layer)
 minimum=min(LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).distance(cu[p['layer']])-g.WIDTH/2 for p in lines)
 both=unary_union(f[1]+f[16]+f[2]+inner);padcu=unary_union(ps)
 for i,p in enumerate(vias):
  q=g.Point(p['x']*.0254,p['y']*.0254);gap=q.distance(both)-g.VIA_D/2;minimum=min(minimum,gap);assert gap>=.158,(net,'Via copper',gap);assert q.distance(padcu)-g.VIA_H/2>=.25
  for v in data['vias']+vias[:i]:assert q.distance(g.Point(v['x']*.0254,v['y']*.0254))-(p['hole']+v['hole'])*.0254/2>=.3499,(net,'Drill')
 assert minimum>=.158,(net,minimum)
 result=dict(lines=lines,vias=vias,min_foreign_copper_gap_mm=minimum,algorithm='Core-envelope MCP isolated portals; physical1/16/2; heuristic sheet penalty, not a physical via length or global optimality claim',routing_cost_mm=total,via_penalty_mm=g.VIA_COST_MM,search_bounds_mm=bounds)
 (OUT/('raw-'+net+'.json')).write_text(json.dumps(result,indent=2));print('GLOBAL_METRICS',net,dict(vias=len(vias),length_mm=sum(math.dist((p['x1'],p['y1']),(p['x2'],p['y2']))*.0254 for p in lines)),flush=True)
 return result
g.search=global_outer_search;g.VIA_COST_MM=20;g.SEARCH_MARGINS=[140]
routes=[];failed=[]
def length(ls):return sum(math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254 for p in ls)
from four_layer_geometry import copper,connected

def validate(data,net,lines,vias):
 f,pads=copper(data,net);f[1]+=guards;f[16]+=quiet;cu={l:unary_union(f[l]) for l in [1,15,16,2]};_,_,ko=orig(data,net);mount=unary_union(ko);minimum=99.
 for p in lines:
  q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]);gap=q.distance(cu[p['layer']])-p['width']*.0254/2;minimum=min(minimum,gap);assert gap>=.158,(net,'line',gap);assert q.distance(mount)>=p['width']*.0254/2+.15
 both=unary_union(f[1]+f[15]+f[16]+f[2]);pad_union=unary_union(pads)
 assert len({(round(p['x'],5),round(p['y'],5)) for p in vias})==len(vias)
 for i,p in enumerate(vias):
  q=g.Point(p['x']*.0254,p['y']*.0254);gap=q.distance(both)-p['diameter']*.0254/2;minimum=min(minimum,gap);assert gap>=.158,(net,'via',gap);assert q.distance(pad_union)-p['hole']*.0254/2>=.25
  for v in data['vias']+vias[:i]:
   if v is p or v==p:continue
   assert q.distance(g.Point(v['x']*.0254,v['y']*.0254))-(p['hole']+v['hole'])*.0254/2>=.3499,(net,'drill')
 return minimum
def save():
 (OUT/'plan.json').write_text(json.dumps(dict(source_file=str(SRC),source_sha256=sha(SRC),native_pcb_sha256=cp['pcb_sha256'],project=cp['project'],routes=routes,failed=failed,protection='Both 1.7mm fine-pitch escape axes reserved for every remaining pending pin',reserved_pin_corridors=len(guards),native_imported=False,manufacturing_release=False,requires_actual_rebuilt_ground_reference_check=True,actual_four_layer_continuity_checked=True,bottom_high_impedance_projection_guard_mm=.5,raster_extra_inflation='GRID*sqrt(2)',reference_validation_pending=True),indent=2))
for net in nets:
 print('START',net,flush=True)
 try:
  rt=g.plan(w,net);assert len(rt['vias'])<=3,'Audio via budget';assert connected([p for p in s['pads'] if p['net']==net],rt['lines'],rt['vias'])['complete'],'Actual four-layer connectivity'
  gap=validate(w,net,rt['lines'],rt['vias']);oldlen=length([p for p in s['lines'] if p['net']==net]);newlen=length(rt['lines']);assert newlen<=oldlen,'Audio length increase'
  rt['quality']=dict(before_length_mm=oldlen,after_length_mm=newlen,before_vias=sum(p['net']==net for p in s['vias']),after_vias=len(rt['vias']),min_foreign_gap_mm=gap)
  routes.append(rt);w['lines']+=rt['lines'];w['vias']+=rt['vias'];print('GLOBAL_CANDIDATE',net,rt['quality'],flush=True)
 except Exception as e:
  failed.append(dict(net=net,error=repr(e)));w['lines'] +=[p for p in s['lines'] if p['net']==net];w['vias'] +=[p for p in s['vias'] if p['net']==net];print('REJECTED',net,repr(e),flush=True)
 save();gc.collect()
# Restore rejected copper before accepting any subset; repeat pruning to a fixed point.
pruned=[]
while True:
 bad=[]
 for rt in routes:
  try:validate(w,rt['net'],rt['lines'],rt['vias'])
  except Exception as e:bad.append((rt,repr(e)))
 if not bad:break
 for rt,err in bad:
  pruned.append(dict(net=rt['net'],reason=err));routes.remove(rt);w['lines']=[p for p in w['lines'] if p['net']!=rt['net']]+[p for p in s['lines'] if p['net']==rt['net']];w['vias']=[p for p in w['vias'] if p['net']!=rt['net']]+[p for p in s['vias'] if p['net']==rt['net']]
save();v=json.loads((OUT/'plan.json').read_text());v['pruned']=pruned;v['batch_final_geometry_pass']=bool(routes);(OUT/'plan.json').write_text(json.dumps(v,indent=2));assert sha(PCB)==cp['pcb_sha256'];print('DONE',len(routes),'safe offline candidates; native unchanged',flush=True)
