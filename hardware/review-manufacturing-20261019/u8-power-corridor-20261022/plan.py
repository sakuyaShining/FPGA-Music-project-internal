"""Co-optimize the two power rails blocking U8 lower control-pin escapes."""
from pathlib import Path
import sys,json,math,hashlib
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT))
from four_layer_geometry import copper,connected
from resume_offline import read_native
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
from shapely.strtree import STRtree
read=lambda p:json.loads(p.read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pointer=read(ROOT/'REGIONAL-WORK-IN-PROGRESS.json');pcb=Path(pointer['project'])/'pcb/PCB1.epcb2';assert sha(pcb)==pointer['pcb_sha256']
(OUT/'plan.json').write_text(json.dumps(dict(source_pcb_sha256=pointer['pcb_sha256'],geometric_pass=False,status='planning')))
s=read(Path(pointer['source_capture']));raw=read_native(pcb)
s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
io_ids=['e00c4c6d46ea3e61','20e4adddfda2dc40','081a5ce595486d80','c1a81b84fde5e562','de88e61f37dcd55d']
v5_ids=['e953ebcb1915ebd3','f0da1f0d6f552110','b0e6235958308ecc']
preset_ids=['07e564c9d3ed423d','7a071374c6f96896','d9c7356771e47de4']
load_ids=['86d0419db8fc184f','ad3ff9670edb5efe','a80d08dfd19733f2','4a72bb51659f0239']
remove=[p for p in s['lines'] if p['id'] in io_ids+v5_ids+preset_ids+load_ids];assert len(remove)==15
oldvia=next(v for v in s['vias'] if v['id']=='714cedfbd5d98db7')
oldload=next(v for v in s['vias'] if v['id']=='c246ee0f0939a38f')
work={**s,'lines':[p for p in s['lines'] if p['id'] not in io_ids+v5_ids+preset_ids+load_ids],'vias':[v for v in s['vias'] if v['id'] not in [oldvia['id'],oldload['id']]]}
a=next(p for p in s['pads'] if p['ref']=='U8' and p['n']=='16');b=next(p for p in s['pads'] if p['ref']=='U8' and p['n']=='10')
left=next(p for p in remove if p['id']==v5_ids[0]);right=next(p for p in remove if p['id']==v5_ids[2])
ax,ay=a['x']*.0254,a['y']*.0254;bx,by=b['x']*.0254,b['y']*.0254
def lines(net,pts,width):return [dict(net=net,layer=1,x1=p[0]/.0254,y1=p[1]/.0254,x2=q[0]/.0254,y2=q[1]/.0254,width=width/.0254) for p,q in zip(pts,pts[1:])]
def shape(p):return LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)])
widthio=next(p for p in remove if p['id']==io_ids[0])['width']*.0254;width5=left['width']*.0254
assert all(abs(p['width']*.0254-widthio)<1e-7 for p in remove if p['net']=='3V3_IO')
preset=lines('PRESET1',[(62.925,52.15),(63.525,51.55),(65.3,51.55),(65.77499926,51.8)],.1524)
preset+=lines('PRESET1',[(65.77499926,51.8),(67.84999946,48.95000116)],.1524)
preset[-1]['layer']=2
newvia={k:v for k,v in oldvia.items() if k!='id'};newvia['y']=51.8/.0254
# INPUT_LOAD_N's crossing branch is recovered with the buses, allowing a
# mature router to reconnect its preserved source and resistor islands.
reserved={**work,'lines':work['lines']+preset,'vias':work['vias']+[newvia]}
trees={n:STRtree(copper(reserved,n)[0][1]) for n in ['3V3_IO','5V_PERIPH']}
best=None;feasible=[]
for yi in [49.75,49.8,49.85,49.9,49.95,50.0]:
 for y5 in [50.7,50.75,50.8,50.85,50.9,50.95,51.0,51.1,51.2]:
  for x5 in [57.6,57.8,58.0,58.2,58.4]:
   io=lines('3V3_IO',[(ax,ay),(ax,yi),(bx,yi),(bx,by)],widthio)
   v5=lines('5V_PERIPH',[(left['x1']*.0254,left['y1']*.0254),(x5,left['y1']*.0254),(x5,y5),(right['x2']*.0254-(y5-right['y2']*.0254),y5),(right['x2']*.0254,right['y2']*.0254)],width5)
   route=io+v5;gaps=[]
   for p in route:
    q=shape(p);t=trees[p['net']];gaps.append(q.distance(t.geometries[t.nearest(q)])-p['width']*.0254/2)
   gaps += [shape(p).distance(shape(q))-(p['width']+q['width'])*.0254/2 for p in io for q in v5]
   gap=min(gaps);trial=dict(io_y_mm=yi,periph_y_mm=y5,periph_turn_x_mm=x5,min_foreign_gap_mm=gap,lines=route)
   if best is None or gap>best['min_foreign_gap_mm']:best=trial
   # Unchanged left 5V copper already has ~0.16345mm gap; preserve native
   # 6mil rules and use the established 0.158mm independent check margin.
   if gap>=.158:feasible.append(trial)
