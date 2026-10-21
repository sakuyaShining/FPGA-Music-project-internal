"""Source-bound physical review of the coupled INV2/power/VIS_DC repair."""
from pathlib import Path
import sys,json,math,re,hashlib,copy
O=Path(__file__).resolve().parent;B=O.parent;R=B.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(R))
from four_layer_geometry import copper,connected
from native_plane_geometry import poured_planes
from resume_offline import read_native
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
rd=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p=rd(O/'complete-plan.json');w=rd(O/'complete-capture.json');cp=rd(R/'REGIONAL-WORK-IN-PROGRESS.json');pcb=Path(cp['project'])/'pcb/PCB1.epcb2'
assert sha(pcb)==p['source_pcb_sha256'];planes=poured_planes(read_native(pcb))
quiet=unary_union([LineString([(z['x1']*.0254,z['y1']*.0254),(z['x2']*.0254,z['y2']*.0254)]).buffer(z['width']*.0254/2+(.6 if z['net'].startswith('I2S_') else .5),quad_segs=32) for z in w['lines'] if z['layer']==2 and (z['net'].startswith('I2S_') or re.fullmatch(r'RC[0-5]',z['net']) or re.match(r'L[0-5]_',z['net']))])
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]]);edge=box(0,0,140,100).boundary
refs=[]
for v in w['vias']:
 if v['net']!='GND':continue
 q=Point(v['x']*.0254,v['y']*.0254);ring=q.buffer(v['diameter']*.0254/2,quad_segs=64).difference(q.buffer(v['hole']*.0254/2,quad_segs=64))
 areas={str(l):ring.intersection(planes[l]).area for l in [15,2]}
 if min(areas.values())>=.15:refs.append({**v,'reference_contact_mm2':areas})
assert refs
# 1.5mm is a preferred placement target, never a substitute for a real
# reference plane or an SI result. Retain all source GND; don't force unsafe
# stitches into the sensing keepout. Search a bounded larger region if needed.
chosen=[]
for sig in p['vias']:
 if sig['net'] not in ['INV2','VIS_DC']:continue
 nearest=min(refs,key=lambda v:math.dist((sig['x'],sig['y']),(v['x'],v['y'])))
 existing_distance=math.dist((sig['x'],sig['y']),(nearest['x'],nearest['y']))*.0254
 if existing_distance<=1.5:continue
 f,ps=copper(w,'GND');fu=unary_union([q for gs in f.values() for q in gs]);pu=unary_union(ps);candidates=[]
 for radius in [.9+i*.1 for i in range(22)]:
  if radius>=existing_distance-.05:break  # Never add a worse or redundant return via.
  for j in range(64):
   theta=j*math.pi/32;x=sig['x']*.0254+radius*math.cos(theta);y=sig['y']*.0254+radius*math.sin(theta);q=Point(x,y)
   if q.distance(fu)-.3048<.165 or q.distance(pu)-.1524<.25 or q.distance(quiet)-.3048<.158 or q.distance(mount)-.3048<.15 or q.distance(edge)-.3048<.3:continue
   if any(q.distance(Point(v['x']*.0254,v['y']*.0254))-(12+v['hole'])*.0254/2<.35 for v in w['vias']):continue
   ring=q.buffer(.3048,quad_segs=64).difference(q.buffer(.1524,quad_segs=64));areas={str(l):ring.intersection(planes[l]).area for l in [15,2]}
   if min(areas.values())<.15:continue
   candidates.append(dict(net='GND',x=x/.0254,y=y/.0254,diameter=24,hole=12,xy_mm=[x,y],predicted_contact_mm2=areas,distance_to_signal_mm=radius))
  if candidates:break
 if candidates:
  ground=max(candidates,key=lambda v:min(v['predicted_contact_mm2'].values()));p['vias'].append(ground);w['vias'].append(ground);refs.append(ground);chosen.append(ground)
