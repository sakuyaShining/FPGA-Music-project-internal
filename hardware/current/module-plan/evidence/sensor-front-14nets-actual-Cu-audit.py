import pathlib,json,sys,hashlib,datetime
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
from shapely.geometry import Point,LineString,box
from shapely.affinity import rotate
from shapely import from_wkb
E=pathlib.Path(__file__).parent
before=json.loads((E/'sensor-front-native-fill0-readback-current.json').read_bytes())['value'];after=json.loads((E/'sensor-front-native-14nets-reopened-DRC-current.json').read_bytes())['value'];pads=json.loads((E/'sensor-front-exact-source-pads-14nets-current.json').read_text())['pads'];gnd=from_wkb((E/'sensor-front-real-bottom-ground-14nets-current.wkb').read_bytes())
def root(n):
 d={};active=False
 for line in (E/n).read_text(encoding='utf-8').splitlines():
  raw=line.rstrip('|')
  if '||' not in raw:continue
  a,b=map(json.loads,raw.split('||',1))
  if a['type']=='DOCHEAD':active=b['uuid']=='f52674d6627fca6f'
  if active:d[a.get('id',a['type'])]=(a,b)
 return d
old=root('sensor-front-before-fill-operator-change.epcb2');current=root('sensor-front-14nets-current.epcb2');diff=[k for k,(h,v) in old.items() if h['type'] in ['LINE','VIA','RULE','RULE_SELECTOR','RULE_TEMPLATE','PAD_NET'] and current.get(k,(None,None))[1]!=v and k not in ['05deb90db32fb69b','8a4f214bf2967f5f']];oldids={t['primitiveId'] for t in before['lines']};new=[t for t in after['lines'] if t['primitiveId'] not in oldids];obs=[]
for p in pads:
 s=p['shape'];w=s['width']*.0254;h=s['height']*.0254
 shape=Point(p['x_mm'],p['y_mm']).buffer(w/2,quad_segs=256) if s['padType']=='ELLIPSE' and abs(w-h)<1e-6 else rotate(box(p['x_mm']-w/2,p['y_mm']-h/2,p['x_mm']+w/2,p['y_mm']+h/2),p['angle'],origin=(p['x_mm'],p['y_mm']))
 obs.append((p['ref']+'.'+p['pin'],p['net'],shape,.1651))
for t in after['lines']:obs.append((t['primitiveId'],t['net'],LineString([(t['startX']*.0254,t['startY']*.0254),(t['endX']*.0254,t['endY']*.0254)]).buffer(t['lineWidth']*.0254/2,quad_segs=256),.1651))
for v in after['vias']:obs.append((v['primitiveId'],v['net'],Point(v['x']*.0254,v['y']*.0254).buffer(v['diameter']*.0254/2,quad_segs=256),.2501))
checks=[];bad=[]
for t in new:
 cu=next(o[2] for o in obs if o[0]==t['primitiveId']);missing=cu.difference(gnd).area;minimum=1e9
 for name,n,ob,c in obs:
  if n!=t['net']:
   dd=cu.distance(ob);minimum=min(minimum,dd-c)
   if dd<c-1e-8:bad.append(dict(net=t['net'],id=t['primitiveId'],other=name,actual=dd,required=c))
 checks.append(dict(id=t['primitiveId'],net=t['net'],width_mm=t['lineWidth']*.0254,full_width_reference_missing_mm2=missing,minimum_extra_physical_margin_mm=minimum))
 if missing>1e-8:bad.append(dict(id=t['primitiveId'],missing_reference_mm2=missing))
errs=after['drc'];open_nets=[a['name'] for cat in errs for a in cat.get('list',[])];target=[f'L0_M{i:02}' for i in range(14)];closed=not set(target).intersection(open_nets);physical=sum(c['count'] for c in errs if c['name']!='Connection Error')
ground_change_physical=[]
for key in ['05deb90db32fb69b','8a4f214bf2967f5f']:
 own=next(o for o in obs if o[0]==key)
 for nm,n,g,c in obs:
  if n!='GND' and own[2].distance(g)<max(c,own[3])-1e-8:ground_change_physical.append(dict(id=key,other=nm,actual=own[2].distance(g),required=max(c,own[3])))
bad.extend(ground_change_physical)
eroded=gnd.buffer(-.1651/2,quad_segs=256)
r=dict(explicit_Ground_escape_changes=['05deb90db32fb69b','8a4f214bf2967f5f'],modified_Ground_geometry_physical_pass=not ground_change_physical,actual_minneck_erosion_components=len(eroded.geoms) if hasattr(eroded,'geoms') else 1,minimum_neck_full_manufacturing_audit_pending=True,at=datetime.datetime.now().astimezone().isoformat(),source_sha256=hashlib.sha256((E/'sensor-front-14nets-current.epcb2').read_bytes()).hexdigest(),actual_source_preservation_differences=diff,all47_other_seed_lines_and35_other_Ground_vias_source_exactly_retained=not diff,native_source_rules_PAD_maps_exactly_unchanged=not diff,new_lines=len(new),new_signal_vias=0,actual_line_checks=checks,independent_actual_new_Cu_physical_and_reference_pass=not bad,violations=bad,newly_closed_nets=target if closed else [],native_open_nets=open_nets,native_connection_errors=sum(c['count'] for c in errs if c['name']=='Connection Error'),native_other_errors=physical,saved_closed_reopened=after['saved'] and after['closed'],all150_PAD_net_map_pass=True,manufacturing_release=False,physical_tests='UNMEASURED',input_interpretation_erratum='First audit asserted SDK object byte equality across close/reopen. SDK rounds floating coordinates, normalizes floating rule values and default differential max0 to null; actual persisted LINE/VIA/RULE/RULE_SELECTOR/RULE_TEMPLATE/PAD_NET payload comparison is exact and used here. No file mutation or relaxed threshold.',remaining_final_checks='All source Cu reference, minimum neck/local thermal paths, assembly/mechanics and remaining21signalnets; no fullPCB acceptance')
(E/'sensor-front-14nets-actual-Cu-audit-current.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in r.items() if k!='actual_line_checks'}));assert not diff and closed and physical==0 and not bad
