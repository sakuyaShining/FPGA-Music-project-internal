"""Move local via shadows without rerouting a closed address tree."""
from pathlib import Path
import sys,json,copy,math,re,hashlib
D=Path(__file__).resolve().parent;O=D.parent;B=O.parent;R=B.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path[:0]=[str(R),str(B)]
from four_layer_geometry import copper,connected
from native_plane_geometry import poured_planes
from resume_offline import read_native
from physical_geometry import actual_pad
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
rd=lambda p:json.loads(p.read_text(encoding='utf8'))
wr=lambda p,x:p.write_text(json.dumps(x,indent=2),encoding='utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert not (D/'patch.json').exists(),'Inspect the existing patch, never overwrite it'
state=rd(O/'native-state.json');info=rd(O/'native-candidate-source.json');pcb=Path(info['candidate_project'])/'pcb/PCB1.epcb2'
assert sha(pcb)==state['pcb_sha256']=='68081b43760c6bac3f8e7e517991fbb097f32fd9697c371ddd0bf064224da0e1'
s=rd(O/'native-stage-capture.json');w=copy.deepcopy(s);audit=rd(O/'native-stage-review.json');plan=rd(O/'grounded-plan.json');created=rd(O/'native-apply.json')
newids=set(created['createdV']);oldplanes=poured_planes(read_native(Path(info['source_project'])/'pcb/PCB1.epcb2'));planes=poured_planes(read_native(pcb))
protected=lambda n:bool(n.startswith('I2S_') or re.fullmatch(r'RC[0-5]',n) or re.match(r'L[0-5]_',n))
top={};losses=[]
for net in {p['net'] for p in s['lines'] if p['layer']==1 and protected(p['net'])}:
 mask=unary_union([Point(v['x']*.0254,v['y']*.0254).buffer(1,quad_segs=64) for v in s['vias'] if v['net']==net]+[actual_pad(p).buffer(.5) for p in s['pads'] if p['net']==net and p['layer']==12])
 qs=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).difference(mask) for p in s['lines'] if p['net']==net and p['layer']==1]
 top[net]=unary_union(qs).intersection(oldplanes[15])
 if any(p['net']==net and p['layer']==1 for p in audit['reference_degradation']):
  lost=top[net].difference(planes[15])
  for z in list(lost.geoms) if hasattr(lost,'geoms') else [lost]:
   if z.length>1e-5:losses.append((net,z))
targets={};unlocalized=[]
for net,loss in losses:
 q=loss.interpolate(.5,normalized=True);vs=sorted((q.distance(Point(v['x']*.0254,v['y']*.0254)),v['id']) for v in s['vias'] if v['id'] in newids and v['net']!=net)
 if vs and vs[0][0]<=.85:targets.setdefault(vs[0][1],[]).append(net)
 else:unlocalized.append(dict(net=net,gap_wkt=loss.wkt,nearest_new_via_distance_mm=vs[0][0] if vs else None))
quiet=unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+(.6 if p['net'].startswith('I2S_') else .5),quad_segs=32) for p in w['lines'] if p['layer']==2 and protected(p['net'])])
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]]);edge=box(0,0,140,100).boundary
patch=dict(source_pcb_sha256=sha(pcb),modify_vias=[],modify_lines=[],unlocalized_losses=unlocalized,unresolved=[],native_imported=False)
for vid,nets in targets.items():
 v=next(p for p in w['vias'] if p['id']==vid);net=v['net'];f,pads=copper(w,net);f={l:unary_union(gs) for l,gs in f.items()};fu=unary_union(list(f.values()));pu=unary_union(pads);t=unary_union([q for n,q in top.items() if n!=net]);incident=[]
 for p in w['lines']:
  if p['net']!=net:continue
  ends=[j for j in [1,2] if math.dist((p['x'+str(j)],p['y'+str(j)]),(v['x'],v['y']))*.0254<1e-5]
  if ends:incident.append((p,ends))
 selected=None
 for radius in [.2,.35,.5,.75,1,1.25]:
  options=[]
  for j in range(64):
   angle=j*math.pi/32;q=Point(v['x']*.0254+radius*math.cos(angle),v['y']*.0254+radius*math.sin(angle))
   if q.distance(t)<.85 or q.distance(fu)-v['diameter']*.0254/2<.165 or q.distance(pu)-v['hole']*.0254/2<.25 or q.distance(mount)-.3048<.15 or q.distance(edge)-.3048<.3:continue
   if any(p['id']!=vid and q.distance(Point(p['x']*.0254,p['y']*.0254))-(p['hole']+v['hole'])*.0254/2<.35 for p in w['vias']):continue
   if net in ['ADDR3','GND'] and q.distance(quiet)-.3048<.158:continue
   if net=='GND':
    ring=q.buffer(.3048,quad_segs=64).difference(q.buffer(.1524,quad_segs=64))
    if min(ring.intersection(planes[l]).area for l in [15,2])<.15:continue
   changed=[];valid=True
   for line,ends in incident:
    z=dict(line)
    for end in ends:z['x'+str(end)]=q.x/.0254;z['y'+str(end)]=q.y/.0254
    g=LineString([(z['x1']*.0254,z['y1']*.0254),(z['x2']*.0254,z['y2']*.0254)]);r=z['width']*.0254/2
    if g.distance(f[z['layer']])-r<.158 or g.distance(mount)-r<.15 or g.distance(edge)-r<.3:valid=False;break
    if net=='ADDR3' and z['layer']==16 and g.distance(quiet)-r<.158:valid=False;break
    changed.append(z)
   if valid:options.append((q.distance(t),q,changed))
  if options:selected=max(options,key=lambda x:x[0]);break
 if not selected:patch['unresolved'].append(dict(id=vid,net=net,xy_mm=[v['x']*.0254,v['y']*.0254],affected_nets=nets));continue
 _,q,changed=selected;after=dict(v,x=q.x/.0254,y=q.y/.0254);patch['modify_vias'].append(dict(before=v,after=after,affected_nets=nets));w['vias']=[after if p['id']==vid else p for p in w['vias']]
 for z in changed:
  before=next(p for p in w['lines'] if p['id']==z['id']);patch['modify_lines'].append(dict(before=before,after=z));w['lines']=[z if p['id']==z['id'] else p for p in w['lines']]
proof={n:connected(*[[p for p in w[k] if p['net']==n] for k in ['pads','lines','vias']]) for n in ['ADDR3','L2_M02','L2_M03','L2_M04','L2_M14']};assert all(v['complete'] for v in proof.values())
patch['continuity']=proof;wr(D/'patch.json',patch);wr(D/'expected-capture.json',w)
print(json.dumps(dict(moved=[dict(net=p['after']['net'],before=[p['before']['x']*.0254,p['before']['y']*.0254],after=[p['after']['x']*.0254,p['after']['y']*.0254],affected=p['affected_nets']) for p in patch['modify_vias']],changed_lines=len(patch['modify_lines']),unresolved=patch['unresolved'],unlocalized=unlocalized),indent=2),flush=True)
