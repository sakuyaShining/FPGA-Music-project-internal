from pathlib import Path
import json,sys,datetime,hashlib
sys.path.insert(0,r'D:\FPGA-Project\codex-tools\shapely')
from shapely.geometry import Point,LineString,Polygon
from shapely import from_wkb,union_all
E=Path(__file__).parent;J=lambda f:json.loads((E/f).read_text(encoding='utf-8-sig'));pads=J('sensor-fourlayer-exact-source-pads-current.json')['pads'];a=J('sensor-fourlayer-signal-repair-reopened-DRC-current.json')['value'];g=J('sensor-fourlayer-actual-ground-reference-current.json');pured={x['layer']:x for x in g['planes']};terminals=[]
for p in pads:
 if p['layer']==12 and p['net']!='GND':terminals.append({'id':p['ref']+'.'+p['pin'],'net':p['net'],'xy':[p['hole_x_mm'],p['hole_y_mm']]})
for v in a['vias']:
 if v['net']!='GND':terminals.append({'id':v['primitiveId'],'net':v['net'],'xy':[v['x']*.0254,v['y']*.0254]})
planes={};voids={};maps={};shared=[]
for layer in [15,16]:
 plane=from_wkb((E/f'sensor-fourlayer-real-ground-layer{layer}-current.wkb').read_bytes());assert plane.geom_type=='Polygon';planes[layer]=plane;vs=[Polygon(x) for x in plane.interiors];voids[layer]=vs;maps[layer]={}
 for t in terminals:
  pt=Point(t['xy']);hits=[(i,q) for i,q in enumerate(vs) if q.covers(pt)];assert len(hits)==1,(layer,t['id'],len(hits));i,q=hits[0];maps[layer][t['id']]={'net':t['net'],'void_index':i,'g':q,'xy':t['xy']}
 for i in range(len(vs)):
  same=[k for k,v in maps[layer].items() if v['void_index']==i];nets={maps[layer][k]['net'] for k in same}
  if len(nets)>1:shared.append({'layer':layer,'void':i,'terminal_ids':same,'nets':sorted(nets)})
checks=[];pairchecks=[]
for layer,mm in maps.items():
 for tid,t in mm.items():
  near=min((v for v in a['vias'] if v['net']=='GND'),key=lambda v:Point(t['xy']).distance(Point(v['x']*.0254,v['y']*.0254)));dist=Point(t['xy']).distance(Point(near['x']*.0254,near['y']*.0254));contacts=[x for x in pured[layer]['Ground_via_contacts'] if x['id']==near['primitiveId']];assert len(contacts)==1;pairchecks.append({'layer':layer,'terminal':tid,'net':t['net'],'Ground_via':near['primitiveId'],'distance_mm':dist,'within1_5mm':dist<=1.5,'actual_poured_contact_mm2':contacts[0]['main_plane_contact_mm2'],'contact_ge0_15':contacts[0]['main_plane_contact_mm2']>=.15})
for t in a['lines']:
 if t['layer'] not in [1,2] or t['net']=='GND':continue
 L=15 if t['layer']==1 else 16;cu=LineString([(t['startX']*.0254,t['startY']*.0254),(t['endX']*.0254,t['endY']*.0254)]).buffer(t['lineWidth']*.0254/2,quad_segs=256);miss=cu.difference(planes[L]);own=union_all([v['g'] for v in maps[L].values() if v['net']==t['net']]);outside=miss.difference(own);checks.append({'id':t['primitiveId'],'net':t['net'],'layer':t['layer'],'actual_missing_mm2':miss.area,'outside_own_exact_native_antipad_void_mm2':outside.area,'diagnostic_only_all_missing_in_own_void':outside.area<=1e-8})
r={'at':datetime.datetime.now().astimezone().isoformat(),'source_sha256':hashlib.sha256((E/'sensor-fourlayer-native-current.epcb2').read_bytes()).hexdigest(),'purpose':'Concrete review of scope conflict ONLY, not authorization to expand old terminalexception. Ownnativeantipads are exactactual Groundpolygon interior boundaries uniquely containing only same-netTH/via terminal(s); no arbitrary enlarged radius, no fakeGroundfill.','old_acceptance_failed_segments':len(g['failed_reference_lines']),'all_actual_missing_is_in_own_native_antipad_void':all(x['diagnostic_only_all_missing_in_own_void'] for x in checks),'outside_own_native_void_failed_lines':[x for x in checks if not x['diagnostic_only_all_missing_in_own_void']],'shared_voids_different_nets':shared,'all_returnpairs_within1_5mm':all(x['within1_5mm'] for x in pairchecks),'all_returnpairs_purepoured_contact_ge0_15':all(x['contact_ge0_15'] for x in pairchecks),'return_pairs':pairchecks,'source_signal_and_supply_checks':checks,'old_gate_changed':False,'accepted':False,'requires_explicit_user_decision_if_changing_acceptance_scope':True,'physical_tests':'UNMEASURED'};(E/'sensor-fourlayer-exact-antipad-scope-review-current.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in r.items() if k not in ['return_pairs','source_signal_and_supply_checks']},ensure_ascii=True));print('maxpair',max(x['distance_mm'] for x in pairchecks))
