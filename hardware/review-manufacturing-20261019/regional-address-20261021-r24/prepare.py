"""Reserve real, four-layer checked pin escapes before mature trunk routing."""
from pathlib import Path
import sys,json,hashlib,shutil,math,re
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
sys.path.insert(0,str(ROOT))
from physical_geometry import actual_pad
from four_layer_geometry import copper
from resume_offline import read_native
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
from shapely.strtree import STRtree
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
previous=ROOT/'regional-net-rebuild-20261021-r23'
meta=json.loads((previous/'checkpoint-meta.json').read_text())
project=Path(json.loads((ROOT/'REGIONAL-WORK-IN-PROGRESS.json').read_text())['project'])
pcb=project/'pcb/PCB1.epcb2';assert sha(pcb)==meta['pcb_sha256']
s=json.loads((previous/'checkpoint-capture.json').read_text());raw=read_native(pcb)
s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in raw.items() if k=='VIA']
nets=['ADDR0','ADDR1','ADDR2','ADDR3','MUX_DISABLE','BUS_SCK','BUS_MOSI']
assert not any(p['net'] in nets for k in ['lines','vias'] for p in s[k])
(OUT/'source-meta.json').write_text(json.dumps(dict(project=str(project),pcb_sha256=sha(pcb)),indent=2))
(OUT/'source-capture.json').write_text(json.dumps(s))
(OUT/'regional-edit-plan.json').write_text(json.dumps(dict(routing_nets=nets),indent=2))
quiet=unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+(.6 if p['net'].startswith('I2S_') else .5),quad_segs=32) for p in s['lines'] if p['layer']==2 and (p['net'].startswith('I2S_') or re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net']))])
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
fan=dict(lines=[],vias=[],escaped=[],unescaped=[])
static={}
pad_tree=STRtree([actual_pad(p) for p in s['pads']])
def distance(q,t):
 return q.distance(t.geometries[t.nearest(q)]) if len(t.geometries) else math.inf
for net in nets:
 f,_=copper(s,net)
 static[net]=(STRtree(f[1]),STRtree([q for shapes in f.values() for q in shapes]))
targets=[p for p in s['pads'] if p['net'] in nets and p['layer']==1]
# Order adjacent fine pitch pads by package and pin, so they get staggered vias.
targets.sort(key=lambda p:(p['ref'],int(p['n']) if p['n'].isdigit() else 100))
for p in targets:
 top_tree,all_tree=static[p['net']]
 dynamic=[LineString([(v['x1']*.0254,v['y1']*.0254),(v['x2']*.0254,v['y2']*.0254)]).buffer(.0762,quad_segs=32) for v in fan['lines'] if v['net']!=p['net']]
 dynamic_v=[Point(v['x']*.0254,v['y']*.0254).buffer(.3048,quad_segs=32) for v in fan['vias'] if v['net']!=p['net']]
 dyn_top=STRtree(dynamic+dynamic_v);dyn_all=STRtree(dynamic+dynamic_v)
 siblings=[a for a in s['pads'] if a['ref']==p['ref']];cx=sum(a['x'] for a in siblings)/len(siblings);cy=sum(a['y'] for a in siblings)/len(siblings)
 a=math.radians(p['rotation']);axis=(math.cos(a),math.sin(a)) if p['shape'][1]>=p['shape'][2] else (-math.sin(a),math.cos(a))
 sign=1 if axis[0]*(p['x']-cx)+axis[1]*(p['y']-cy)>=0 else -1
 out=(axis[0]*sign,axis[1]*sign);start=(p['x']*.0254,p['y']*.0254)
 # Protect the direct pin exit of every other selected pin on the same row.
 corridors=[]
 for other in siblings:
  if other['id']==p['id'] or other['net'] not in nets:continue
  angle=math.radians(other['rotation']);ax=(math.cos(angle),math.sin(angle)) if other['shape'][1]>=other['shape'][2] else (-math.sin(angle),math.cos(angle))
  sg=1 if ax[0]*(other['x']-cx)+ax[1]*(other['y']-cy)>=0 else -1
  x,y=other['x']*.0254,other['y']*.0254
  corridors.append(LineString([(x-ax[0]*sg*1.9,y-ax[1]*sg*1.9),(x+ax[0]*sg*1.9,y+ax[1]*sg*1.9)]))
 corridor=unary_union(corridors)
 chosen=None
 for direction in [(-out[0],-out[1]),out]:
  for dist in [1.25+i*.125 for i in range(23)]:
   for lateral in [0,.1,-.1,.2,-.2,.3,-.3,.5,-.5]:
    q=(start[0]+direction[0]*dist-direction[1]*lateral,start[1]+direction[1]*dist+direction[0]*lateral)
    if not(.7<q[0]<139.3 and .7<q[1]<99.3):continue
    line=LineString([start,q]);v=Point(q)
    if min(distance(line,top_tree),distance(line,dyn_top))<.0762+.165 or min(distance(v,all_tree),distance(v,dyn_all))<.3048+.165:continue
    if distance(v,pad_tree)<.1524+.25:continue
    if any(math.dist(q,(o['x']*.0254,o['y']*.0254))-(.3048+o['hole']*.0254)/2<.35 for o in s['vias']):continue
    if v.distance(quiet)<.3048+.165 or v.distance(mount)<.3048+.15 or line.distance(mount)<.0762+.15:continue
    if v.distance(corridor)<.3048+.0762+.165 or line.distance(corridor)<.1524+.165:continue
    chosen=q;break
   if chosen:break
  if chosen:break
 if chosen:
  line=dict(net=p['net'],layer=1,x1=p['x'],y1=p['y'],x2=chosen[0]/.0254,y2=chosen[1]/.0254,width=6)
  via=dict(net=p['net'],x=chosen[0]/.0254,y=chosen[1]/.0254,diameter=24,hole=12)
  fan['lines'].append(line);fan['vias'].append(via);s['lines'].append(line);s['vias'].append(via)
  fan['escaped'].append([p['ref'],p['n'],p['net'],chosen])
 else:fan['unescaped'].append([p['ref'],p['n'],p['net']])
 print('ESCAPE',p['ref'],p['n'],p['net'],bool(chosen),flush=True)
(OUT/'reserved-escapes.json').write_text(json.dumps(fan,indent=2))
for name in ['exchange.py','ses.py','run_bounded.py','calibration-result.json']:
 shutil.copyfile(previous/name,OUT/name)
path=OUT/'exchange.py';text=path.read_text();text=text.replace("    return cp,pcb,s\n\ndef build():", "    fan=json.loads((OUT/'reserved-escapes.json').read_text())\n    s['lines']+=fan['lines'];s['vias']+=fan['vias']\n    return cp,pcb,s\n\ndef build():")
path.write_text(text)
print(json.dumps(dict(escaped=len(fan['escaped']),unescaped=fan['unescaped']),indent=2),flush=True)
