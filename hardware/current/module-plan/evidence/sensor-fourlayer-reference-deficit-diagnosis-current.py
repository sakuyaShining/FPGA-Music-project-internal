from pathlib import Path
import json,sys,datetime,hashlib,math
sys.path.insert(0,r'D:\FPGA-Project\codex-tools\shapely')
from shapely.geometry import Point,LineString,box
from shapely.affinity import rotate
from shapely import union_all,from_wkb
E=Path(__file__).parent
J=lambda f:json.loads((E/f).read_text(encoding='utf-8-sig'))
pads=J('sensor-fourlayer-exact-source-pads-current.json')['pads'];snap=J('sensor-fourlayer-reopened-DRC-current.json')['value'];g=J('sensor-fourlayer-actual-ground-reference-current.json');lines={x['primitiveId']:x for x in snap['lines']};planes={l:from_wkb((E/f'sensor-fourlayer-real-ground-layer{l}-current.wkb').read_bytes()) for l in [15,16]}
def shape(p):
 s=p['shape'];w=s['width']*.0254;h=s['height']*.0254
 return Point(p['x_mm'],p['y_mm']).buffer(w/2,quad_segs=256) if s['padType']=='ELLIPSE' and abs(w-h)<1e-6 else rotate(box(p['x_mm']-w/2,p['y_mm']-h/2,p['x_mm']+w/2,p['y_mm']+h/2),p['angle'],origin=(p['x_mm'],p['y_mm']))
# These larger regions are DIAGNOSTIC classifications from the unchanged physical
# zone-clearance0.254 rule, never substituted for existing acceptance exclusions.
term=[];drills=[]
for p in pads:
 if p['layer']==12 and p['net']!='GND':term.append({'id':p['ref']+'.'+p['pin'],'net':p['net'],'region':shape(p).buffer(.254,quad_segs=256),'kind':'TH_PAD_ANTIPAD'})
 if p['hole']:drills.append({'id':p['ref']+'.'+p['pin'],'g':Point(p['hole_x_mm'],p['hole_y_mm']).buffer(p['hole']['width']*.0254/2,quad_segs=256)})
for v in snap['vias']:
 p=Point(v['x']*.0254,v['y']*.0254)
 if v['net']!='GND':term.append({'id':v['primitiveId'],'net':v['net'],'region':p.buffer(v['diameter']*.0254/2+.254,quad_segs=256),'kind':'SIGNAL_VIA_ANTIPAD'})
 drills.append({'id':v['primitiveId'],'g':p.buffer(v['holeDiameter']*.0254/2,quad_segs=256)})
checks=[]
for fail in g['failed_reference_lines']:
 t=lines[fail['id']];cu=LineString([(t['startX']*.0254,t['startY']*.0254),(t['endX']*.0254,t['endY']*.0254)]).buffer(t['lineWidth']*.0254/2,quad_segs=256);miss=cu.difference(planes[fail['reference_layer']]);regions=[q['region'] for q in term if q['net']==t['net']];own=union_all(regions);rem=miss.difference(own);neighbor=[]
 for q in term:
  if q['net']==t['net']:continue
  a=rem.intersection(q['region']).area
  if a>1e-8:neighbor.append({'id':q['id'],'net':q['net'],'kind':q['kind'],'overlap_missing_mm2':a})
 hd=[{'id':q['id'],'overlap_mm2':rem.intersection(q['g']).area} for q in drills if rem.intersection(q['g']).area>1e-8];covered=union_all([q['region'] for q in term if q['net']!=t['net']]+[q['g'] for q in drills]);res=rem.difference(covered)
 checks.append({'id':fail['id'],'net':t['net'],'layer':t['layer'],'original_gate_failed_missing_mm2':fail['missing_outside_unchanged_terminal_mm2'],'own_actual_rule_antipad_overlap_mm2':miss.intersection(own).area,'missing_outside_own_actual_rule_antipads_mm2':rem.area,'neighbor_antipad_overlaps':neighbor,'drill_overlaps':hd,'unclassified_residual_mm2':res.area,'residual_bounds_mm':list(res.bounds) if not res.is_empty else [],'acceptance_pass':False})
r={'at':datetime.datetime.now().astimezone().isoformat(),'source_sha256':hashlib.sha256((E/'sensor-fourlayer-native-current.epcb2').read_bytes()).hexdigest(),'diagnostic_only':True,'original_gate_failed_segments':34,'own_antipad_only_segments':sum(x['missing_outside_own_actual_rule_antipads_mm2']<=1e-8 for x in checks),'neighbor_or_residual_segments':sum(x['missing_outside_own_actual_rule_antipads_mm2']>1e-8 for x in checks),'checks':checks,'acceptance_exclusions_unchanged':True,'native_not_modified':True,'accepted':False}
(E/'sensor-fourlayer-reference-deficit-diagnosis-current.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in r.items() if k!='checks'},ensure_ascii=True));print(json.dumps([x for x in checks if x['missing_outside_own_actual_rule_antipads_mm2']>1e-8],ensure_ascii=True))
