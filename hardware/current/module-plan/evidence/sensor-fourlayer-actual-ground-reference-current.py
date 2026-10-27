import sys,math,json,collections,hashlib,datetime
sys.path.insert(0,'D:/FPGA-Project/codex-tools/shapely')
from pathlib import Path
from shapely.geometry import Point,LineString,Polygon
from shapely.ops import unary_union
E=Path(__file__).parent;src=E/'sensor-fourlayer-native-current.epcb2';docs={};cur=None
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

from shapely.geometry import box
from shapely.affinity import rotate
from shapely import union_all
netlist=json.loads((E/'sensor-fourlayer-trial-schematic-netlist-current.json').read_text(encoding='utf-8'));expected={(v['props']['Designator'],k):x['net'] for v in netlist['components'].values() for k,x in v['pinInfoMap'].items()};assert len(pads)==len(expected)==150 and all(p['net']==expected[p['ref'],p['pin']] for p in pads)
(E/'sensor-fourlayer-exact-source-pads-current.json').write_text(json.dumps({'source':str(src),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'all150netlist_PADs_match':True,'pads':pads},ensure_ascii=False,indent=2),encoding='utf-8')
vs=[dict(b,id=a['id']) for a,b in rr.values() if a['type']=='VIA'];holes=[]
for p in pads:
 if p['hole']:holes.append(Point(p['hole_x_mm'],p['hole_y_mm']).buffer(p['hole']['width']*.0254/2,quad_segs=256))
for v in vs:holes.append(Point(v['centerX']*.0254,v['centerY']*.0254).buffer(v['holeDiameter']*.0254/2,quad_segs=256))
hole_union=union_all(holes)
pourby={a['id']:b for a,b in rr.values() if a['type']=='POUR'};planes={};plane_reports=[]
for h,po in rr.values():
 if h['type']!='POURED':continue
 pid=json.loads(h['id'])[1];border=pourby[pid];cu=[]
 for f in po['pourFill']:
  if f['fill']:
   g=Polygon(points(f['path'][0]))
   for q in f['path'][1:]:g=g.symmetric_difference(Polygon(points(q)))
  else:g=LineString(points(f['path'])).buffer(f['strokeWidth']*.254/2,quad_segs=256)
  cu.append(g)
 layer=border['layerId'];poured_only=union_all(cu).difference(hole_union);poured_parts=list(poured_only.geoms) if hasattr(poured_only,'geoms') else [poured_only];poured_main=max(poured_parts,key=lambda p:p.area)
 # Actual source Ground conductors on this layer, not hypothetical fill.
 for hh,t in rr.values():
  if hh['type']=='LINE' and t['layerId']==layer and t['netName']=='GND':cu.append(LineString([(t['startX']*.0254,t['startY']*.0254),(t['endX']*.0254,t['endY']*.0254)]).buffer(t['width']*.0254/2,quad_segs=256))
 for p in pads:
  if p['layer']==12 and p['net']=='GND':
   assert p['shape']['padType']=='ELLIPSE' and abs(p['shape']['width']-p['shape']['height'])<1e-6
   cu.append(Point(p['x_mm'],p['y_mm']).buffer(p['shape']['width']*.0254/2,quad_segs=256))
 for v in vs:
  if v['netName']=='GND':cu.append(Point(v['centerX']*.0254,v['centerY']*.0254).buffer(v['viaDiameter']*.0254/2,quad_segs=256))
 ground=union_all(cu).difference(hole_union);polys=list(ground.geoms) if hasattr(ground,'geoms') else [ground];main=max(polys,key=lambda p:p.area);planes[layer]=ground;(E/f'sensor-fourlayer-real-ground-layer{layer}-current.wkb').write_bytes(ground.wkb);contacts=[]
 for v in vs:
  if v['netName']!='GND':continue
  p=Point(v['centerX']*.0254,v['centerY']*.0254);ann=p.buffer(v['viaDiameter']*.0254/2,quad_segs=256).difference(p.buffer(v['holeDiameter']*.0254/2,quad_segs=256));contacts.append({'id':v['id'],'main_plane_contact_mm2':poured_main.intersection(ann).area,'full_actual_Ground_contact_mm2':main.intersection(ann).area})
 plane_reports.append({'layer':layer,'native_fineness':border['pourType']['fineness'],'keepIsland':border['keepIsland'],'components':len(polys),'areas_mm2':sorted([p.area for p in polys],reverse=True),'Ground_via_contacts':contacts,'all_Ground_vias_contact_ge0_15':all(x['main_plane_contact_mm2']>=.15 for x in contacts),'minimum_contact_mm2':min(x['main_plane_contact_mm2'] for x in contacts)})

