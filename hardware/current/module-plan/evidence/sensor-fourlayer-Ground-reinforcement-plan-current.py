from pathlib import Path
import json,sys,math,datetime,hashlib
sys.path.insert(0,r'D:\FPGA-Project\codex-tools\shapely')
from shapely.geometry import Point,LineString,box
from shapely.affinity import rotate
E=Path(__file__).parent
J=lambda f:json.loads((E/f).read_text(encoding='utf-8-sig'));pads=J('sensor-fourlayer-exact-source-pads-current.json')['pads'];a=J('sensor-fourlayer-reopened-DRC-current.json')['value'];src=Path(r'C:\Users\Sakuya\Documents\LCEDA-Pro\projects\FPGA-Music-U9ControlWork-20261023\pcb\PCB2.epcb2');h=hashlib.sha256(src.read_bytes()).hexdigest();assert h=='22eddc58e712c86d1a59bf90edf35955d4a5ebe5bb8a0f8a911416ff262cbb26'
def shape(p):
 s=p['shape'];w=s['width']*.0254;hh=s['height']*.0254
 return Point(p['x_mm'],p['y_mm']).buffer(w/2,quad_segs=256) if s['padType']=='ELLIPSE' and abs(w-hh)<1e-6 else rotate(box(p['x_mm']-w/2,p['y_mm']-hh/2,p['x_mm']+w/2,p['y_mm']+hh/2),p['angle'],origin=(p['x_mm'],p['y_mm']))
obs=[]
for p in pads:
 if p['layer']==12 and p['net']!='GND':obs.append((p['id'],p['net'],shape(p),.1651))
for v in a['vias']:
 if v['net']!='GND':obs.append((v['primitiveId'],v['net'],Point(v['x']*.0254,v['y']*.0254).buffer(v['diameter']*.0254/2,quad_segs=256),.2501011))
routes=[];bad=[]
for p in pads:
 if p['layer']!=12 or p['net']!='GND':continue
 for layer in [15,16]:
  for dx,dy in [(1.4,0),(-1.4,0),(0,1.4),(0,-1.4)]:
   pts=[[p['x_mm'],p['y_mm']],[p['x_mm']+dx,p['y_mm']+dy]];g=LineString(pts).buffer(.254/2,quad_segs=256);viol=[];margin=1e9
   for nm,net,o,cl in obs:
    d=g.distance(o);margin=min(margin,d-cl)
    if d<cl-1e-8:viol.append({'other':nm,'net':net,'gap':d,'required':cl})
   if g.distance(box(0,0,55,45).boundary)<.2999994-1e-8:viol.append({'error':'boardedgeclearance'})
   r={'Ground_pad':p['ref']+'.'+p['pin'],'net':'GND','layer':layer,'points':pts,'width_mm':.254,'minimum_extra_clearance_mm':margin,'physical_pass':not viol};routes.append(r)
   if viol:bad.append({'route':r,'violations':viol})
r={'at':datetime.datetime.now().astimezone().isoformat(),'source_sha256':h,'plan':'80realGNDtrack segments:4spokes for each of10GroundTHpads on2innerplanes; native sourceconductors, no polygonfakefill. Extend existing0.254mmthermalspokes to1.4mm fromPADcenter to bridge actual fineness8 notch. Original tracks/components/PADnets/clearance rules retained.','routes':routes,'physical_pass':not bad,'violations':bad,'native_applied':False,'accepted':False,'34reference_gate_not_waived':True,'physical_tests':'UNMEASURED'};assert len(routes)==80;(E/'sensor-fourlayer-Ground-reinforcement-plan-current.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in r.items() if k!='routes'},ensure_ascii=True));assert not bad
