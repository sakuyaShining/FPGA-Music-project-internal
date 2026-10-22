"""Repair a proven missing interlayer join; validate both vias in all layers."""
from pathlib import Path
import sys,json,hashlib,math,re
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT))
from four_layer_geometry import copper,connected
from resume_offline import read_native
from native_plane_geometry import poured_planes
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old=ROOT/'regional-address-20261021-r24'
meta=json.loads((old/'source-meta.json').read_text());pcb=Path(meta['project'])/'pcb/PCB1.epcb2'
assert sha(pcb)==meta['pcb_sha256'];s=json.loads((old/'source-capture.json').read_text());planes=poured_planes(read_native(pcb))
quiet=unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+(.6 if p['net'].startswith('I2S_') else .5),quad_segs=32) for p in s['lines'] if p['layer']==2 and (p['net'].startswith('I2S_') or re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net']))])
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
edge=box(0,0,140,100).boundary
def check(v,data):
 f,pads=copper(data,v['net']);q=Point(v['x']*.0254,v['y']*.0254)
 checks=dict(copper=q.distance(unary_union([g for gs in f.values() for g in gs]))-.3048,hole_pad=q.distance(unary_union(pads))-.1524,drill_drill=min(math.dist((v['x'],v['y']),(o['x'],o['y']))*.0254-(12+o['hole'])*.0254/2 for o in data['vias']),quiet=q.distance(quiet)-.3048,mount=q.distance(mount)-.3048,edge=q.distance(edge)-.3048)
 limits=dict(copper=.165,hole_pad=.25,drill_drill=.35,quiet=.158,mount=.15,edge=.3)
 return all(checks[k]>=limit-1e-7 for k,limit in limits.items()),checks
signal=dict(net='BUS_RETURN',x=73.05/.0254,y=50.925/.0254,diameter=24,hole=12)
valid,signal_checks=check(signal,s);assert valid,signal_checks
before=connected([p for p in s['pads'] if p['net']=='BUS_RETURN'],[p for p in s['lines'] if p['net']=='BUS_RETURN'],[p for p in s['vias'] if p['net']=='BUS_RETURN'])
work={**s,'vias':s['vias']+[signal]};ground=None
# Use the previous project preference for a nearby GND join, not a universal SI rule.
for radius in [.9,1.,1.1,1.2,1.3,1.4]:
 for i in range(32):
  angle=i*math.pi/16;x=73.05+radius*math.cos(angle);y=50.925+radius*math.sin(angle)
  v=dict(net='GND',x=x/.0254,y=y/.0254,diameter=24,hole=12)
  okay,checks=check(v,work)
  if not okay:continue
  q=Point(x,y);ring=q.buffer(.3048,quad_segs=64).difference(q.buffer(.1524,quad_segs=64));areas={str(l):ring.intersection(planes[l]).area for l in [15,2]}
  if min(areas.values())<.15:continue
  ground=v;ground_checks=checks;contacts=areas;distance=radius;break
 if ground:break
assert ground,'No checked nearby reference connection'
work['vias'].append(ground)
after=connected([p for p in s['pads'] if p['net']=='BUS_RETURN'],[p for p in s['lines'] if p['net']=='BUS_RETURN'],[p for p in work['vias'] if p['net']=='BUS_RETURN'])
assert not before['complete'] and after['complete']
audit=dict(source_pcb_sha256=meta['pcb_sha256'],project=meta['project'],before=before,after=after,signal_checks_mm=signal_checks,ground_checks_mm=ground_checks,predicted_ground_reference_contact_mm2=contacts,reference_layers=[15,2],nearby_reference_distance_mm=distance,distance_is_project_preference_not_si_signoff=True,vias=[signal,ground],lines=[],geometric_pass=True,manufacturing_release=False)
(OUT/'plan.json').write_text(json.dumps(audit,indent=2));(OUT/'source-capture.json').write_text(json.dumps(s));print(json.dumps(audit,indent=2),flush=True)
