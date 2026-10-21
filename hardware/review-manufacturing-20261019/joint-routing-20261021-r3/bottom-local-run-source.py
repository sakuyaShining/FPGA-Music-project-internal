"""Keep BUS_RETURN trunks; replace only the short segment blocking U17 supply."""
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
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
PCB=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019/pcb/PCB1.epcb2')
SRC=ROOT/'quality-r1-source-78.json';before=sha(PCB)
assert before=='be576cabac058fc0754fbc87a07565e69531e59c7d249a6f6d267c5f93c5fc3e'
d=read(SRC);native=read_native(PCB)
for p in d['vias']:
    n=native['VIA',p['id']];p['diameter']=n['viaDiameter'];p['hole']=n['holeDiameter']
ids={p['id'] for p in d['lines']}
for (k,i),p in native.items():
    if k=='LINE' and p.get('layerId') in [1,2] and i not in ids:
        d['lines'].append(dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']))
remove=[p for p in d['lines'] if p['net']=='BUS_RETURN' and p['layer']==1 and
    ((abs(p['x1']*.0254-23.7)<.001 and abs(p['y1']*.0254-51.45)<.001) or
     (abs(p['x2']*.0254-23.7)<.001 and abs(p['y2']*.0254-51.45)<.001))]
assert len(remove)==2
removed_ids={p['id'] for p in remove}
branch=read(OUT/'dac-power-branch-plan.json');power=read(OUT/'power-bus-return-unblocked/power-plan.json')
assert branch['route_found'] and power['all_pad_groups_connected'] and not power['vias']
power_lines=branch['lines']+power['lines']
working={**d,'lines':[p for p in d['lines'] if p['id'] not in removed_ids]+power_lines}
grid.pad_shape=actual_pad;grid.WIDTH=.1524;grid.GAP=.17;grid.GRID=.05
rr=grid.raster;grid.raster=lambda gs,b,i,s:rr(gs,b,i+grid.GRID/math.sqrt(2),s)
geo=grid.geometries
def bottom_only(data,net):
    f,p,k=geo(data,net);f[1].append(box(-1,-1,141,101));return f,p,k
grid.geometries=bottom_only
anchors=[]
for x,y in [(24.525,52.275),(23.625,48.075)]:
    via=min([p for p in d['vias'] if p['net']=='BUS_RETURN'],key=lambda p:math.hypot(p['x']*.0254-x,p['y']*.0254-y))
    assert math.hypot(via['x']*.0254-x,via['y']*.0254-y)<.001
    anchors.append(dict(id='anchor-'+via['id'],ref='EXISTING_BUS_VIA',n='',net='BUS_RETURN',layer=2,
        x=via['x'],y=via['y'],rotation=0,shape=['ELLIPSE',via['diameter'],via['diameter']]))
route=None
for margin in [3,6,12]:
    try:route=grid.search(working,'BUS_RETURN',anchors[0],anchors[1],margin)
    except grid.SealedEscape:break
    if route:break
grid.geometries=geo
result=dict(source_file=str(SRC),source_sha256=sha(SRC),native_pcb_sha256=before,
    remove_line_ids=sorted(removed_ids),removed_lines=remove,additive_power_lines=power_lines,
    bus_lines=[],bus_vias=[],both_nets_complete=False,independent_geometry_pass=False,
    native_imported=False,manufacturing_release=False,
    dependency_sha256={n:sha(OUT/n) for n in ['dac-power-branch-plan.json','power-bus-return-unblocked/power-plan.json']})
length=lambda ls:sum(math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254 for p in ls)
if route:
    try:
        assert not route['vias'] and all(p['layer']==2 for p in route['lines'])
        final={**working,'lines':working['lines']+route['lines']}
        gaps={}
        for net,lines in [('BUS_RETURN',route['lines']),('5V_PERIPH',power_lines)]:
            f,_,k=geo(final,net);cu={l:unary_union(f[l]) for l in [1,2]};ko=unary_union(k);gs=[]
            for p in lines:
                q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)])
                gap=q.distance(cu[p['layer']])-p['width']*.0254/2;gs.append(gap)
                assert gap>=.158 and q.distance(ko)>=p['width']*.0254/2+.15,(net,gap)
            gaps[net]=min(gs)
            conn=connected_subset([p for p in d['pads'] if p['net']==net],[p for p in final['lines'] if p['net']==net],[p for p in final['vias'] if p['net']==net])
            assert conn['complete'],(net,conn)
        old_bus=[p for p in d['lines'] if p['net']=='BUS_RETURN'];new_bus=[p for p in final['lines'] if p['net']=='BUS_RETURN']
        metrics=dict(before_length_mm=length(old_bus),after_length_mm=length(new_bus),
            removed_local_length_mm=length(remove),added_local_length_mm=length(route['lines']),
            vias_before=7,vias_after=7,new_vias=0)
        assert metrics['after_length_mm']<=metrics['before_length_mm']*1.10,'Local BUS_RETURN budget exceeded'
        result.update(bus_lines=route['lines'],bus_quality=metrics,min_foreign_gaps_mm=gaps,
            both_nets_complete=True,independent_geometry_pass=True)
    except Exception as e:result['failure']=repr(e)
else:result['failure']='No bottom-only local path'
(OUT/'local-power-bus-exchange-plan.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
assert sha(PCB)==before
print(json.dumps({k:v for k,v in result.items() if k not in ['removed_lines','bus_lines','additive_power_lines']},indent=2))
