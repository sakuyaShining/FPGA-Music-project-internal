"""Complete power connectivity only together with a compatible BUS_RETURN route."""
import copy,hashlib,json,math,sys,time
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');sys.path.insert(0,str(ROOT))
import shapely
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
import grid_route as grid
import reserve_escape as escape
from physical_geometry import actual_pad,connected_subset
from resume_offline import read_native
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
PCB=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019/pcb/PCB1.epcb2')
SRC=ROOT/'quality-r1-source-78.json';before=sha(PCB)
assert before=='be576cabac058fc0754fbc87a07565e69531e59c7d249a6f6d267c5f93c5fc3e'
data=read(SRC);native=read_native(PCB)
ids={p['id'] for p in data['lines']}
for (k,i),p in native.items():
    if k=='LINE' and p.get('layerId') in [1,2] and i not in ids:
        data['lines'].append(dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']))
for p in data['vias']:
    n=native['VIA',p['id']];p['diameter']=n['viaDiameter'];p['hole']=n['holeDiameter']
branch=read(OUT/'dac-power-branch-plan.json');power=read(OUT/'power-bus-return-unblocked/power-plan.json')
assert power['all_pad_groups_connected'] and power['excluded_native_nets_require_joint_replacement']==['BUS_RETURN']
assert branch['route_found'] and branch['independent_geometry_pass']
power_lines=branch['lines']+power['lines'];power_vias=power['vias']
assert not power_vias,'This trial specifically keeps both new supply connections on top copper'
working={**data,'pads':copy.deepcopy(data['pads']),
    'lines':[p for p in data['lines'] if p['net']!='BUS_RETURN']+power_lines,
    'vias':[p for p in data['vias'] if p['net']!='BUS_RETURN']+power_vias}
grid.pad_shape=escape.pad_shape=actual_pad
grid.WIDTH=escape.WIDTH=.1524;grid.GAP=escape.GAP=.17;grid.GRID=escape.GRID=.075
grid.VIA_COST_MM=12;grid.SEARCH_MARGINS=[8,22,50]
rr=grid.raster;grid.raster=escape.raster=lambda gs,b,i,s:rr(gs,b,i+grid.GRID/math.sqrt(2),s)
fans=escape.reserve(data,working,'BUS_RETURN')
print('RETAINED SHORT BUS FANOUTS',len(fans['lines']),len(fans['vias']),flush=True)
result=dict(source_file=str(SRC),source_sha256=sha(SRC),native_pcb_sha256=before,
    additive_power_lines=power_lines,additive_power_vias=power_vias,replace_nets=['BUS_RETURN'],
    dependency_sha256={n:sha(OUT/n) for n in ['dac-power-branch-plan.json','power-bus-return-unblocked/power-plan.json']},
    independent_geometry_pass=False,both_nets_complete=False,native_imported=False,manufacturing_release=False)
length=lambda ls:sum(math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254 for p in ls)
try:
    route=grid.plan(working,'BUS_RETURN')
    lines=fans['lines']+route['lines'];vias=fans['vias']+route['vias']
    conn=connected_subset([p for p in data['pads'] if p['net']=='BUS_RETURN'],lines,vias)
    assert conn['complete'],conn
    lines=conn['lines'];vias=conn['vias']
    final={**data,'lines':[p for p in data['lines'] if p['net']!='BUS_RETURN']+power_lines+lines,
           'vias':[p for p in data['vias'] if p['net']!='BUS_RETURN']+power_vias+vias}
    min_gaps={}
    for net,newlines,newvias in [('BUS_RETURN',lines,vias),('5V_PERIPH',power_lines,power_vias)]:
        f,_,k=grid.geometries(final,net);cu={l:unary_union(f[l]) for l in [1,2]};both=unary_union(f[1]+f[2]);ko=unary_union(k);gaps=[]
        for p in newlines:
            q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)])
            gap=q.distance(cu[p['layer']])-p['width']*.0254/2;gaps.append(gap)
            assert gap>=.158 and q.distance(ko)>=p['width']*.0254/2+.15,(net,'track',gap)
        for i,p in enumerate(newvias):
            q=Point(p['x']*.0254,p['y']*.0254);gap=q.distance(both)-p['diameter']*.0254/2;gaps.append(gap)
            assert gap>=.158 and q.distance(ko)>=p['diameter']*.0254/2+.15,(net,'via',gap)
            for old in [v for v in final['vias'] if v['net']!=net]+newvias[:i]:
                assert math.hypot(p['x']-old['x'],p['y']-old['y'])*.0254-(p['hole']+old['hole'])*.0254/2>=.3499
        min_gaps[net]=min(gaps)
        assert connected_subset([p for p in data['pads'] if p['net']==net],[p for p in final['lines'] if p['net']==net],[p for p in final['vias'] if p['net']==net])['complete'],net
    old_lines=[p for p in data['lines'] if p['net']=='BUS_RETURN'];old_vias=[p for p in data['vias'] if p['net']=='BUS_RETURN']
    metrics=dict(before_length_mm=length(old_lines),after_length_mm=length(lines),before_vias=len(old_vias),after_vias=len(vias))
    print('QUALITY',metrics,flush=True)
    assert len(vias)<=len(old_vias) and length(lines)<=length(old_lines)*1.10,'BUS_RETURN quality budget exceeded'
    result.update(bus_lines=lines,bus_vias=vias,bus_quality=metrics,min_foreign_gaps_mm=min_gaps,
                  independent_geometry_pass=True,both_nets_complete=True)
except Exception as e:
    result.update(failure=repr(e))
(OUT/'power-bus-exchange-plan.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
assert sha(PCB)==before
print(json.dumps({k:v for k,v in result.items() if k not in ['additive_power_lines','additive_power_vias','bus_lines','bus_vias']},indent=2),flush=True)
