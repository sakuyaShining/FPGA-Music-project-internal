"""Relocate the MOSI pulldown using current native footprint and copper."""
from pathlib import Path
import sys,json,math,copy,hashlib,ast
B=Path(__file__).resolve().parent;R=B.parent;O=B/'mosi';O.mkdir(exist_ok=True)
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path[:0]=[str(R),str(B)]
from native_project import PROJECT
from resume_offline import read_native
from physical_geometry import actual_pad
from four_layer_geometry import copper
from shapely.geometry import Point,LineString,box
from shapely.affinity import rotate,translate
from shapely.ops import unary_union
read=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cp=read(R/'REGIONAL-WORK-IN-PROGRESS.json');assert sha(PROJECT/'pcb/PCB1.epcb2')==cp['pcb_sha256']=='8b9b68a5f42a446b2c716e41d6693f480fb9c8048e6c1c7080b151244978aa19'
s=read(Path(cp['source_capture']));raw=read_native(PROJECT/'pcb/PCB1.epcb2')
docs={};current=None
for line in (PROJECT/'pcb/PCB1.epcb2').read_text(encoding='utf8').splitlines():
 if '||' not in line:continue
 h,b=line.split('||',1);h=json.loads(h);v=json.loads(b.rstrip('|')) if b.rstrip('|').strip() else None
 if h['type']=='DOCHEAD':current=v['uuid'];docs.setdefault(current,{})
 if current:docs[current][h['type'],h.get('id')]=v
# Reuse only the pure footprint path routine; do not execute historical plans.
t=ast.parse((R/'regional-layout-20261021-r19/layout_compare.py').read_text(encoding='utf8'))
exec(compile(ast.Module(body=[n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='points'],type_ignores=[]),'points','exec'))
attrs={}
for (k,i),v in raw.items():
 if k=='ATTR':attrs.setdefault(v['parentId'],{})[v['key']]=v['value']
boxes={};locals={};cid_by_ref={}
for cid,a in attrs.items():
 if 'Designator' not in a or 'Footprint' not in a or ('COMPONENT',cid) not in raw:continue
 geoms=[]
 for (k,i),p in docs[a['Footprint']].items():
  if not p:continue
  if k=='POLY':
   pts=points(p.get('path',[]));sw=p.get('width',0)/2
   if pts:geoms.append(box(min(x for x,y in pts)-sw,min(y for x,y in pts)-sw,max(x for x,y in pts)+sw,max(y for x,y in pts)+sw))
  if k=='PAD':
   q=p['defaultPad'];x,y=p['centerX'],p['centerY'];geoms.append(rotate(box(x-q['width']/2,y-q['height']/2,x+q['width']/2,y+q['height']/2),p.get('padAngle',0),origin=(x,y)))
 if not geoms:continue
 ref=a['Designator'];locals[ref]=unary_union(geoms);c=raw['COMPONENT',cid];q=translate(rotate(locals[ref],c['angle'],origin=(0,0)),c['x'],c['y']);boxes[ref]=box(*[v*.0254 for v in q.bounds]);cid_by_ref[ref]=cid
for p in s['pads']:
 if p['ref'] not in cid_by_ref:boxes[p['ref']]=box(*actual_pad(p).bounds)
cid=cid_by_ref['R64'];c=raw['COMPONENT',cid];oldps=[p for p in s['pads'] if p['ref']=='R64'];mx=sum(p['x'] for p in oldps)/2*.0254;my=sum(p['y'] for p in oldps)/2*.0254
remove_lines=[p for p in s['lines'] if p['id']=='5f4c1224cbcfd431'];remove_vias=[p for p in s['vias'] if p['id']=='0af4c21a70dbb0c0'];assert len(remove_lines)==len(remove_vias)==1
work=copy.deepcopy(s);work['lines']=[p for p in work['lines'] if p not in remove_lines];work['vias']=[p for p in work['vias'] if p not in remove_vias];work['pads']=[p for p in work['pads'] if p['ref']!='R64']
foreign={n:unary_union(copper(work,n)[0][1]) for n in ['GND','BUS_MOSI']}
holes=unary_union([Point(p['x']*.0254,p['y']*.0254).buffer(p['hole']*.0254/2,quad_segs=32) for p in work['vias']])
candidates=[]
for angle in [0,90,180,270]:
 for x in [67.5+i*.25 for i in range(29)]:
  for y in [46+i*.25 for i in range(16)]:
   rad=math.radians(angle);cs,sn=math.cos(rad),math.sin(rad);ox,oy=c['x']*.0254-mx,c['y']*.0254-my;origin=(x+ox*cs-oy*sn,y+ox*sn+oy*cs)
   q=translate(rotate(locals['R64'],angle,origin=(0,0)),origin[0]/.0254,origin[1]/.0254);bbox=box(*[v*.0254 for v in q.bounds]);bgap=min(bbox.distance(b) for ref,b in boxes.items() if ref!='R64')
   if bgap<.55:continue
   pads=[{**p,'x':(x+(p['x']*.0254-mx)*cs-(p['y']*.0254-my)*sn)/.0254,'y':(y+(p['x']*.0254-mx)*sn+(p['y']*.0254-my)*cs)/.0254,'rotation':p['rotation']+angle} for p in oldps]
   cg=min(actual_pad(p).distance(foreign[p['net']]) for p in pads);hg=min(actual_pad(p).distance(holes) for p in pads)
   if cg<.18 or hg<.25:continue
   # Prefer the accessible U8 data corridor and nearby real GND stitch.
   candidates.append(dict(midpoint_mm=[x,y],rotation=angle,origin_mil=[v/.0254 for v in origin],pads=pads,bbox_gap_mm=bgap,copper_gap_mm=cg,hole_gap_mm=hg,score=math.hypot(x-69.5,y-48.2)))
candidates.sort(key=lambda p:p['score'])
(O/'placement-options.json').write_text(json.dumps(dict(source_pcb_sha256=cp['pcb_sha256'],component=cid,attrs=attrs[cid],remove_lines=remove_lines,remove_vias=remove_vias,candidates=candidates),indent=2),encoding='utf8')
print('OPTIONS',len(candidates));print(json.dumps(candidates[:8],indent=2),flush=True)
