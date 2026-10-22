"""Source-bound top-only I2S trial. No native edits or new vias."""
import sys,json,math,hashlib,copy,gc,time
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;OUT=BASE/'top-only-trial';OUT.mkdir(exist_ok=False)
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
from shapely.geometry import LineString,box
from shapely.ops import unary_union
sys.path.insert(0,str(ROOT));import grid_route as g
from physical_geometry import actual_pad,connected_subset
from resume_offline import read_native
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();cp=json.loads((ROOT/'ACTIVE-ROUTING-CANDIDATE.json').read_text());SRC=ROOT/cp['source_capture'];PCB=Path(cp['project'])/'pcb/PCB1.epcb2';assert sha(PCB)==cp['pcb_sha256']
s=json.loads(SRC.read_text());raw=read_native(PCB);s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]];s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in raw.items() if k=='VIA']
nets=['I2S_LRCK','I2S_DIN','I2S_BCK'];w={**s,'lines':[p for p in s['lines'] if p['net'] not in nets],'vias':[p for p in s['vias'] if p['net'] not in nets]}
g.pad_shape=actual_pad;g.GRID=.025;g.GAP=.165;g.WIDTH=.1524;g.VIA_COST_MM=100;g.SEARCH_MARGINS=[8,22,50]
raster=g.raster;g.raster=lambda gs,b,i,s:raster(gs,b,i+g.GRID/math.sqrt(2),s)
guards=[]
for p in s['pads']:
 if p['net'] not in cp['pending_nets'] or p['layer']!=1 or min(p['shape'][1:3])*.0254>.65:continue
 angle=math.radians(p['rotation']);axis=(math.cos(angle),math.sin(angle)) if p['shape'][1]>=p['shape'][2] else (-math.sin(angle),math.cos(angle));x,y=p['x']*.0254,p['y']*.0254
 guards.append(LineString([(x-axis[0]*1.7,y-axis[1]*1.7),(x+axis[0]*1.7,y+axis[1]*1.7)]).buffer(.0762))
orig=g.geometries
def geom(data,net):
 f,ps,ko=orig(data,net);f[1]+=guards;f[2].append(box(-2,-2,142,102));return f,ps,ko
g.geometries=geom
routes=[];failed=[]
def length(ls):return sum(math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254 for p in ls)
def validate(data,net,lines):
 f,_,ko=g.geometries(data,net);cu=unary_union(f[1]);mount=unary_union(ko);minimum=99.
 for p in lines:
  assert p['layer']==1;q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]);gap=q.distance(cu)-p['width']*.0254/2;minimum=min(gap,minimum);assert gap>=.158,(net,gap);assert q.distance(mount)>=p['width']*.0254/2+.15
 return minimum
def save():
 (OUT/'plan.json').write_text(json.dumps(dict(source_file=str(SRC),source_sha256=sha(SRC),native_pcb_sha256=cp['pcb_sha256'],project=cp['project'],routes=routes,failed=failed,protection='Both 1.7mm fine-pitch escape axes reserved for every remaining pending pin',reserved_pin_corridors=len(guards),native_imported=False,manufacturing_release=False,requires_actual_rebuilt_ground_reference_check=True),indent=2))
for net in nets:
 print('START',net,flush=True)
 try:
  rt=g.plan(w,net);assert not rt['vias'];assert connected_subset([p for p in s['pads'] if p['net']==net],rt['lines'],[])['complete']
  gap=validate(w,net,rt['lines']);oldlen=length([p for p in s['lines'] if p['net']==net]);newlen=length(rt['lines']);assert newlen<=oldlen,'Audio length increase'
  rt['quality']=dict(before_length_mm=oldlen,after_length_mm=newlen,before_vias=sum(p['net']==net for p in s['vias']),after_vias=0,min_foreign_gap_mm=gap)
  routes.append(rt);w['lines']+=rt['lines'];print('TOP_CANDIDATE',net,rt['quality'],flush=True)
 except Exception as e:
  failed.append(dict(net=net,error=repr(e)));w['lines'] +=[p for p in s['lines'] if p['net']==net];w['vias'] +=[p for p in s['vias'] if p['net']==net];print('REJECTED',net,repr(e),flush=True)
 save();gc.collect()
# Restore rejected copper before accepting any subset; repeat pruning to a fixed point.
pruned=[]
while True:
 bad=[]
 for rt in routes:
  try:validate(w,rt['net'],rt['lines'])
  except Exception as e:bad.append((rt,repr(e)))
 if not bad:break
 for rt,err in bad:
  pruned.append(dict(net=rt['net'],reason=err));routes.remove(rt);w['lines']=[p for p in w['lines'] if p['net']!=rt['net']]+[p for p in s['lines'] if p['net']==rt['net']];w['vias'] +=[p for p in s['vias'] if p['net']==rt['net']]
save();v=json.loads((OUT/'plan.json').read_text());v['pruned']=pruned;v['batch_final_geometry_pass']=bool(routes);(OUT/'plan.json').write_text(json.dumps(v,indent=2));assert sha(PCB)==cp['pcb_sha256'];print('DONE',len(routes),'safe offline candidates; native unchanged',flush=True)
