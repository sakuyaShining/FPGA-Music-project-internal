from pathlib import Path
import json,datetime,sys,math
sys.path.insert(0,r'D:\FPGA-Project\codex-tools\shapely')
from shapely.geometry import Point,LineString,box
from shapely.affinity import rotate
E=Path(__file__).parent
J=lambda f:json.loads((E/f).read_text(encoding='utf-8-sig'))
v=J('sensor-today-PCB-state-after-geometry-current.json')['value'];old=J('sensor-today-PCB-sync-preflight-current.json')['value'];c=J('sensor-fourlayer-control-candidate-current.json');sourcepads=J('sensor-front-exact-source-pads-14nets-current.json')['pads'];actualnets={p['primitiveId']:p['net'] for p in v['pads']};oldids={x['primitiveId'] for x in old['lines']};newlines=[x for x in v['lines'] if x['primitiveId'] not in oldids];byid={x['primitiveId']:x for x in v['lines']};assert all(byid[x['primitiveId']]==x for x in old['lines']);assert v['rules']==old['rules']
obs=[]
for p in sourcepads:
 s=p['shape'];w=s['width']*.0254;h=s['height']*.0254;g=Point(p['x_mm'],p['y_mm']).buffer(w/2,quad_segs=256) if s['padType']=='ELLIPSE' and abs(w-h)<1e-6 else rotate(box(p['x_mm']-w/2,p['y_mm']-h/2,p['x_mm']+w/2,p['y_mm']+h/2),p['angle'],origin=(p['x_mm'],p['y_mm']));obs.append((p['id'],actualnets[p['id']],g,.1651,{1,2} if p['layer']==12 else {p['layer']},'PAD'))
for x in v['lines']:obs.append((x['primitiveId'],x['net'],LineString([(x['startX']*.0254,x['startY']*.0254),(x['endX']*.0254,x['endY']*.0254)]).buffer(x['lineWidth']*.0254/2,quad_segs=256),.1651,{x['layer']},'LINE'))
for x in v['vias']:obs.append((x['primitiveId'],x['net'],Point(x['x']*.0254,x['y']*.0254).buffer(x['diameter']*.0254/2,quad_segs=256),.2501011,{1,2},'VIA'))
newids={x['primitiveId'] for x in newlines}|{x['primitiveId'] for x in v['vias']};bad=[];mins=[]
for nm,n,g,cl,ls,k in obs:
 if nm not in newids:continue
 margin=1e9
 for on,net,geo,clear,layers,kind in obs:
  if n==net or not ls&layers:continue
  d=g.distance(geo);req=max(cl,clear);margin=min(margin,d-req)
  if d<req-1e-8:bad.append({'own':nm,'other':on,'kind':kind,'actual_mm':d,'required_mm':req})
 mins.append({'id':nm,'minimum_extra_clearance_mm':margin})
holes=[{'id':x['primitiveId'],'xy':[x['x']*.0254,x['y']*.0254],'drill':x['holeDiameter']*.0254} for x in v['vias']]
for p in sourcepads:
 if p['hole']:holes.append({'id':p['id'],'xy':[p['hole_x_mm'],p['hole_y_mm']],'drill':p['hole']['width']*.0254})
hbad=[]
for i,h in enumerate(holes):
 for k in holes[i+1:]:
  gap=math.dist(h['xy'],k['xy'])-(h['drill']+k['drill'])/2
  if gap<.2999994-1e-8:hbad.append({'a':h['id'],'b':k['id'],'gap_mm':gap})
out={'at':datetime.datetime.now().astimezone().isoformat(),'source_all91Cu_preserved':True,'rules_identical':True,'actual_lines':len(v['lines']),'actual_added_lines':len(newlines),'actual_vias':len(v['vias']),'physical_clearance_pass':not bad,'violations':bad,'drill_spacing_pass':not hbad,'drill_violations':hbad,'minimum_clearance_margins':mins,'native_canonicalization':'Native save merged near-collinear first2 E13 header segments into chord [5.00000016,8.53000072]-[5.9,10.45]. Actual chord independently rechecked with every PAD/via/source/newCu at unchanged exact source rules; no geometric-match waiver or new clearance exception. Other differences require actual source capture audit.','accepted':False,'ground_reference_DC_pending':True}
(E/'sensor-fourlayer-native-geometry-audit-current.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in out.items() if k not in ['minimum_clearance_margins']},ensure_ascii=False));assert not bad and not hbad
