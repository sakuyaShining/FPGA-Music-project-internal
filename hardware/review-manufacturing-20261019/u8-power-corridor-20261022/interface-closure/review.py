"""Classify terminal routing; accept only complete nets with actual four-layer clearance."""
from pathlib import Path
import sys,json,copy,math,re,hashlib
O=Path(__file__).resolve().parent;B=O.parent;R=B.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path[:0]=[str(R),str(B)]
import ses
from four_layer_geometry import copper,connected
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
rd=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
wr=lambda p,x:p.write_text(json.dumps(x,indent=2),encoding='utf8')
a=rd(O/'attempt.json');assert a['state']=='terminal' and a['source_unchanged']
s=rd(O/'working-capture.json');out=ses.parse((O/'result.ses').read_text(),set(a['selected']))
out['vias']=[v for v in out['vias'] if not any(v['net']==p['net'] and math.dist((v['x'],v['y']),(p['x'],p['y']))*.0254<.0001 for p in s['vias'])]
for k in ['lines','vias']:
 for i,p in enumerate(out[k]):p['id']='interface-'+k+'-'+str(i)
w=copy.deepcopy(s)
for k in ['lines','vias']:w[k]+=out[k]
quiet=unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+(.6 if p['net'].startswith('I2S_') else .5),quad_segs=32) for p in s['lines'] if p['layer']==2 and (p['net'].startswith('I2S_') or re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net']))])
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]]);edge=box(0,0,140,100).boundary
reviews={};accepted=[]
for net in a['selected']:
 proof=connected(*[[p for p in w[k] if p['net']==net] for k in ['pads','lines','vias']]);fail=[];mins={}
 f,pads=copper(w,net);f={l:unary_union(q) for l,q in f.items()};fu=unary_union(list(f.values()));pu=unary_union(pads)
 def ck(kind,gap,limit,obj):
  mins[kind]=min(mins.get(kind,math.inf),gap)
  if gap<limit-1e-7:fail.append(dict(kind=kind,gap_mm=gap,limit_mm=limit,id=obj['id']))
 for p in [p for p in out['lines'] if p['net']==net]:
  q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]);r=p['width']*.0254/2
  ck('track_copper',q.distance(f[p['layer']])-r,.158,p);ck('track_edge',q.distance(edge)-r,.3,p);ck('track_mount',q.distance(mount)-r,.15,p)
  if p['layer'] in [16,2]:ck('track_quiet',q.distance(quiet)-r,.158,p)
 for p in [p for p in out['vias'] if p['net']==net]:
  q=Point(p['x']*.0254,p['y']*.0254);r=p['diameter']*.0254/2;h=p['hole']*.0254/2
  ck('via_copper',q.distance(fu)-r,.158,p);ck('hole_pad',q.distance(pu)-h,.25,p);ck('via_quiet',q.distance(quiet)-r,.158,p);ck('via_mount',q.distance(mount)-r,.15,p);ck('via_edge',q.distance(edge)-r,.3,p)
  for v in w['vias']:
   d=math.dist((p['x'],p['y']),(v['x'],v['y']))*.0254
   if d>1e-7:ck('drill_drill',d-(p['hole']+v['hole'])*.0254/2,.35,p)
 reviews[net]=dict(continuity=proof,failures=fail,minimum_clearances_mm=mins)
 if proof['complete'] and not fail:accepted.append(net)
plan={k:[p for p in out[k] if p['net'] in accepted] for k in ['lines','vias']};plan.update(source_pcb_sha256=a['source_pcb_sha256'],accepted_nets=accepted,remove_lines=[],remove_vias=[])
wr(O/'classification.json',dict(source_pcb_sha256=a['source_pcb_sha256'],reviews=reviews,accepted_nets=accepted,native_imported=False));wr(O/'reviewed-plan.json',plan)
wr(O/'routed-capture.json',w)
print(json.dumps(dict(accepted=accepted,results={n:dict(**v['continuity'],failure_count=len(v['failures'])) for n,v in reviews.items()}),indent=2))
