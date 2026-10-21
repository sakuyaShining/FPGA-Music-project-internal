"""Source-bound C35 relocation and short local bypass connection, offline only."""
import sys,json,hashlib,math,copy
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
assert not (BASE/'native-candidate-checkpoint.json').exists(), 'Accepted r7 stage is frozen; continue in a new source-bound stage instead of replaying it'
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT))
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
from physical_geometry import actual_pad
from four_layer_geometry import copper,connected
from resume_offline import read_native
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cp=json.loads((ROOT/'ACTIVE-ROUTING-CANDIDATE.json').read_text(encoding='utf-8'));assert 'Stackup-20261021-r5' in cp['project']
SRC=ROOT/cp['source_capture'];PCB=Path(cp['project'])/'pcb/PCB1.epcb2';assert sha(PCB)==cp['pcb_sha256']
s=json.loads(SRC.read_text(encoding='utf-8'));raw=read_native(PCB)
s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in raw.items() if k=='VIA']
REMOVE=['360090ebde71f414','8f73f9fcb655dfcd','2e1ff785117d1989','ee3577f6924b1697']
assert len([p for p in s['lines'] if p['id'] in REMOVE])==4
w={**s,'lines':[p for p in s['lines'] if p['id'] not in REMOVE],'pads':[p for p in s['pads'] if p['ref']!='C35']}
oldcap=[p for p in s['pads'] if p['ref']=='C35'];vcc=next(p for p in s['pads'] if p['ref']=='U15' and p['n']=='20')
assert len(oldcap)==2
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
def line(net,a,b,width):return dict(net=net,layer=1,x1=a[0]/.0254,y1=a[1]/.0254,x2=b[0]/.0254,y2=b[1]/.0254,width=width/.0254)
def validate(data,newpads,ls,vs):
 minimum=99.
 for net in ['3V3_PERIPH','GND']:
  f,ps=copper(data,net);cu={l:unary_union(f[l]) for l in f};both=unary_union([q for gs in f.values() for q in gs]);allpads=unary_union(ps)
  for p in newpads:
   if p['net']==net:
    gap=actual_pad(p).distance(cu[1]);minimum=min(minimum,gap);assert gap>=.2,('pad',p['n'],gap)
  for p in ls:
   if p['net']!=net:continue
   q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]);gap=q.distance(cu[1])-p['width']*.0254/2;minimum=min(minimum,gap);assert gap>=.165,('line',net,gap)
  for p in vs:
   if p['net']!=net:continue
   q=Point(p['x']*.0254,p['y']*.0254);gap=q.distance(both)-p['diameter']*.0254/2;minimum=min(minimum,gap);assert gap>=.165,('via',gap)
   assert q.distance(allpads)-p['hole']*.0254/2>=.25
   assert q.distance(mount)>=p['diameter']*.0254/2+.15
   for v in data['vias']:
    if p is v:continue
    assert q.distance(Point(v['x']*.0254,v['y']*.0254))-(p['hole']+v['hole'])*.0254/2>=.35
 return minimum
results=[];failures=[]
# A conservative placement envelope excludes every other component's pad bounds,
# not only its actual copper. Native component/body and DRC review still required.
otherrefs={p['ref'] for p in w['pads']};envelopes=[]
for ref in otherrefs:
 ps=[actual_pad(p) for p in w['pads'] if p['ref']==ref];q=unary_union(ps);envelopes.append((ref,box(*q.bounds)))
for x in [78.45,78.2,77.95,77.7]:
 if results:break
 for y in [45.9,46.3,45.5,46.7]:
  if results:break
  for flip in [False,True]:
   if results:break
   # Rotation90->0: pin1 at right, pin2 at left; polarity can be reversed.
   newpads=[{**p,'x':(x+(.7 if p['n']=='1' else -.7)*(-1 if flip else 1))/.0254,'y':y/.0254,'rotation':0} for p in oldcap]
   capenvelope=box(x-1.15,y-.6,x+1.15,y+.6)
   if any(capenvelope.distance(q)<.15 for ref,q in envelopes):continue
   power=next(p for p in newpads if p['net']=='3V3_PERIPH');gnd=next(p for p in newpads if p['net']=='GND')
   pp=(power['x']*.0254,power['y']*.0254);gp=(gnd['x']*.0254,gnd['y']*.0254);vp=(vcc['x']*.0254,vcc['y']*.0254)
   if math.dist(pp,vp)>2.5:continue
   for dx,dy in [(-.9,0),(0,-.9),(0,.9),(-.7,-.7),(-.7,.7),(.9,0),(.7,-.7),(.7,.7)]:
    if results:break
    v=dict(net='GND',x=(gp[0]+dx)/.0254,y=(gp[1]+dy)/.0254,diameter=24,hole=12)
    ls=[line('3V3_PERIPH',pp,vp,.33528),line('GND',gp,(gp[0]+dx,gp[1]+dy),.254)]
    work={**w,'pads':w['pads']+newpads,'lines':w['lines']+ls,'vias':w['vias']+[v]}
    try:
     gap=validate(work,newpads,ls,[v])
     assert connected([p for p in work['pads'] if p['net']=='3V3_PERIPH'],[p for p in work['lines'] if p['net']=='3V3_PERIPH'],[p for p in work['vias'] if p['net']=='3V3_PERIPH'])['complete']
     print('ACCEPTED PLACEMENT',x,y,flip,dx,dy,gap,flush=True);results.append(dict(component='C35',component_x_mm=x,component_y_mm=y,component_rotation=180 if flip else 0,pads=newpads,lines=ls,vias=[v],min_gap_mm=gap,vcc_centerline_mm=math.dist(pp,vp),ground_stub_mm=math.hypot(dx,dy),working=work))
    except AssertionError as e:failures.append(str(e))
assert results,('No acceptable local placement',failures[:10])
best=min(results,key=lambda r:r['vcc_centerline_mm']+r['ground_stub_mm']);work=best.pop('working')
oldlen=sum(math.dist((p['x1'],p['y1']),(p['x2'],p['y2']))*.0254 for p in s['lines'] if p['id'] in REMOVE and p['net']=='3V3_PERIPH')
plan=dict(source_project=cp['project'],source_pcb_sha256=cp['pcb_sha256'],source_capture=str(SRC),source_capture_sha256=sha(SRC),remove_line_ids=REMOVE,remove_via_ids=[],before_power_stub_mm=oldlen,accepted_candidates=len(results),selection_strategy='first geometrically acceptable placement in proximity-ordered bounded list; not global optimum',**best,native_imported=False,manufacturing_release=False)
(BASE/'decoupling-plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8');(BASE/'decoupling-working.json').write_text(json.dumps(work),encoding='utf-8');assert sha(PCB)==cp['pcb_sha256']
print(json.dumps({k:v for k,v in plan.items() if k not in ['pads','lines','vias']},indent=2),flush=True)
