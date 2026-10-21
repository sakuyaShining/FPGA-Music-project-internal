"""Plan an isolated 0.5mm DAC-LDO supply branch; retain 1mm display trunk.

This branch supplies only U13, not either display. No native edits.
"""
import hashlib,json,math,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');sys.path.insert(0,str(ROOT))
import shapely
from shapely.geometry import box,LineString,Point
from shapely.ops import unary_union
import grid_route as grid
from physical_geometry import actual_pad,connected_subset
from resume_offline import read_native
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
PCB=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019/pcb/PCB1.epcb2')
SRC=ROOT/'quality-r1-source-78.json';before=sha(PCB)
assert before=='be576cabac058fc0754fbc87a07565e69531e59c7d249a6f6d267c5f93c5fc3e'
data=json.loads(SRC.read_text(encoding='utf-8'));native=read_native(PCB)
for p in data['vias']:
    v=native['VIA',p['id']];p['diameter']=v['viaDiameter'];p['hole']=v['holeDiameter']
ids={p['id'] for p in data['lines']}
for (k,i),p in native.items():
    if k=='LINE' and p.get('layerId') in [1,2] and i not in ids:
        data['lines'].append(dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']))
grid.pad_shape=actual_pad;grid.WIDTH=.5;grid.GAP=.17;grid.GRID=.025
raw_raster=grid.raster
grid.raster=lambda gs,b,i,s:raw_raster(gs,b,i+grid.GRID/math.sqrt(2),s)
native_geometries=grid.geometries
def top_only(data,net):
    f,p,k=native_geometries(data,net);f[2].append(box(-1,-1,141,101));return f,p,k
grid.geometries=top_only
start=next(p for p in data['pads'] if p['ref']=='C30' and p['n']=='1')
end=next(p for p in data['pads'] if p['ref']=='U13' and p['n']=='1')
route=None
for margin in [3,6,12]:
    try:route=grid.search(data,'5V_PERIPH',start,end,margin)
    except grid.SealedEscape:break
    if route:break
grid.geometries=native_geometries
result=dict(source_file=str(SRC),source_sha256=sha(SRC),native_pcb_sha256=before,
    net='5V_PERIPH',branch='C30.1 to U13.1 DAC regulator supply only',
    display_main_trunk_unchanged=True,branch_width_mm=.5,branch_copper_thickness_assumption_mm=.035,
    current_envelope_a=.6,requires_native_drc=True,manufacturing_release=False,native_imported=False)
if route:
    assert not route['vias'] and all(p['layer']==1 for p in route['lines'])
    f,_,k=native_geometries(data,'5V_PERIPH');cu=unary_union(f[1]);ko=unary_union(k);minimum=999
    for p in route['lines']:
        q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)])
        gap=q.distance(cu)-.25;minimum=min(minimum,gap)
        assert gap>=.158 and q.distance(ko)>=.4
    length=sum(math.hypot(p['x1']-p['x2'],p['y1']-p['y2'])*.0254 for p in route['lines'])
    assert length<=15
    # DC resistance estimate at 20C only; not an ampacity/thermal qualification.
    resistance=.01724*(length/1000)/(.5*.035)
    result.update(lines=route['lines'],vias=[],length_mm=length,min_foreign_gap_mm=minimum,
        estimated_resistance_ohm_20c=resistance,estimated_drop_v_at_envelope=resistance*.6,
        estimated_copper_loss_w_at_envelope=resistance*.6**2,
        independent_geometry_pass=True,route_found=True,
        estimate_limit='Assumes 35um copper and 20C resistivity, excludes pads/connections; not whole-board current/thermal/voltage signoff')
else:result.update(route_found=False,lines=[],vias=[])
(OUT/'dac-power-branch-plan.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
assert sha(PCB)==before
print(json.dumps({k:v for k,v in result.items() if k not in ['lines']},indent=2))
