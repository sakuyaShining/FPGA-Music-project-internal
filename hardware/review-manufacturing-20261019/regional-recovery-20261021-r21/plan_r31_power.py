"""Make a short supply branch by trimming only obstructing control-area ground traces."""
from pathlib import Path
import sys,json,math,hashlib
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,str(BASE))
import exchange
from native_project import PROJECT
from resume_offline import read_native
from shapely.geometry import LineString
from shapely.ops import unary_union
from four_layer_geometry import copper
s=json.loads((BASE/'native-batch-capture.json').read_text());raw=read_native(PROJECT/'pcb/PCB1.epcb2')
s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
p1=next(p for p in s['pads'] if p['ref']=='R31' and p['n']=='1');p2=next(p for p in s['pads'] if p['ref']=='R30' and p['n']=='1')
width=13.2;q=LineString([(p1['x']*.0254,p1['y']*.0254),(p2['x']*.0254,p2['y']*.0254)])
remove=[];retained=[];trimmed_length=0
for p in s['lines']:
    if p['layer']!=1 or p['net']=='3V3_IO':continue
    g=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)])
    if g.distance(q)-(p['width']+width)*.0254/2>=.165:continue
    assert p['net']=='GND','Do not disturb another signal for this supply repair'
    assert all(74<p[k]*.0254<80 for k in ['x1','x2'])
    remove.append(p)
    rest=g.difference(q.buffer((p['width']+width)*.0254/2+.175,quad_segs=32))
    trimmed_length+=g.length-rest.length
    parts=list(rest.geoms) if hasattr(rest,'geoms') else [rest]
    for v in parts:
        if v.is_empty or v.length<.01:continue
        a,z=v.coords[0],v.coords[-1]
        retained.append(dict(net='GND',layer=1,x1=a[0]/.0254,y1=a[1]/.0254,x2=z[0]/.0254,y2=z[1]/.0254,width=p['width']))
power=dict(net='3V3_IO',layer=1,x1=p1['x'],y1=p1['y'],x2=p2['x'],y2=p2['y'],width=width)
work={**s,'lines':[p for p in s['lines'] if p not in remove]+retained+[power]}
f,_=copper(work,'3V3_IO');clear=q.distance(unary_union(f[1]))-width*.0254/2
assert clear>=.165
plan=dict(source_pcb_sha256=hashlib.sha256((PROJECT/'pcb/PCB1.epcb2').read_bytes()).hexdigest(),remove_lines=remove,lines=retained+[power],trimmed_ground_record_length_mm=trimmed_length,new_power_length_mm=q.length,remaining_min_clearance_mm=clear,new_vias=0,manufacturing_release=False,rationale='Retain ground traces outside a 0.175mm clearance corridor. No ground pad or via removed; existing ground pours and original ground planes must be rebuilt and checked for no new ground disconnects.')
(BASE/'r31-power-plan.json').write_text(json.dumps(plan,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in plan.items() if k not in ['remove_lines','lines']},indent=2));print('delete',len(remove),'retained segments',len(retained))
