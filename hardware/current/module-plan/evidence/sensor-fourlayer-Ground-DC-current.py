from pathlib import Path
import json,sys,datetime,hashlib
sys.path.insert(0,r'D:\FPGA-Project\codex-tools\shapely')
from shapely.geometry import Point,LineString,box
from shapely.affinity import rotate
from shapely import union_all,from_wkb
E=Path(__file__).parent
J=lambda f:json.loads((E/f).read_text(encoding='utf-8-sig'))
pads=J('sensor-fourlayer-exact-source-pads-current.json')['pads'];a=J('sensor-fourlayer-signal-repair-reopened-DRC-current.json')['value'];old=J('sensor-today-PCB-sync-preflight-current.json')['value'];live=Path(r'C:\Users\Sakuya\Documents\LCEDA-Pro\projects\FPGA-Music-U9ControlWork-20261023\pcb\PCB2.epcb2');h=hashlib.sha256(live.read_bytes()).hexdigest();assert h==hashlib.sha256((E/'sensor-fourlayer-native-current.epcb2').read_bytes()).hexdigest()
def shape(p):
 q=p['shape'];w=q['width']*.0254;hh=q['height']*.0254
 return Point(p['x_mm'],p['y_mm']).buffer(w/2,quad_segs=256) if q['padType']=='ELLIPSE' and abs(w-hh)<1e-6 else rotate(box(p['x_mm']-w/2,p['y_mm']-hh/2,p['x_mm']+w/2,p['y_mm']+hh/2),p['angle'],origin=(p['x_mm'],p['y_mm']))
obs=[];seeds=[]
for p in pads:
 if p['net']!='GND':continue
 g=shape(p)
 if p['hole']:
  g=g.difference(Point(p['hole_x_mm'],p['hole_y_mm']).buffer(p['hole']['width']*.0254/2,quad_segs=256));seeds.append((p['ref']+'.'+p['pin'],g))
 obs.append((p['ref']+'.'+p['pin'],'PAD',g))
for v in a['vias']:
 if v['net']!='GND':continue
 pt=Point(v['x']*.0254,v['y']*.0254);g=pt.buffer(v['diameter']*.0254/2,quad_segs=256).difference(pt.buffer(v['holeDiameter']*.0254/2,quad_segs=256));obs.append((v['primitiveId'],'VIA',g));seeds.append((v['primitiveId'],g))
for t in a['lines']:
 if t['net']!='GND' or t['layer']!=1:continue
 obs.append((t['primitiveId'],'LINE',LineString([(t['startX']*.0254,t['startY']*.0254),(t['endX']*.0254,t['endY']*.0254)]).buffer(t['lineWidth']*.0254/2,quad_segs=256)))
top=union_all([x[2] for x in obs]);parts=list(top.geoms) if hasattr(top,'geoms') else [top];cs=[]
for i,g in enumerate(parts):cs.append({'index':i,'area_mm2':g.area,'through_ground_seeds':[sid for sid,sg in seeds if g.intersection(sg).area>1e-8]})
allseeded=all(x['through_ground_seeds'] for x in cs);checks=[]
for oid,kind,g in obs:
 contact=[x['index'] for x,gg in zip(cs,parts) if g.intersection(gg).area>1e-8];checks.append({'id':oid,'kind':kind,'components':contact,'DC_to_through_Ground':bool(contact) and all(cs[i]['through_ground_seeds'] for i in contact)})
plane=[]
for layer in [2,15,16]:
 g=from_wkb((E/f'sensor-fourlayer-real-ground-layer{layer}-current.wkb').read_bytes());er=g.buffer(-.1651/2,quad_segs=256);ep=list(er.geoms) if hasattr(er,'geoms') else [er];contacts=[{'id':sid,'contact_mm2':g.intersection(sg).area} for sid,sg in seeds];plane.append({'layer':layer,'Ground_TH_contacts':contacts,'all_TH_positive_contacts':all(x['contact_mm2']>1e-8 for x in contacts),'minimum_width_erosion_mm':.1651,'eroded_components':len(ep),'eroded_areas_mm2':sorted([q.area for q in ep],reverse=True),'erosion_scope':'Geometry diagnostic, not full manufacturability/thermalbridge signoff; unchanged0.1651 width gate.'})
sourceold={x['primitiveId']:x for x in old['lines']};actual={x['primitiveId']:x for x in a['lines']};sourcechanged=[i for i,x in sourceold.items() if actual.get(i)!=x]
# SDK normalizes float precision after reopen; use native source payload comparison for exactpreservation separately.
r={'at':datetime.datetime.now().astimezone().isoformat(),'source_sha256':h,'native_file_unchanged':True,'actual_top_Ground_components':cs,'actual_all_top_Ground_components_have_through_seed':allseeded,'all_Top_Ground_PAD_via_line_DC_to_plane':all(x['DC_to_through_Ground'] for x in checks),'Top_Ground_checks':checks,'actual_planes':plane,'all_PTH_via_contacts_positive_on_all3planes':all(x['all_TH_positive_contacts'] for x in plane),'scope':'ActualTopGround sourceCu/PADs/vias union, explicitTHbarrel seeds to3actual singleGroundplanes. Signal reference/34deficits remain FAIL and whole minimumneck/factory signoff not claimed.','native_SDK_source_line_float_normalization_differences':sourcechanged,'accepted':False,'physical_tests':'UNMEASURED'}
(E/'sensor-fourlayer-Ground-DC-current.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in r.items() if k not in ['actual_top_Ground_components','Top_Ground_checks','actual_planes','native_SDK_source_line_float_normalization_differences']},ensure_ascii=True));print('erodedcomponents',[(x['layer'],x['eroded_components'],x['all_TH_positive_contacts']) for x in plane]);print('unseeded',[x for x in cs if not x['through_ground_seeds']])