def padshape(p):
 s=p['shape'];w=s['width']*.0254;hh=s['height']*.0254
 return Point(p['x_mm'],p['y_mm']).buffer(w/2,quad_segs=256) if s['padType']=='ELLIPSE' and abs(w-hh)<1e-6 else rotate(box(p['x_mm']-w/2,p['y_mm']-hh/2,p['x_mm']+w/2,p['y_mm']+hh/2),p['angle'],origin=(p['x_mm'],p['y_mm']))
terminal={}
for p in pads:
 if p['layer']==12 and p['net'] not in ['GND','3V3_IO']:terminal.setdefault(p['net'],[]).append(padshape(p).buffer(.1651+1e-5,quad_segs=256))
for v in vs:
 if v['netName']!='GND':terminal.setdefault(v['netName'],[]).append(Point(v['centerX']*.0254,v['centerY']*.0254).buffer(v['viaDiameter']*.0254/2+.1651+1e-5,quad_segs=256))
terminal={n:union_all(z) for n,z in terminal.items()};checks=[]
for h,t in rr.values():
 if h['type']!='LINE' or t['netName']=='GND' or t['layerId'] not in [1,2]:continue
 layer=t['layerId'];ref=15 if layer==1 else 16;pts=[(t['startX']*.0254,t['startY']*.0254),(t['endX']*.0254,t['endY']*.0254)];cu=LineString(pts).buffer(t['width']*.0254/2,quad_segs=256);missing=cu.difference(planes[ref]);outside=missing.difference(terminal[t['netName']]) if t['netName'] in terminal else missing
 checks.append({'id':h['id'],'net':t['netName'],'layer':layer,'reference_layer':ref,'fullwidth_missing_mm2':missing.area,'missing_outside_unchanged_terminal_mm2':outside.area,'pass':outside.area<=1e-8})
ret=[]
for p in pads:
 if p['layer']!=12 or p['net'] in ['GND','3V3_IO']:continue
 near=min((v for v in vs if v['netName']=='GND'),key=lambda v:math.dist([v['centerX']*.0254,v['centerY']*.0254],[p['hole_x_mm'],p['hole_y_mm']]));dist=math.dist([near['centerX']*.0254,near['centerY']*.0254],[p['hole_x_mm'],p['hole_y_mm']]);ret.append({'ref':p['ref'],'pin':p['pin'],'Ground_via':near['id'],'distance_mm':dist,'pass':dist<=1.5})
report={'at':datetime.datetime.now().astimezone().isoformat(),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'all150PAD_matches':True,'planes':plane_reports,'signal_reference_checks':checks,'all_source_signal_reference_pass':all(x['pass'] for x in checks),'max_missing_outside_unchanged_terminal_mm2':max(x['missing_outside_unchanged_terminal_mm2'] for x in checks),'failed_reference_lines':[x for x in checks if not x['pass']],'TH_returns':ret,'all_TH_returns_within1_5mm':all(x['pass'] for x in ret),'native_saved_closed_reopened_strict_DRC_errors':0,'minimum_neck_and_old_contact_DC_full_acceptance_pending':True,'actualGround_scope':'NativePOURED plus actualsame-layerGroundtracks, physicalGroundTHPAD/viaannuli; all actualdrills subtracted. Poured-via contactgate remains purepoured area, not selfannulus.','accepted':False,'physical_tests':'UNMEASURED'}
(E/'sensor-fourlayer-actual-ground-reference-current.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k not in ['planes','signal_reference_checks','TH_returns','failed_reference_lines']},ensure_ascii=False));print('planes',[(x['layer'],x['components'],x['minimum_contact_mm2'],x['all_Ground_vias_contact_ge0_15']) for x in plane_reports]);print('failedreferences',len(report['failed_reference_lines']),report['failed_reference_lines'][:12])
