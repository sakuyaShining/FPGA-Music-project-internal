"""Offline four-layer alternative. L2 stays GND; L3 routes selected controls.
No native changes. Existing two-layer release pointer remains authoritative.
"""
import sys,json,copy,math,hashlib,time,traceback,gc
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;OUT=BASE/'four-layer-offline';OUT.mkdir(exist_ok=False)
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');sys.path.insert(0,str(ROOT))
import shapely
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
import grid_route as g,reserve_escape as e
from physical_geometry import actual_pad
from current_state import current_checkpoint
from resume_offline import read_native
_,cp,SRC=current_checkpoint(ROOT);s=json.loads(SRC.read_text());PCB=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019/pcb/PCB1.epcb2')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();assert sha(PCB)==cp['pcb_sha256']
native=read_native(PCB)
s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in native.items() if k=='LINE' and p.get('layerId') in [1,2]]
s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in native.items() if k=='VIA']
pending=cp['pending_nets'];u15={p['net'] for p in s['pads'] if p['ref']=='U15'}-{'GND','3V3_IO','3V3_PERIPH'}
# Keep the existing audio nets for this initial alternative: avoid extending scope.
selected=list(pending)+sorted(u15-set(pending))+['SCAN_LATCH','INPUT_LOAD_N','I2C_SDA','BUS_RETURN']
assert len(selected)==len(set(selected))
w={**s,'pads':copy.deepcopy(s['pads']),'lines':[p for p in s['lines'] if p['net'] not in selected],'vias':[p for p in s['vias'] if p['net'] not in selected]}
g.pad_shape=e.pad_shape=actual_pad;g.GRID=e.GRID=.05;g.GAP=e.GAP=.165;g.WIDTH=e.WIDTH=.1524
orig=g.raster;g.raster=e.raster=lambda gs,b,i,s:orig(gs,b,i+g.GRID/math.sqrt(2),s)
fans={}
for n in selected:fans[n]=e.reserve(s,w,n)
# PTH pads already reach inner copper; do not fabricate an unnecessary fanout.
refs={p['ref'] for p in s['pads'] if p['layer']!=12}
fan_nets=selected
print('SOURCE',cp['pcb_sha256'],'SELECTED',selected,flush=True)
a=e.grid_mux_fanouts(w,fan_nets,refs=refs,max_pad_short_mm=3.0)
b=e.new_mux_fanouts(w,fan_nets,refs=refs,max_pad_short_mm=3.0)
for f in [a,b]:
 for kind in ['lines','vias']:
  for p in f[kind]:fans[p['net']][kind].append(p)
(OUT/'outer-fanouts.json').write_text(json.dumps(dict(fans=fans,working=w)),encoding='utf-8')
print('FANOUTS', {n:(len(f['lines']),len(f['vias'])) for n,f in fans.items()},flush=True)
# A via traverses all four layers; all foreign through-via copper is an obstacle
# on L3. Surface-only SMD pads and tracks are absent on L3.
def inner_data(work):
 ps=[]
 for p in work['pads']:
  if p.get('routing_pad_exclude'):continue
  if p['layer']==12:ps.append({**p,'layer':1})
 return dict(pads=ps,lines=[{**p,'layer':1} for p in work['lines'] if p.get('layer')==16],vias=work['vias'])
# Prevent an accidental second abstract routing layer; no blind vias are used.
inner_geometry_original=g.geometries
def inner_geometries(data,net):
 f,ps,ko=inner_geometry_original(data,net)
 f[2].append(box(-1,-1,141,101))
 return f,ps,ko
routes=[];failed=[]
def save():
 (OUT/'plan.json').write_text(json.dumps(dict(source_file=str(SRC),source_sha256=sha(SRC),native_pcb_sha256=cp['pcb_sha256'],selected=selected,routes=routes,failed=failed,native_imported=False,manufacturing_release=False,L2_role='continuous GND',L3_role='control signals and remaining GND',requires_stackup_and_bottom_return_audit=True),indent=2))
for n in selected:
 print('START',n,flush=True)
 missing=[p['ref']+'.'+p['n'] for p in w['pads'] if p['net']==n and p['layer']!=12 and not p.get('routing_pad_exclude')]
 if missing:
  failed.append(dict(net=n,reason='missing_outer_fanout',pads=missing))
  for k in ['lines','vias']:w[k]=[p for p in w[k] if p['net']!=n]+[p for p in s[k] if p['net']==n]
  print('NO FANOUT',n,missing,flush=True);save();continue
 try:
  abstract=inner_data(w);g.geometries=inner_geometries;g.GRID=.1;g.VIA_COST_MM=100;g.SEARCH_MARGINS=[8,22,50]
  trial=g.plan(abstract,n);assert not trial['vias'],'Inner route attempted an unintended second signal layer'
  inner=[{**p,'layer':16} for p in trial['lines']]
  lines=fans[n]['lines']+inner;vias=fans[n]['vias']
  # Every actual surface pad must touch its retained/new outer fanout; all
  # inner anchors must be connected by the generated inner tree.
  metrics=dict(old_vias=sum(p['net']==n for p in s['vias']),new_vias=len(vias),old_length_mm=sum(math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254 for p in s['lines'] if p['net']==n),new_length_mm=sum(math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254 for p in lines))
  routes.append(dict(net=n,lines=lines,vias=vias,edges=trial['edges'],metrics=metrics))
  for k,vals in [('lines',lines),('vias',vias)]:w[k]=[p for p in w[k] if p['net']!=n]+vals
  print('OFFLINE',n,metrics,flush=True)
 except Exception as ex:
  failed.append(dict(net=n,reason=repr(ex)))
  for k in ['lines','vias']:w[k]=[p for p in w[k] if p['net']!=n]+[p for p in s[k] if p['net']==n]
  print('FAILED',n,repr(ex),flush=True)
 finally:g.geometries=inner_geometry_original;save();gc.collect()
(OUT/'working-final.json').write_text(json.dumps(w));assert sha(PCB)==cp['pcb_sha256'];print('DONE',len(routes),len(failed),'NATIVE UNCHANGED',flush=True)
