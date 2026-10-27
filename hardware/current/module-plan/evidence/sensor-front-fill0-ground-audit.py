import sys,math,json,collections,hashlib,datetime
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
from pathlib import Path
from shapely.geometry import Point,LineString,Polygon
from shapely.ops import unary_union
E=Path(__file__).parent;src=E/'sensor-front-fill0-current.epcb2';docs={};cur=None
for ln in src.read_text(encoding='utf-8-sig').splitlines():
 raw=ln.rstrip('|')
 if '||' not in raw:continue
 a,b=raw.split('||',1);a=json.loads(a);b=json.loads(b)
 if a['type']=='DOCHEAD':cur=b['uuid'];docs[cur]={}
 docs[cur][a.get('id',a['type'])]=(a,b)
rr=docs['f52674d6627fca6f'];attrs=collections.defaultdict(dict);comps={};nets={}
for a,b in rr.values():
 if a['type']=='ATTR':attrs[b['parentId']][b['key']]=b['value']
 elif a['type']=='COMPONENT':comps[a['id']]=b
 elif a['type']=='PAD_NET':key=json.loads(a['id']);nets[key[1],key[3]]=b['padNet']
pads=[]
for cid,c in comps.items():
 theta=math.radians(c['angle']);co,si=math.cos(theta),math.sin(theta)
 for a,p in docs[attrs[cid]['Footprint']].values():
  if a['type']!='PAD':continue
  x,y=p['centerX'],p['centerY'];pa=math.radians(p['padAngle']);ox,oy=p.get('padOffsetX',0) or 0,p.get('padOffsetY',0) or 0;hx=x+ox*math.cos(pa)-oy*math.sin(pa);hy=y+ox*math.sin(pa)+oy*math.cos(pa)
  pads.append(dict(ref=attrs[cid]['Designator'],pin=p['num'],net=nets[cid,a['id']],id=cid+a['id'],layer=p['layerId'],x_mm=(c['x']+x*co-y*si)*.0254,y_mm=(c['y']+x*si+y*co)*.0254,hole_x_mm=(c['x']+hx*co-hy*si)*.0254,hole_y_mm=(c['y']+hx*si+hy*co)*.0254,shape=p['defaultPad'],angle=c['angle']+p['padAngle'],hole=p['hole']))
exp=json.loads((E/'sensor-front-expected-pin-nets-current.json').read_text(encoding='utf-8'))['expected_pin_nets'];assert len(pads)==150 and all(p['net']==(exp[p['ref']][p['pin']] or '') for p in pads)
(E/'sensor-front-exact-source-pads-fill0-current.json').write_text(json.dumps(dict(source=str(src),source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),source_pin_map_pass=True,pads=pads,pad_offset_scope='hole offset per officialformat/pcb/pad_via.md; copper origin unchanged'),ensure_ascii=False,indent=2),encoding='utf-8')
def points(src):
 while src and isinstance(src[0],list):
  assert len(src)==1;src=src[0]
 x,y=src[:2];pts=[(x*.254,y*.254)];i=2
 while i<len(src):
  if src[i]=='L':i+=1;continue
  if src[i]=='ARC':
   deg,nx,ny=src[i+1:i+4];i+=4;dx,dy=nx-x,ny-y;theta=math.radians(deg);ll=math.hypot(dx,dy);hh=ll/(2*math.tan(theta/2));cx=(x+nx)/2-dy/ll*hh;cy=(y+ny)/2+dx/ll*hh;rad=math.hypot(x-cx,y-cy);phi=math.atan2(y-cy,x-cx);n=max(1,math.ceil(abs(deg)/360*1024));pts.extend(((cx+rad*math.cos(phi+theta*j/n))*.254,(cy+rad*math.sin(phi+theta*j/n))*.254) for j in range(1,n+1));x,y=nx,ny
  else:x,y=src[i:i+2];i+=2;pts.append((x*.254,y*.254))
 return pts
# Native POURED source uses10mil coordinates; copper/via/pad source usesmil.
po=next(b for a,b in rr.values() if a['type']=='POURED');cu=[]
for f in po['pourFill']:
 if f['fill']:
  g=Polygon(points(f['path'][0]))
  for q in f['path'][1:]:g=g.symmetric_difference(Polygon(points(q)))
 else:g=LineString(points(f['path'])).buffer(f['strokeWidth']*.254/2,quad_segs=256)
 cu.append(g)
