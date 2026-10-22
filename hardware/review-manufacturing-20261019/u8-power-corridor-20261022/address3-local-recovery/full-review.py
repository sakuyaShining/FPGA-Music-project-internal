"""Aggregate source650 changes and independently check all real copper layers."""
from pathlib import Path
import sys,json,math,re,hashlib,copy
O=Path(__file__).resolve().parent;B=O.parent;R=B.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path[:0]=[str(R),str(B)]
from four_layer_geometry import copper,connected
from native_plane_geometry import poured_planes
from resume_offline import read_native
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
rd=lambda p:json.loads(p.read_text(encoding='utf8'))
wr=lambda p,x:p.write_text(json.dumps(x,indent=2),encoding='utf8')
D=O/'reachable-exits/plane-aware-backbone/analog-critical-first/raw2-recovery'
s=rd(B/'inv2-coupled/checkpoint-capture.json');w=rd(D/'routed-capture.json');cp=rd(R/'REGIONAL-WORK-IN-PROGRESS.json');pcb=Path(cp['project'])/'pcb/PCB1.epcb2'
assert hashlib.sha256(pcb.read_bytes()).hexdigest()=='6509803e7afca781b7f71ad69183cc10d8f6413312701eb16a2cdc46dfe83afd'
assert all(x['complete'] for x in rd(D/'classification.json')['continuity'].values())
plan=dict(source_pcb_sha256=cp['pcb_sha256'],components_unchanged=True,accepted_nets=['ADDR3'],required_closed=['ADDR3','L2_M02','L2_M03','L2_M04','L2_M14'])
for k in ['lines','vias']:
 original={p['id']:p for p in s[k]};final={p['id']:p for p in w[k]}
 for i in original.keys()&final.keys():
  for key,value in original[i].items():assert final[i][key]==value,(i,key)
 plan[k]=[p for p in w[k] if p['id'] not in original];plan['remove_'+k]=[p for p in s[k] if p['id'] not in final]
assert all(p['net'] in ['L2_M02','L2_M03'] for p in plan['remove_lines']+plan['remove_vias'])
assert all(p['net'] in ['ADDR3','L2_M02','L2_M03'] for p in plan['lines']+plan['vias'])
quiet=unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+(.6 if p['net'].startswith('I2S_') else .5),quad_segs=32) for p in w['lines'] if p['layer']==2 and (p['net'].startswith('I2S_') or re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net']))])
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]]);edge=box(0,0,140,100).boundary
checks={};fail=[]
for net in {p['net'] for p in plan['lines']+plan['vias']}:
 f,pads=copper(w,net);f={l:unary_union(q) for l,q in f.items()};fu=unary_union(list(f.values()));pu=unary_union(pads)
 def ck(kind,gap,limit,p):
  checks[kind]=min(checks.get(kind,math.inf),gap)
  if gap<limit-1e-7:fail.append(dict(net=net,id=p['id'],kind=kind,gap_mm=gap,minimum_mm=limit))
 for p in [p for p in plan['lines'] if p['net']==net]:
  assert p['layer'] in ([1,16] if net=='ADDR3' else [1,2]);assert p['width']>= (6 if net=='ADDR3' else 8)-1e-7
  q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]);rad=p['width']*.0254/2
  ck('track_copper',q.distance(f[p['layer']])-rad,.158,p);ck('track_mount',q.distance(mount)-rad,.15,p);ck('track_edge',q.distance(edge)-rad,.3,p)
  if net=='ADDR3' and p['layer']==16:ck('digital_track_quiet',q.distance(quiet)-rad,.158,p)
 for p in [p for p in plan['vias'] if p['net']==net]:
  q=Point(p['x']*.0254,p['y']*.0254);rad=p['diameter']*.0254/2
  ck('via_copper',q.distance(fu)-rad,.158,p);ck('hole_pad',q.distance(pu)-p['hole']*.0254/2,.25,p);ck('via_edge',q.distance(edge)-rad,.3,p);ck('via_mount',q.distance(mount)-rad,.15,p)
  if net=='ADDR3':ck('digital_via_quiet',q.distance(quiet)-rad,.158,p)
  for v in w['vias']:
   if v['id']==p['id']:continue
   ck('drill_drill',math.dist((p['x'],p['y']),(v['x'],v['y']))*.0254-(p['hole']+v['hole'])*.0254/2,.35,p)
proof={n:connected(*[[p for p in w[k] if p['net']==n] for k in ['pads','lines','vias']]) for n in plan['required_closed']}
assert all(p['complete'] for p in proof.values())
planes=poured_planes(read_native(pcb));projections=[]
for net in ['ADDR3','L2_M02','L2_M03']:
 ex=unary_union([Point(p['x']*.0254,p['y']*.0254).buffer(1) for p in w['vias'] if p['net']==net])
 for layer,ref in [(1,15),(16,2),(2,16)]:
  qs=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).difference(ex) for p in plan['lines'] if p['net']==net and p['layer']==layer]
  if not qs:continue
  length=sum(q.length for q in qs);covered=sum(q.intersection(planes[ref]).length for q in qs);projections.append(dict(net=net,layer=layer,reference=ref,length_mm=length,covered_mm=covered,gap_mm=length-covered))
refs=[]
for p in w['vias']:
 if p['net']!='GND':continue
 q=Point(p['x']*.0254,p['y']*.0254);ring=q.buffer(p['diameter']*.0254/2,quad_segs=64).difference(q.buffer(p['hole']*.0254/2,quad_segs=64));areas={str(l):ring.intersection(planes[l]).area for l in [15,2]}
 if min(areas.values())>=.15:refs.append(dict(p,contact_mm2=areas))
returns=[]
for p in plan['vias']:
 if p['net']!='ADDR3':continue
 r=min(refs,key=lambda r:math.dist((p['x'],p['y']),(r['x'],r['y'])));distance=math.dist((p['x'],p['y']),(r['x'],r['y']))*.0254;returns.append(dict(signal_xy_mm=[p['x']*.0254,p['y']*.0254],nearest_ground_xy_mm=[r['x']*.0254,r['y']*.0254],distance_mm=distance,within_project_preference_1p5mm=distance<=1.5))
audit=dict(source_pcb_sha256=plan['source_pcb_sha256'],geometric_pass=not fail,minimum_clearances_mm=checks,failures=fail,continuity=proof,predicted_reference_projection=projections,predicted_returns=returns,reference_not_si_signoff=True,native_imported=False,manufacturing_release=False)
wr(O/'full-preflight.json',audit);wr(O/'aggregate-plan.json',plan);wr(O/'complete-capture.json',w)
print(json.dumps(audit,indent=2),flush=True)
