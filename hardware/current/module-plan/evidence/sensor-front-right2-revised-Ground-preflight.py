import json,sys,pathlib,math
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
from shapely.geometry import Point,LineString,box
from shapely.affinity import rotate
from shapely import from_wkb
E=pathlib.Path(__file__).parent;data=json.loads((E/'sensor-front-native-12nets-reopened-DRC-current.json').read_bytes())['value'];pads=json.loads((E/'sensor-front-exact-source-pads-12nets-current.json').read_text())['pads'];plane=from_wkb((E/'sensor-front-real-bottom-ground-12nets-current.wkb').read_bytes());gid='05deb90db32fb69b';lid='8a4f214bf2967f5f'
v=next(v for v in data['vias'] if v['primitiveId']==gid);old_drill=Point(v['x']*.0254,v['y']*.0254).buffer(v['holeDiameter']*.0254/2,quad_segs=256);new_drill=Point(33.7,20.45).buffer(v['holeDiameter']*.0254/2,quad_segs=256);expected_plane=plane.union(old_drill).difference(new_drill)
for p in pads:
 if p['ref'] in ['R15','R16']:
  c=next(c for c in data['components'] if c['designator']==p['ref']);nx=38 if p['ref']=='R15' else c['x']*.0254;p['x_mm']=nx+c['x']*.0254-p['x_mm'];p['y_mm']=2*c['y']*.0254-p['y_mm'];p['angle']+=180
obs=[]
for p in pads:
 s=p['shape'];w=s['width']*.0254;h=s['height']*.0254;shape=Point(p['x_mm'],p['y_mm']).buffer(w/2,quad_segs=256) if s['padType']=='ELLIPSE' and abs(w-h)<1e-6 else rotate(box(p['x_mm']-w/2,p['y_mm']-h/2,p['x_mm']+w/2,p['y_mm']+h/2),p['angle'],origin=(p['x_mm'],p['y_mm']));obs.append((p['ref']+'.'+p['pin'],p['net'],shape,.1651))
for t in data['lines']:
 if t['primitiveId']==lid: pts=[(t['startX']*.0254,t['startY']*.0254),(33.7,20.45)]
 else:pts=[(t['startX']*.0254,t['startY']*.0254),(t['endX']*.0254,t['endY']*.0254)]
 obs.append((t['primitiveId'],t['net'],LineString(pts).buffer(t['lineWidth']*.0254/2,quad_segs=256),.1651))
for t in data['vias']:obs.append((t['primitiveId'],t['net'],Point(33.7,20.45).buffer(t['diameter']*.0254/2,quad_segs=256) if t['primitiveId']==gid else Point(t['x']*.0254,t['y']*.0254).buffer(t['diameter']*.0254/2,quad_segs=256),.2501))
tracks=[];bad=[]
for i in [12,13]:
 net=f'L0_M{i:02}';a=next(p for p in pads if p['ref']=='U1' and p['net']==net);b=next(p for p in pads if p['ref'].startswith('R') and p['net']==net)
 if i==12:pts=[(a['x_mm'],a['y_mm']),(b['x_mm']-abs(b['y_mm']-a['y_mm']),a['y_mm']),(b['x_mm'],b['y_mm'])]
 else:pts=[(a['x_mm'],a['y_mm']),(31.2,a['y_mm']),(31.325,22.30013472),(34.15,22.30013472),(34.4,22.05013472),(34.4,b['y_mm']+(b['x_mm']-34.4)),(b['x_mm'],b['y_mm'])]
 cu=LineString(pts).buffer(.1651/2,quad_segs=256)
 for name,n,g,c in obs:
  if n!=net and cu.distance(g)<c-1e-8:bad.append(dict(net=net,other=name,d=cu.distance(g),required=c))
 miss=cu.difference(expected_plane).area
 if miss>1e-8:bad.append(dict(net=net,expected_reference_missing_mm2=miss))
 obs.append((net,net,cu,.1651));tracks.append(dict(net=net,points_mm=pts,width_mm=.1651,expected_reference_missing_mm2=miss))
for name in [gid,lid]:
 ob=next(o for o in obs if o[0]==name)
 for nm,n,g,c in obs:
  if n!='GND' and ob[2].distance(g)<max(c,ob[3])-1e-8:bad.append(dict(object=name,other=nm,d=ob[2].distance(g),required=max(c,ob[3])))
r=dict(scope='Changed real C3 Groundvia escape and same-part R15/R16 placement; preserve all other83Cu/36vias',tracks=tracks,ground_via_change={'id':gid,'from_mm':[v['x']*.0254,v['y']*.0254],'to_mm':[33.7,20.45],'diameter_mm':v['diameter']*.0254,'drill_mm':v['holeDiameter']*.0254},ground_line_change={'id':lid,'end_mm':[33.7,20.45]},component_changes=[{'ref':'R15','id':next(c['primitiveId'] for c in data['components'] if c['designator']=='R15'),'x_mm':38,'rotation':180},{'ref':'R16','id':next(c['primitiveId'] for c in data['components'] if c['designator']=='R16'),'rotation':180}],expected_plane_only=True,native_refill_and_actual_reference_required=True,violations=bad,independent_preflight_pass=not bad)
(E/'sensor-front-right2-revised-Ground-plan-current.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r))
