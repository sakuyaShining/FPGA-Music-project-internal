"""Diagnostic only: identify which existing top nets separate HARM terminals."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
sys.path.insert(0,str(ROOT))
from four_layer_geometry import copper
from resume_offline import read_native
from physical_geometry import actual_pad
cp=json.loads((ROOT/'ACTIVE-ROUTING-CANDIDATE.json').read_text(encoding='utf-8'))
pcb=Path(cp['project'])/'pcb/PCB1.epcb2';assert hashlib.sha256(pcb.read_bytes()).hexdigest()==cp['pcb_sha256']
s=json.loads((ROOT/cp['source_capture']).read_text(encoding='utf-8'));raw=read_native(pcb)
lines=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId')==1 and p['netName']!='HARM_CS_N']
fixed=[actual_pad(p) for p in s['pads'] if p['net']!='HARM_CS_N' and p['layer'] in [1,12]]
fixed +=[Point(p['centerX']*.0254,p['centerY']*.0254).buffer(p['viaDiameter']*.0254/2,quad_segs=32) for (k,i),p in raw.items() if k=='VIA' and p['netName']!='HARM_CS_N']
shapes=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,quad_segs=32) for p in lines]
padlist=[p for p in s['pads'] if p['net']=='HARM_CS_N'];pts=[Point(p['x']*.0254,p['y']*.0254) for p in padlist]
def polys(q):
    if q.geom_type=='Polygon':yield q
    elif hasattr(q,'geoms'):
        for p in q.geoms:yield from polys(p)
def regions_without(nets):
    obstacle=unary_union(fixed+[q for p,q in zip(lines,shapes) if p['net'] not in nets])
    return sorted(polys(box(.5,.5,139.5,99.5).difference(obstacle.buffer(.2367,quad_segs=32))),key=lambda p:p.area,reverse=True)
original=regions_without(set());rows=[]
for pt,p in zip(pts,padlist):
    po=next(q for q in original if q.covers(pt))
    contacts=[]
    for line,shape in zip(lines,shapes):
        length=po.boundary.intersection(shape.buffer(.23675,quad_segs=32)).length
        if length>.01:contacts.append(dict(id=line['id'],net=line['net'],boundary_contact_mm=length,xy_mm=[line['x1']*.0254,line['y1']*.0254,line['x2']*.0254,line['y2']*.0254]))
    rows.append(dict(ref=p['ref'],pin=p['n'],region_area_mm2=po.area,boundary_lines=sorted(contacts,key=lambda p:p['boundary_contact_mm'],reverse=True)))
candidates=[[],['GND'],['3V3_IO'],['3V3_PERIPH'],['GND','3V3_IO','3V3_PERIPH','5V_PERIPH']]
near_nets=sorted({r['net'] for row in rows for r in row['boundary_lines']})
candidates += [[net] for net in near_nets if net not in ['GND','3V3_IO','3V3_PERIPH']]
results=[]
for removed in candidates:
    parts=regions_without(set(removed));ids=[next((i for i,q in enumerate(parts) if q.covers(p)),None) for p in pts]
    result=dict(diagnostic_removed_top_line_nets=removed,terminal_regions=ids,distinct_terminal_regions=len(set(ids)),removed_line_count=sum(p['net'] in removed for p in lines))
    results.append(result);print(result,flush=True)
(OUT/'top-barrier-probe.json').write_text(json.dumps(dict(source_pcb_sha256=cp['pcb_sha256'],native_imported=False,not_a_removal_plan=True,terminals=rows,cases=results),indent=2)+'\n',encoding='utf-8')
