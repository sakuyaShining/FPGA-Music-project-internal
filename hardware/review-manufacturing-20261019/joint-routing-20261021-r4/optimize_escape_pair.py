"""Offline U15 power/ground exchange; never writes native PCB."""
import json,sys,math,hashlib,copy,time
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');sys.path.insert(0,str(ROOT))
import shapely
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
import grid_route as g
from physical_geometry import actual_pad,connected_subset
from current_state import current_checkpoint
from resume_offline import read_native
_,checkpoint,SRC=current_checkpoint(ROOT)
s=json.loads(SRC.read_text());PCB=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019/pcb/PCB1.epcb2')
assert hashlib.sha256(PCB.read_bytes()).hexdigest()==checkpoint['pcb_sha256']
native=read_native(PCB)
s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in native.items() if k=='LINE' and p.get('layerId') in [1,2]]
s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in native.items() if k=='VIA']
remove=['4fd0f4b6c360bde9','eb25d4fa91bd7653','e0b3f1ccd5724d8c','3ec9afee3fe5310f','bf66b309980642f5','e525d868a3ef090a']
remove_via=['78fa58214c2b9bfd']
w={**s,'lines':[p for p in s['lines'] if p['id'] not in remove],'vias':[p for p in s['vias'] if p['id'] not in remove_via]}
def ls(net,pts,width):return [dict(net=net,layer=1,x1=a[0]/.0254,y1=a[1]/.0254,x2=b[0]/.0254,y2=b[1]/.0254,width=width/.0254) for a,b in zip(pts,pts[1:])]
p17=next(p for p in s['pads'] if p['ref']=='U15' and p['n']=='17')
p19=next(p for p in s['pads'] if p['ref']=='U15' and p['n']=='19')
old=next(p for p in s['lines'] if p['id']=='e0b3f1ccd5724d8c')
io=ls('3V3_IO',[(p17['x']*.0254,p17['y']*.0254),(p17['x']*.0254,47.45),(old['x2']*.0254,47.45),(old['x2']*.0254,old['y2']*.0254)],.2032)
g.pad_shape=actual_pad;g.GRID=.025;g.GAP=.165;g.WIDTH=.33528;g.VIA_D=.85;g.VIA_H=.4;g.VIA_COST_MM=25
orig=g.raster;g.raster=lambda gs,b,i,s:orig(gs,b,i+g.GRID/math.sqrt(2),s)

w['lines']+=io
from itertools import product
shape=actual_pad
C={};P={}
for n in ['GND','DISP_SCK']:
 f,ps,_=g.geometries(w,n);C[n]={1:unary_union(f[1]),2:unary_union(f[2]),3:unary_union(f[1]+f[2])};P[n]=unary_union(ps)
points=[Point(x/20,y/20) for x,y in product(range(1580,1661),range(864,971))]
valid={}
for n,pad,width in [('GND',p19,.2032),('DISP_SCK',next(p for p in s['pads'] if p['ref']=='U15' and p['n']=='18'),.1524)]:
 a=(pad['x']*.0254,pad['y']*.0254);v=[]
 for q in points:
  if q.distance(C[n][3])<.3048+.158:continue
  if q.distance(P[n])<.1524+.25:continue
  seg=LineString([a,(q.x,q.y)])
  if seg.distance(C[n][1])<width/2+.158:continue
  if any(q.distance(Point(v['x']*.0254,v['y']*.0254))<(.3048+v['hole']*.0254)/2+.35 for v in w['vias']):continue
  v.append(((q.x,q.y),seg,q))
 valid[n]=v
 print(n,'VALID STRAIGHT FANOUTS',len(v),[a for a,_,q in sorted(v,key=lambda t:t[2].distance(Point(81.35,47.3)))[:5]],flush=True)
pairs=[]
for a,sa,qa in valid['GND']:
 for b,sb,qb in valid['DISP_SCK']:
  if qa.distance(qb)<.6096+.158:continue
  if sa.distance(qb)<.1016+.3048+.158 or sb.distance(qa)<.0762+.3048+.158:continue
  if sa.distance(sb)<.1016+.0762+.158:continue
  cost=sa.length+sb.length
  pairs.append(dict(ground=a,clock=b,cost=cost))
pairs.sort(key=lambda p:p['cost'])
(OUT/'joint-fanout-pairs.json').write_text(json.dumps(pairs,indent=2))
print('PAIR_COUNT',len(pairs),'BEST',pairs[:8],flush=True)
