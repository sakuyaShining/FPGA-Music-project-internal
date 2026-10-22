"""Search C35 with cached copper plus actual footprint graphics envelopes."""
import sys,json,math,hashlib,copy,shutil
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
assert not (BASE/'native-candidate-checkpoint.json').exists(), 'Accepted r7 stage is frozen; continue in a new source-bound stage instead of replaying it'
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT))
from four_layer_geometry import copper,connected
from physical_geometry import actual_pad
from resume_offline import read_native
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
from shapely.affinity import rotate,translate
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();info=json.loads((BASE/'native-candidate-source.json').read_text(encoding='utf-8'));PCB=Path(info['candidate_project'])/'pcb/PCB1.epcb2';raw=read_native(PCB);s=json.loads((BASE/'native-verified-capture.json').read_text(encoding='utf-8'))
s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in raw.items() if k=='VIA']
audit=json.loads((BASE/'native-courtyard-repair-audit.json').read_text(encoding='utf-8'));first=json.loads((BASE/'native-decoupling-audit.json').read_text(encoding='utf-8'));remove=audit['result']['createdL'];oldvia=next(p for p in s['vias'] if p['id']==first['result']['createdV'][0]);oldpads=[p for p in s['pads'] if p['ref']=='C35'];w={**s,'pads':[p for p in s['pads'] if p['ref']!='C35'],'lines':[p for p in s['lines'] if p['id'] not in remove],'vias':[p for p in s['vias'] if p['id']!=oldvia['id']]}
# Replay all embedded documents, including footprint records.
docs={};cur=None
for text in PCB.read_text(encoding='utf-8').splitlines():
 if '||' not in text:continue
 header,body=text.split('||',1);h=json.loads(header);v=json.loads(body.rstrip('|')) if body.rstrip('|').strip() else None
 if h['type']=='DOCHEAD':cur=v['uuid'];docs.setdefault(cur,{})
 if cur:docs[cur][h['type'],h.get('id')]=v
def points(path):
 if path and path[0]=='CIRCLE':
  _,x,y,r=path;return [(x-r,y-r),(x+r,y+r)]
 if not path or not isinstance(path[0],(int,float)):return []
 x,y=path[:2];out=[(x,y)];i=2;mode=None
 while i<len(path):
  if isinstance(path[i],str):mode=path[i];i+=1
  if mode=='L':x,y=path[i:i+2];i+=2;out.append((x,y))
  elif mode=='ARC':
   angle,tx,ty=path[i:i+3];i+=3;t=math.radians(angle);dx,dy=tx-x,ty-y
   if abs(t)>1e-8:
    cx=(x+tx)/2-dy/(2*math.tan(t/2));cy=(y+ty)/2+dx/(2*math.tan(t/2));r=math.hypot(x-cx,y-cy);out.extend([(cx-r,cy-r),(cx+r,cy+r)])
   x,y=tx,ty;out.append((x,y))
  else:break
 return out
attrs={}
for (k,i),v in raw.items():
 if k=='ATTR':attrs.setdefault(v['parentId'],{})[v['key']]=v['value']
boxes={};local_cap=None
for cid,a in attrs.items():
 if 'Designator' not in a or 'Footprint' not in a or ('COMPONENT',cid) not in raw:continue
 f=docs[a['Footprint']];geoms=[]
 for (k,i),p in f.items():
  if not p:continue
  if k=='POLY':
   pts=points(p.get('path',[]));sw=p.get('width',0)/2
   if pts:geoms.append(box(min(x for x,y in pts)-sw,min(y for x,y in pts)-sw,max(x for x,y in pts)+sw,max(y for x,y in pts)+sw))
  if k=='PAD':
   q=p['defaultPad'];x,y=p['centerX'],p['centerY'];g=box(x-q['width']/2,y-q['height']/2,x+q['width']/2,y+q['height']/2);geoms.append(rotate(g,p.get('padAngle',0),origin=(x,y)))
 if not geoms:continue
 geometry=unary_union(geoms);c=raw['COMPONENT',cid];g=translate(rotate(geometry,c['angle'],origin=(0,0)),c['x'],c['y']);bounds=[v*.0254 for v in g.bounds];boxes[a['Designator']]=box(*bounds)
 if a['Designator']=='C35':local_cap=geometry
assert local_cap is not None
foreign={};allpads=unary_union([actual_pad(p) for p in w['pads']]);mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
for net in ['3V3_PERIPH','GND']:
 f,ps=copper(w,net);foreign[net]={l:unary_union(gs) for l,gs in f.items()};foreign[net]['all']=unary_union([q for gs in f.values() for q in gs])