assert sha(pcb)==pointer['pcb_sha256']
if feasible:
 chosen=min(feasible,key=lambda v:(abs(v['io_y_mm']-49.85)+abs(v['periph_y_mm']-50.8),-v['min_foreign_gap_mm']))
 after={**reserved,'lines':reserved['lines']+chosen['lines']};proofs={}
 for net in ['3V3_IO','5V_PERIPH','PRESET1']:
  proofs[net]=connected([p for p in s['pads'] if p['net']==net],[p for p in after['lines'] if p['net']==net],[p for p in after['vias'] if p['net']==net]);assert proofs[net]['complete'],proofs
 signal_gaps=[];via_gaps={}
 for net,new in [('PRESET1',newvia)]:
  f,pads=copper(after,net);sigtrees={l:STRtree(shapes) for l,shapes in f.items()}
  for p in [p for p in preset if p['net']==net]:
   q=shape(p);t=sigtrees[p['layer']];signal_gaps.append(q.distance(t.geometries[t.nearest(q)])-.0762)
  viaq=Point(new['x']*.0254,new['y']*.0254)
  checks=dict(copper=viaq.distance(unary_union([q for shapes in f.values() for q in shapes]))-.3048,hole_pad=viaq.distance(unary_union(pads))-.1524,drill_drill=min(math.dist((new['x'],new['y']),(v['x'],v['y']))*.0254-(12+v['hole'])*.0254/2 for v in after['vias'] if v is not new))
  assert checks['copper']>=.158 and checks['hole_pad']>=.25 and checks['drill_drill']>=.35,checks
  via_gaps[net]=checks
 assert min(signal_gaps)>=.158,signal_gaps
 loadproof=connected([p for p in s['pads'] if p['net']=='INPUT_LOAD_N'],[p for p in after['lines'] if p['net']=='INPUT_LOAD_N'],[p for p in after['vias'] if p['net']=='INPUT_LOAD_N'])
 assert not loadproof['complete']
 plan=dict(source_pcb_sha256=pointer['pcb_sha256'],project=pointer['project'],remove_lines=remove,remove_vias=[oldvia,oldload],lines=chosen['lines']+preset,vias=[newvia],required_recovery_nets=['INPUT_LOAD_N'],recovery_islands=loadproof,selected_variant={k:v for k,v in chosen.items() if k!='lines'},power_and_preset_connectivity=proofs,neighbor_signal_min_track_gap_mm=min(signal_gaps),neighbor_signal_via_checks_mm=via_gaps,feasible_variants=len(feasible),geometric_pass=True,native_apply_requires_complete_recovery=True,manufacturing_release=False)
else:plan=dict(source_pcb_sha256=pointer['pcb_sha256'],geometric_pass=False,best=best,manufacturing_release=False)
(OUT/'plan.json').write_text(json.dumps(plan,indent=2));(OUT/'source-capture.json').write_text(json.dumps(s));print(json.dumps({k:v for k,v in plan.items() if k not in ['lines','remove_lines']},indent=2),flush=True)
