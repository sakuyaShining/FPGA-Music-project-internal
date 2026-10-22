"""Offline U15 power/ground exchange; never writes native PCB."""
import json,sys,math,hashlib,copy,time
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;OUT=BASE/'local-v3';OUT.mkdir(exist_ok=False)
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
gnd=ls('GND',[(p19['x']*.0254,p19['y']*.0254),(81.0,47.2)],.2032)
via=dict(net='GND',x=81.0/.0254,y=47.2/.0254,diameter=24,hole=12)
w['lines']+=io+gnd;w['vias'].append(via)
g.pad_shape=actual_pad;g.GRID=.025;g.GAP=.165;g.WIDTH=.33528;g.VIA_D=.85;g.VIA_H=.4;g.VIA_COST_MM=25
orig=g.raster;g.raster=lambda gs,b,i,s:orig(gs,b,i+g.GRID/math.sqrt(2),s)
def validate(net,lines,vias):
 f,ps,ko=g.geometries(w,net);cu={l:unary_union(f[l]) for l in [1,2]};both=unary_union(f[1]+f[2]);minimum=99.
 for p in lines:
  q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]);gap=q.distance(cu[p['layer']])-p['width']*.0254/2;minimum=min(gap,minimum)
  assert gap>=.158,(net,'track',gap,p)
 for p in vias:
  q=Point(p['x']*.0254,p['y']*.0254);gap=q.distance(both)-p['diameter']*.0254/2;minimum=min(gap,minimum)
  assert gap>=.158,(net,'via',gap,p)
  assert q.distance(unary_union(ps))-p['hole']*.0254/2>=.25,(net,'hole-to-pad')
  for v in w['vias']:
   if v is p:continue
   assert q.distance(Point(v['x']*.0254,v['y']*.0254))-(p['hole']+v['hole'])*.0254/2>=.3499,(net,'drill')
 return minimum
print('LOCAL PRECHECK',validate('3V3_IO',io,[]),validate('GND',gnd,[via]),flush=True)
power_old=next(p for p in s['lines'] if p['id']=='e525d868a3ef090a')
a=dict(x=power_old['x1'],y=power_old['y1'],layer=1);b=dict(x=power_old['x2'],y=power_old['y2'],layer=1)
# Reserve the planned clock escape so the power detour cannot occupy it.
fan_points=[(81.37398,45.8724),(81.37398,46.7),(81.6,46.95),(81.6,47.8),(80.6,47.8),(80.6,48.45)]
guard=ls('DISP_SCK',fan_points,.1524);w['lines']+=guard
clock_via=dict(net='DISP_SCK',x=80.6/.0254,y=48.45/.0254,diameter=24,hole=12)
w['vias'].append(clock_via)
print('CLOCK FANOUT CHECK',validate('DISP_SCK',guard,[clock_via]),flush=True)
power=None
for margin in [4,8]:
 power=g.search(w,'3V3_PERIPH',a,b,margin)
 if power:break
assert power,'No safe local power detour'
assert len(power['vias'])<=2 and sum(math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254 for p in power['lines'])<=8,'Power detour quality budget'
w['lines']=[p for p in w['lines'] if p not in guard]+power['lines'];w['vias']=[p for p in w['vias'] if p is not clock_via]+power['vias']
for n,l,v in [('3V3_IO',io,[]),('GND',gnd,[via]),('3V3_PERIPH',power['lines'],power['vias'])]:print('VALIDATED',n,validate(n,l,v),flush=True)
for n in ['3V3_IO','3V3_PERIPH']:
 assert connected_subset([p for p in s['pads'] if p['net']==n],[p for p in w['lines'] if p['net']==n],[p for p in w['vias'] if p['net']==n])['complete'],n
plan=dict(source_file=str(SRC),source_sha256=hashlib.sha256(SRC.read_bytes()).hexdigest(),native_pcb_sha256=checkpoint['pcb_sha256'],remove_line_ids=remove,remove_via_ids=remove_via,lines=io+gnd+power['lines'],vias=[via]+power['vias'],power=power,native_imported=False,manufacturing_release=False)
(OUT/'local-escape-exchange-plan.json').write_text(json.dumps(plan,indent=2));(OUT/'local-escape-working.json').write_text(json.dumps(w))
print('LOCAL EXCHANGE ACCEPTED OFFLINE',len(plan['lines']),len(plan['vias']),flush=True)
# Route a complete clock net with the actual un-ripped signal surroundings.
g.WIDTH=.1524;g.VIA_D=.6096;g.VIA_H=.3048;g.VIA_COST_MM=15;g.GRID=.05;g.SEARCH_MARGINS=[8,22,50]
fan=ls('DISP_SCK',fan_points,.1524)
w['lines']+=fan;w['vias'].append(clock_via)
p18=next(p for p in w['pads'] if p['ref']=='U15' and p['n']=='18')
w['pads']=[{**p,'routing_pad_exclude':True} if p['id']==p18['id'] else p for p in w['pads']]+[{**p18,'id':'anchor-'+p18['id'],'ref':'FANOUT-U15','x':clock_via['x'],'y':clock_via['y'],'rotation':0,'layer':12,'shape':['ELLIPSE',24,24,0]}]
clock=g.plan(w,'DISP_SCK');clock['lines']+=fan;clock['vias'].append(clock_via)
assert connected_subset([p for p in s['pads'] if p['net']=='DISP_SCK'],clock['lines'],clock['vias'])['complete']
assert len(clock['vias'])<=5,'Clock via budget'
w['lines']+=clock['lines'];w['vias']+=clock['vias'];print('CLOCK VALIDATED',validate('DISP_SCK',clock['lines'],clock['vias']),flush=True)
plan['clock']=clock;plan['lines']+=clock['lines'];plan['vias']+=clock['vias']
(OUT/'local-escape-with-clock-plan.json').write_text(json.dumps(plan,indent=2))
print('CLOCK CANDIDATE',len(clock['vias']),flush=True)
