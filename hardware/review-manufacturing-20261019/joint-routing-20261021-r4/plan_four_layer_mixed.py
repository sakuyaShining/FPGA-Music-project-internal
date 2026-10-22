"""Offline four-layer routing with actual outer copper and through-via checks.
L2 GND; L3 control plus GND; bottom participates when necessary. No native edit.
"""
import json,sys,math,copy,hashlib,inspect,gc,time
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;OUT=BASE/'four-layer-mixed';OUT.mkdir(exist_ok=False)
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');sys.path.insert(0,str(ROOT))
import shapely
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
import grid_route as g
from physical_geometry import actual_pad
from current_state import current_checkpoint
from resume_offline import read_native
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
_,cp,SRC=current_checkpoint(ROOT);source=json.loads(SRC.read_text());PCB=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019/pcb/PCB1.epcb2');assert sha(PCB)==cp['pcb_sha256']
native=read_native(PCB)
source['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in native.items() if k=='LINE' and p.get('layerId') in [1,2]]
source['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in native.items() if k=='VIA']
cache=json.loads((BASE/'four-layer-offline/outer-fanouts.json').read_text());w=cache['working'];fans=cache['fans']
prev=json.loads((BASE/'four-layer-offline/plan.json').read_text());assert prev['native_pcb_sha256']==cp['pcb_sha256']
missing={f['net'] for f in prev['failed'] if f['reason']=='missing_outer_fanout'}
selected=[n for n in prev['selected'] if n not in missing]
# Restore every unrouteable net before planning anything else.
for k in ['lines','vias']:w[k]=[p for p in w[k] if p['net'] not in missing]+[p for p in source[k] if p['net'] in missing]
w['pads']=[{k:v for k,v in p.items() if k!='routing_pad_exclude'} if p['net'] in missing else p for p in w['pads'] if not(p['net'] in missing and p['id'].startswith('anchor-'))]
pending=cp['pending_nets'];selected.sort(key=lambda n:(n in pending,sum(p['net']==n for p in source['vias'])))
g.pad_shape=actual_pad;g.GRID=.075;g.GAP=.165;g.WIDTH=.1524;g.VIA_D=.6096;g.VIA_H=.3048;g.VIA_COST_MM=20;g.SEARCH_MARGINS=[8,22,50]
raw_raster=g.raster;g.raster=lambda gs,b,i,s:raw_raster(gs,b,i+g.GRID/math.sqrt(2),s)
# Keep a 0.6 mm projected corridor around existing bottom I2S copper. This is a
# geometric guard for a later ground-pour/reference check, not an SI simulation.
protected=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+.6) for p in source['lines'] if p['net'].startswith('I2S_') and p['layer']==2]
original_geom=g.geometries
def geom(data,net):
 f,ps,ko=original_geom(data,net);f[1]+=protected;ps+=data.get('top_pad_shapes',[])
 return f,ps,ko
g.geometries=geom
# Add surface-top clearance to every through-via transition. Normal two-layer
# routing only examines its two search planes; that is insufficient here.
ss=inspect.getsource(g.search).replace('def search(','def search4(')
needle="    own_drills="
pos=ss.index(needle)
ss=ss[:pos]+"    via_block|=raster([shape for owner,shape in data.get('top_copper',[]) if owner!=net],bounds,VIA_D/2+GAP,shape)\n"+ss[pos:]
exec(ss,g.__dict__);g.search=g.search4

def mapped(work):
 ps=[p for p in work['pads'] if p['layer']==12 or p['layer']==2]
 top=[];top_pads=[]
 for p in work['pads']:
  if p['id'].startswith('anchor-'):continue
  if p['layer']==1:
   sh=actual_pad(p);top.append((p['net'],sh));top_pads.append(sh)
 for p in work['lines']:
  if p['layer']==1:top.append((p['net'],LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,resolution=16)))
 return dict(pads=ps,lines=[{**p,'layer':1 if p['layer']==16 else 2} for p in work['lines'] if p['layer'] in [16,2]],vias=work['vias'],top_copper=top,top_pad_shapes=top_pads)
# Four-layer continuity, independent of the raster route search.
def continuity(net,lines,vias):
 mask={1:1,15:2,16:4,2:8,12:15};objects=[]
 for p in source['pads']:
  if p['net']==net:objects.append((mask[p['layer']],actual_pad(p),'pad'))
 pads=len(objects)
 for p in lines:objects.append((mask[p['layer']],LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,resolution=16),'line'))
 for p in vias:objects.append((15,Point(p['x']*.0254,p['y']*.0254).buffer(p['diameter']*.0254/2,resolution=16),'via'))
 parent=list(range(len(objects)))
 def root(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 for i,(m,sh,_) in enumerate(objects):
  for j in range(i):
   if m&objects[j][0] and root(i)!=root(j) and sh.distance(objects[j][1])<=.003:parent[root(i)]=root(j)
 return len({root(i) for i in range(pads)})==1
routes=[];failed=[]
def save():
 (OUT/'plan.json').write_text(json.dumps(dict(source_file=str(SRC),source_sha256=sha(SRC),native_pcb_sha256=cp['pcb_sha256'],selected=selected,routes=routes,failed=failed,missing_fanouts=sorted(missing),native_imported=False,manufacturing_release=False,inner_i2s_keepout_mm=.6,requires_final_combined_geometry_and_native_drc=True),indent=2))
print('SELECTED',selected,flush=True)
for n in selected:
 print('START',n,flush=True)
 try:
  trial=g.plan(mapped(w),n)
  lines=fans[n]['lines']+[{**p,'layer':16 if p['layer']==1 else 2} for p in trial['lines']];vias=fans[n]['vias']+trial['vias']
  assert continuity(n,lines,vias),'Four-layer real-pad continuity failed'
  oldv=sum(p['net']==n for p in source['vias']);oldl=sum(math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254 for p in source['lines'] if p['net']==n);length=sum(math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254 for p in lines)
  metrics=dict(before_vias=oldv,after_vias=len(vias),before_length_mm=oldl,after_length_mm=length)
  if n not in pending:assert len(vias)<=oldv and length<=oldl*1.15,'Connected-net quality budget'
  else:assert len(vias)<=len([p for p in source['pads'] if p['net']==n])+2,'Pending-net via budget'
  routes.append(dict(net=n,lines=lines,vias=vias,edges=trial['edges'],metrics=metrics,real_four_layer_continuity=True))
  for k,val in [('lines',lines),('vias',vias)]:w[k]=[p for p in w[k] if p['net']!=n]+val
  print('CANDIDATE',n,metrics,flush=True)
 except Exception as ex:
  failed.append(dict(net=n,reason=repr(ex)))
  for k in ['lines','vias']:w[k]=[p for p in w[k] if p['net']!=n]+[p for p in source[k] if p['net']==n]
  print('REJECTED',n,repr(ex),flush=True)
 save();gc.collect()
(OUT/'working-final.json').write_text(json.dumps(w));assert sha(PCB)==cp['pcb_sha256'];print('DONE',len(routes),len(failed),'NOT NATIVE-VALIDATED',flush=True)
