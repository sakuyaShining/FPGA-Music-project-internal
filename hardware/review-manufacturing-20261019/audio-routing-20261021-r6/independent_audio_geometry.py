"""Independent continuous check against complete native four-layer copper."""
import sys,json,hashlib,math,re
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT))
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
from resume_offline import read_native
from four_layer_geometry import copper,connected
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cp=json.loads((ROOT/'ACTIVE-ROUTING-CANDIDATE.json').read_text(encoding='utf-8'))
PLAN=BASE/'fixed-fanout-four-via-bundle-1/plan.json';plan=json.loads(PLAN.read_text(encoding='utf-8'))
assert len(plan['routes'])==3 and plan['batch_final_geometry_pass'] and plan['bundle_length_pass']
PCB=Path(cp['project'])/'pcb/PCB1.epcb2';assert sha(PCB)==plan['native_pcb_sha256']==cp['pcb_sha256']
SRC=ROOT/cp['source_capture'];s=json.loads(SRC.read_text(encoding='utf-8'));assert sha(SRC)==plan['source_sha256']
native=read_native(PCB)
s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in native.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in native.items() if k=='VIA']
nets={rt['net'] for rt in plan['routes']}
w={**s,'lines':[p for p in s['lines'] if p['net'] not in nets]+[p for rt in plan['routes'] for p in rt['lines']],'vias':[p for p in s['vias'] if p['net'] not in nets]+[p for rt in plan['routes'] for p in rt['vias']]}
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
quiet=unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+.5,resolution=32) for p in s['lines'] if p['layer']==2 and (re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net']))])
# A projected crossing must not create connectivity between separate copper layers.
pads=[dict(id='a',net='T',layer=1,x=0,y=0,rotation=0,shape=['ELLIPSE',10,10]),dict(id='b',net='T',layer=1,x=100,y=0,rotation=0,shape=['ELLIPSE',10,10])]
line=dict(net='T',layer=16,x1=0,y1=0,x2=100,y2=0,width=6)
assert not connected(pads,[line],[])['complete']
assert connected(pads,[line],[dict(net='T',x=x,y=0,diameter=24,hole=12) for x in [0,100]])['complete']
results=[]
for rt in plan['routes']:
 net=rt['net'];f,ps=copper(w,net);cu={l:unary_union(f[l]) for l in f};both=unary_union([q for v in f.values() for q in v]);padcu=unary_union(ps);minimum=99.;newminimum=99.
 assert connected([p for p in s['pads'] if p['net']==net],rt['lines'],rt['vias'])['complete']
 for p in rt['lines']:
  q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]);gap=q.distance(cu[p['layer']])-p['width']*.0254/2;minimum=min(minimum,gap)
  assert gap>=(.15239 if p.get('id') else .158),(net,'track',gap)
  if not p.get('id'):newminimum=min(newminimum,gap)
  assert q.distance(mount)>=p['width']*.0254/2+.15
  if p['layer']==16:assert q.distance(quiet)>=p['width']*.0254/2+.158
 for p in rt['vias']:
  q=Point(p['x']*.0254,p['y']*.0254);gap=q.distance(both)-p['diameter']*.0254/2;minimum=min(minimum,gap);assert gap>=.158,(net,'via',gap)
  if not p.get('id'):newminimum=min(newminimum,gap)
  assert q.distance(padcu)-p['hole']*.0254/2>=.25
  assert q.distance(mount)>=p['diameter']*.0254/2+.15
  for v in w['vias']:
   if p is v:continue
   assert q.distance(Point(v['x']*.0254,v['y']*.0254))-(p['hole']+v['hole'])*.0254/2>=.3499,(net,'drill')
 results.append(dict(net=net,min_copper_gap_mm=minimum,min_new_copper_gap_mm=newminimum,actual_four_layer_connected=True,**rt['quality']))
assert all(sha(Path(cp['project'])/rel)==h for rel,h in cp['files'].items())
v=dict(source_pcb_sha256=cp['pcb_sha256'],plan_file=str(PLAN),plan_sha256=sha(PLAN),combined_geometry_pass=True,layer_crossing_negative_control_pass=True,through_via_positive_control_pass=True,results=results,source_19_unchanged=True,manufacturing_release=False,native_reference_check_required=True)
(BASE/'independent-geometry.json').write_text(json.dumps(v,indent=2),encoding='utf-8');print(json.dumps(v,indent=2))