vs=[dict(b,id=a['id']) for a,b in rr.values() if a['type']=='VIA'];holes=[]
for p in pads:
 if p['hole']:
  assert p['hole']['holeType']=='ROUND';holes.append(Point(p['hole_x_mm'],p['hole_y_mm']).buffer(p['hole']['width']*.0254/2,quad_segs=256))
for v in vs:holes.append(Point(v['centerX']*.0254,v['centerY']*.0254).buffer(v['holeDiameter']*.0254/2,quad_segs=256))
ground=unary_union(cu).difference(unary_union(holes));polys=list(ground.geoms) if hasattr(ground,'geoms') else [ground];main=max(polys,key=lambda p:p.area);contacts=[]
for v in vs:
 p=Point(v['centerX']*.0254,v['centerY']*.0254);ann=p.buffer(v['viaDiameter']*.0254/2,quad_segs=256).difference(p.buffer(v['holeDiameter']*.0254/2,quad_segs=256));contacts.append(dict(id=v['id'],Bottom_contact_mm2=main.intersection(ann).area))
returns=[]
for p in pads:
 if p['layer']!=12 or p['net'] in ['GND','3V3_IO']:continue
 v=min(vs,key=lambda v:math.hypot(v['centerX']*.0254-p['hole_x_mm'],v['centerY']*.0254-p['hole_y_mm']));returns.append(dict(ref=p['ref'],pin=p['pin'],net=p['net'],Ground_via_id=v['id'],distance_mm=math.hypot(v['centerX']*.0254-p['hole_x_mm'],v['centerY']*.0254-p['hole_y_mm'])))
report=dict(time=datetime.datetime.now().astimezone().isoformat(),scope='PRE_SIGNAL_ROUTE_BOTTOM_REAL_GROUND_AND21_REAL_PTH_RETURNS_ONLY',source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),pads=150,drills_subtracted=len(holes),Ground_vias=len(vs),ground_components=len(polys),ground_areas_mm2=sorted([p.area for p in polys],reverse=True),contacts=contacts,minimum_actual_contact_mm2=min(p['Bottom_contact_mm2'] for p in contacts),all_contacts_ge_0_15=all(p['Bottom_contact_mm2']>=.15 for p in contacts),signal_PTH_returns=returns,all_returns_le_1_5=all(p['distance_mm']<=1.5 for p in returns),not_full_signal_reference_or_final_DRC_acceptance=True,physical_tests='UNMEASURED',prior_input_error='First inline parser encountered native DOCEND separator, next input defaultGBKdecode failed before geometry; Native false-filled thermal strokes also required unwrapping their single path list; this source uses explicitUTF8, skips DOCEND and uses documented hole offsets.')
(E/'sensor-front-native-fill0-ground-contact-current.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');(E/'sensor-front-real-bottom-ground-fill0-current.wkb').write_bytes(main.wkb);print(json.dumps({k:v for k,v in report.items() if k not in ['contacts','signal_PTH_returns','prior_input_error']},ensure_ascii=True))

from shapely.geometry import box
from shapely.affinity import rotate
check=[]
for p in pads:
 if p['layer']!=12 or p['net'] in ['GND','3V3_IO']:continue
 center=Point(p['hole_x_mm'],p['hole_y_mm']);exempt=center.buffer(1,quad_segs=256); directions=[]
 for deg in (0,90,180,270):
  corridor=rotate(box(p['x_mm'],p['y_mm']-.1651/2,p['x_mm']+2,p['y_mm']+.1651/2),deg,origin=(p['x_mm'],p['y_mm']))
  missing=corridor.difference(exempt).difference(main)
  directions.append(dict(deg=deg,unreferenced_mm2=missing.area,pass_1e_8mm2=missing.area<=1e-8))
 check.append(dict(ref=p['ref'],pin=p['pin'],directions=directions))
eroded=main.buffer(-.1651/2,quad_segs=256)
checks=dict(scope='Actual Bottom fill local candidate diagnosis, not signal-routing acceptance',signal_PTH_cardinal_escape=check,pass_at_least_one_full_width_cardinal_escape=all(any(d['pass_1e_8mm2'] for d in p['directions']) for p in check),eroded_ground_components_at_0_1651mm_neck=len(eroded.geoms) if hasattr(eroded,'geoms') else 1,eroded_ground_area_mm2=eroded.area,neck_scope='Erosion topology only; final all-contact/minimum-neck manufacturing audit pending',strict_reference_and_neck_gates_unchanged=True)
(E/'sensor-front-fill0-reference-diagnosis-current.json').write_text(json.dumps(checks,indent=2),encoding='utf-8');print(json.dumps(checks))
