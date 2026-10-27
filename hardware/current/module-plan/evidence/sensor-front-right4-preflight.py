import pathlib,json,sys,math
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
from shapely.geometry import Point,LineString,box
from shapely.affinity import rotate
from shapely import from_wkb
E=pathlib.Path(__file__).parent
pads=json.loads((E/'sensor-front-exact-source-pads-fill0-current.json').read_text(encoding='utf-8'))['pads'];data=json.loads((E/'sensor-front-native-left8-readback-current.json').read_text(encoding='utf-8'))['value'];gnd=from_wkb((E/'sensor-front-real-bottom-ground-fill0-current.wkb').read_bytes())
turn=[f'R{i}' for i in range(11,15)];changes=[]
for p in pads:
 if p['ref'] in turn:
  c=next(c for c in data['components'] if c['designator']==p['ref']);p['x_mm']=2*c['x']*.0254-p['x_mm'];p['y_mm']=2*c['y']*.0254-p['y_mm'];p['angle']+=180
for ref in turn:
 c=next(c for c in data['components'] if c['designator']==ref);changes.append(dict(ref=ref,id=c['primitiveId'],old_rotation=c['rotation'],new_rotation=180))
obs=[]
for p in pads:
 s=p['shape'];w=s['width']*.0254;h=s['height']*.0254
 shape=Point(p['x_mm'],p['y_mm']).buffer(w/2,quad_segs=256) if s['padType']=='ELLIPSE' and abs(w-h)<1e-6 else rotate(box(p['x_mm']-w/2,p['y_mm']-h/2,p['x_mm']+w/2,p['y_mm']+h/2),p['angle'],origin=(p['x_mm'],p['y_mm']))
 obs.append((p['ref']+'.'+p['pin'],p['net'],shape,.1651))
for t in data['lines']:obs.append((t['primitiveId'],t['net'],LineString([(t['startX']*.0254,t['startY']*.0254),(t['endX']*.0254,t['endY']*.0254)]).buffer(t['lineWidth']*.0254/2,quad_segs=128),.1651))
for v in data['vias']:obs.append((v['primitiveId'],v['net'],Point(v['x']*.0254,v['y']*.0254).buffer(v['diameter']*.0254/2,quad_segs=256),.2501))
plan=[];bad=[]
for i in range(8,12):
 net=f'L0_M{i:02}';ps=[p for p in pads if p['net']==net];a=next(p for p in ps if p['ref']=='U1');b=next(p for p in ps if p['ref'].startswith('R'));dy=b['y_mm']-a['y_mm'];x1=33.5+abs(dy);pts=[(a['x_mm'],a['y_mm']),(33.5,a['y_mm']),(x1,b['y_mm']),(b['x_mm'],b['y_mm'])]
 if i==8:pts=[(a['x_mm'],a['y_mm']),(b['x_mm']-abs(dy),a['y_mm']),(b['x_mm'],b['y_mm'])]
 if i==13:pts=[(a['x_mm'],a['y_mm']),(31.15,a['y_mm']),(31.45,a['y_mm']+.3),(33.3,a['y_mm']+.3),(33.3+abs(b['y_mm']-a['y_mm']-.3),b['y_mm']),(b['x_mm'],b['y_mm'])]
 cu=LineString(pts).buffer(.1651/2,quad_segs=128)
 for name,n,ob,clearance in obs:
  if n!=net and cu.distance(ob)<clearance-1e-8:bad.append(dict(net=net,other=name,d=cu.distance(ob),required=clearance))
 missing=cu.difference(gnd).area
 if missing>1e-8:bad.append(dict(net=net,reference_missing_mm2=missing))
 obs.append((net,net,cu,.1651));plan.append(dict(net=net,points_mm=pts,width_mm=.1651,reference_missing_mm2=missing))
r=dict(scope='Right4 same-component180deg fanout; no circuit or footprint changes',rotation_changes=changes,tracks=plan,independent_preflight_pass=not bad,violations=bad,layer=1,all72_existing_copper_retained=True)
(E/'sensor-front-right4-manual-plan-current.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r))