vcc=next(p for p in s['pads'] if p['ref']=='U15' and p['n']=='20');vp=(vcc['x']*.0254,vcc['y']*.0254)
candidates=[]
for rotation in [180,90,270,0]:
 theta=math.radians(rotation)
 for x in [round(75.5+i*.1,2) for i in range(31)]:
  for y in [round(44.4+i*.1,2) for i in range(29)]:
   sh=translate(rotate(local_cap,rotation,origin=(0,0)),x/.0254,y/.0254);cb=box(*[v*.0254 for v in sh.bounds]);gap=min(cb.distance(q) for ref,q in boxes.items() if ref!='C35')
   if gap<.505:continue
   ps=[]
   for p in oldpads:
    # Embedded C35 pin1=-0.7mm; pin2=+0.7mm in local zero-rotation frame.
    u=-.7 if p['n']=='1' else .7;ps.append({**p,'x':(x+u*math.cos(theta))/.0254,'y':(y+u*math.sin(theta))/.0254,'rotation':rotation})
   a=next(p for p in ps if p['n']=='1');b=next(p for p in ps if p['n']=='2');ap=(a['x']*.0254,a['y']*.0254);bp=(b['x']*.0254,b['y']*.0254);length=math.dist(ap,vp)
   if length>3.:continue
   try:
    for p in ps:assert actual_pad(p).distance(foreign[p['net']][1])>=.2
    powerline=LineString([ap,vp]);assert powerline.distance(foreign['3V3_PERIPH'][1])-.33528/2>=.165
   except AssertionError:continue
   for dx,dy in [(-.9,0),(0,-.9),(0,.9),(-.7,-.7),(-.7,.7),(.9,0),(.7,-.7),(.7,.7)]:
    q=Point(bp[0]+dx,bp[1]+dy);gndline=LineString([bp,(q.x,q.y)])
    if q.distance(foreign['GND']['all'])-.3048<.165 or q.distance(allpads)-.1524<.25 or any(q.distance(actual_pad(p))-.1524<.25 for p in ps):continue
    if gndline.distance(foreign['GND'][1])-.127<.165 or q.distance(mount)<.3048+.15:continue
    if any(q.distance(Point(v['x']*.0254,v['y']*.0254))-(12+v['hole'])*.0254/2<.35 for v in w['vias']):continue
    candidates.append(dict(x=x,y=y,rotation=rotation,pads=ps,via={**oldvia,'x':q.x/.0254,'y':q.y/.0254},power_mm=length,ground_mm=math.hypot(dx,dy),footprint_bbox_gap_mm=gap));break
assert candidates,'No acceptable same-side pocket under 3mm VCC routing budget'
best=min(candidates,key=lambda p:p['power_mm']+p['ground_mm']);power=next(p for p in best['pads'] if p['n']=='1');ground=next(p for p in best['pads'] if p['n']=='2');v=best['via']
def line(net,a,b,width):return dict(net=net,layer=1,x1=a[0],y1=a[1],x2=b[0],y2=b[1],width=width/.0254)
ls=[line('3V3_PERIPH',(power['x'],power['y']),(vcc['x'],vcc['y']),.33528),line('GND',(ground['x'],ground['y']),(v['x'],v['y']),.254)];work={**w,'pads':w['pads']+best['pads'],'lines':w['lines']+ls,'vias':w['vias']+[v]}
assert connected([p for p in work['pads'] if p['net']=='3V3_PERIPH'],[p for p in work['lines'] if p['net']=='3V3_PERIPH'],[p for p in work['vias'] if p['net']=='3V3_PERIPH'])['complete']
plan=dict(source_pcb_sha256=sha(PCB),source_capture=str(BASE/'second-position-native-verified-capture.json'),source_capture_sha256=sha(BASE/'native-verified-capture.json'),component='C35',component_x_mm=best['x'],component_y_mm=best['y'],component_rotation=best['rotation'],pads=best['pads'],remove_line_ids=remove,remove_via_ids=[],lines=ls,vias=[],retained_ground_via_id=v['id'],via_move=dict(id=v['id'],x=v['x'],y=v['y']),vcc_centerline_mm=best['power_mm'],ground_stub_mm=best['ground_mm'],device_bbox_gap_estimate_mm=best['footprint_bbox_gap_mm'],accepted_candidates=len(candidates),requires_native_device_spacing_check=True,native_imported=False,manufacturing_release=False)
(BASE/'final-decoupling-plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8');(BASE/'final-decoupling-working.json').write_text(json.dumps(work),encoding='utf-8');(BASE/'footprint-graphics-envelopes.json').write_text(json.dumps({r:q.bounds for r,q in boxes.items()},indent=2),encoding='utf-8')
for name in ['native-drc.json','native-drc-meta.json','native-verified-capture.json']:
 target=BASE/('second-position-'+name);assert not target.exists();shutil.copy2(BASE/name,target)
print(json.dumps({k:v for k,v in plan.items() if k not in ['pads','lines']},indent=2),flush=True)