checks={};fail=[]
for net in {z['net'] for z in p['lines']+p['vias']}:
 f,ps=copper(w,net);f={l:unary_union(gs) for l,gs in f.items()};fu=unary_union(list(f.values()));pu=unary_union(ps)
 def ck(kind,gap,minimum):
  checks[kind]=min(checks.get(kind,math.inf),gap)
  if gap<minimum-1e-7:fail.append(dict(net=net,kind=kind,gap_mm=gap,minimum_mm=minimum))
 for z in [z for z in p['lines'] if z['net']==net and z!=p['preserved_line']]:
  q=LineString([(z['x1']*.0254,z['y1']*.0254),(z['x2']*.0254,z['y2']*.0254)]);rad=z['width']*.0254/2;ck('track_copper',q.distance(f[z['layer']])-rad,.158);ck('track_edge',q.distance(edge)-rad,.3);ck('track_mount',q.distance(mount)-rad,.15)
  if z['layer'] in [16,2]:ck('track_quiet',q.distance(quiet)-rad,.158)
 for z in [z for z in p['vias'] if z['net']==net]:
  q=Point(z['x']*.0254,z['y']*.0254);ck('via_copper',q.distance(fu)-.3048,.158);ck('hole_pad',q.distance(pu)-.1524,.25);ck('via_quiet',q.distance(quiet)-.3048,.158);ck('via_mount',q.distance(mount)-.3048,.15);ck('via_edge',q.distance(edge)-.3048,.3)
  for v in w['vias']:
   d=math.dist((z['x'],z['y']),(v['x'],v['y']))*.0254
   if d>1e-7:ck('drill_drill',d-(z['hole']+v['hole'])*.0254/2,.35)
proofs={net:connected([z for z in w['pads'] if z['net']==net],[z for z in w['lines'] if z['net']==net],[z for z in w['vias'] if z['net']==net]) for net in ['INV2','3V3_PERIPH','VIS_DC']}
assert proofs['INV2']['complete'] and proofs['3V3_PERIPH']['complete'] and proofs['VIS_DC']['pad_islands']==2
returns=[]
for v in [v for v in p['vias'] if v['net']!='GND']:
 nearest=min(refs,key=lambda z:math.dist((v['x'],v['y']),(z['x'],z['y'])));d=math.dist((v['x'],v['y']),(nearest['x'],nearest['y']))*.0254
 returns.append(dict(signal_net=v['net'],xy_mm=[v['x']*.0254,v['y']*.0254],qualified_reference_xy_mm=[nearest['x']*.0254,nearest['y']*.0254],distance_mm=d,within_project_1p5mm_goal=d<=1.5))
excluded=unary_union([Point(v['x']*.0254,v['y']*.0254).buffer(1) for v in p['vias'] if v['net']=='INV2']);projection=[]
for z in [z for z in p['lines'] if z['net']=='INV2']:
 ref=15 if z['layer']==1 else 2;q=LineString([(z['x1']*.0254,z['y1']*.0254),(z['x2']*.0254,z['y2']*.0254)]).difference(excluded)
 projection.append(dict(layer=z['layer'],reference=ref,length_mm=q.length,covered_mm=q.intersection(planes[ref]).length))
a=dict(source_pcb_sha256=p['source_pcb_sha256'],geometric_pass=not fail,minimum_clearances_mm=checks,failures=fail,continuity=proofs,new_ground_stitches=chosen,predicted_reference_returns=returns,reference_distance_is_preference_not_si_signoff=True,predicted_inv2_reference_projection=projection,components_unchanged=True,source_sensor_audio_copper_unchanged=True,native_imported=False,manufacturing_release=False)
for name,obj in [('full-preflight.json',a),('validated-copper-plan.json',p),('validated-capture.json',w)]:
 (O/name).write_text(json.dumps(obj,indent=2),encoding='utf8')
assert sha(pcb)==p['source_pcb_sha256']
print(json.dumps(a,indent=2),flush=True)
