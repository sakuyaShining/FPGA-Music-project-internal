"""Realize stored region graph ports as copper, retaining original obstacles."""
from pathlib import Path
import sys,json,math,hashlib
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
if len(sys.argv)>1:
    assert sys.argv[1] in ['bounded-local','bounded-medium','power-rework']
    OUT=OUT/sys.argv[1]
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'control-closure-20261021-r8'))
from four_layer_geometry import copper,connected
from physical_geometry import actual_pad
from resume_offline import read_native
from mesh_fanout import route as mesh_route
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cp=json.loads((ROOT/'ACTIVE-ROUTING-CANDIDATE.json').read_text(encoding='utf-8'))
pcb=Path(cp['project'])/'pcb/PCB1.epcb2';assert sha(pcb)==cp['pcb_sha256']
graph=json.loads((OUT/'graph.json').read_text(encoding='utf-8'));assert graph['source_pcb_sha256']==cp['pcb_sha256']
geo=json.loads((OUT/'geometry.json').read_text(encoding='utf-8'))
regions={int(l):[shapely.from_wkb(h) for h in qs] for l,qs in geo['regions'].items()}
obstacles={int(l):shapely.from_wkb(h) for l,h in geo['obstacles'].items()}
s=json.loads((ROOT/cp['source_capture']).read_text(encoding='utf-8'));raw=read_native(pcb)
s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in raw.items() if k=='VIA']
if graph.get('power_rework'):
    removed={r['remove_line_id'] for r in graph['power_rework']['bridges']}
    s['lines']=[p for p in s['lines'] if p['id'] not in removed]
    for r in graph['power_rework']['bridges']:
        s['lines']+=r['lines'];s['vias']+=r['vias']
net=graph['net'];vias=[];per_node={};via_points=[]
def add(node,xy):
    if xy not in per_node.setdefault(node,[]):per_node[node].append(xy)
for e in graph['selected_edges']:
    xy=e.get('candidate_xy_mm',e.get('xy_mm'))
    add(e['a'],xy);add(e['b'],xy)
    if e['type']=='new_through_via':vias.append(dict(net=net,x=xy[0]/.0254,y=xy[1]/.0254,diameter=24,hole=12));via_points.append(xy)
for t in graph['terminals']:
    for node in t['nodes'].values():add(node,t['xy_mm'])
lines=[];paths=[]
for node,points in per_node.items():
    layer=graph['nodes'][node]['layer'];region=regions[layer][graph['nodes'][node]['region']]
    assert all(region.covers(Point(p)) for p in points),(node,points)
    used={0}
    while len(used)<len(points):
        _,a,b=min((math.dist(points[a],points[b]),a,b) for a in used for b in range(len(points)) if b not in used)
        direct=LineString([points[a],points[b]])
        if region.covers(direct):path=[points[a],points[b]]
        else:path=mesh_route(points[a],points[b],obstacles[layer],tuple(graph.get('routing_bounds_mm',(.5,.5,139.5,99.5))))
        length=sum(math.dist(a,b) for a,b in zip(path,path[1:]));paths.append(dict(node=node,layer=layer,points=path,length_mm=length))
        for u,v in zip(path,path[1:]):lines.append(dict(net=net,layer=layer,x1=u[0]/.0254,y1=u[1]/.0254,x2=v[0]/.0254,y2=v[1]/.0254,width=6))
        used.add(b)
        print('PATH',node,layer,length,flush=True)
f,pad_shapes=copper(s,net);foreign=unary_union([q for qs in f.values() for q in qs]);allpads=unary_union(pad_shapes)
min_track=min(LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).distance(obstacles[p['layer']])-.0762 for p in lines)
min_via=min(Point(p['x']*.0254,p['y']*.0254).distance(foreign)-.3048 for p in vias)
min_hole_pad=min(Point(p['x']*.0254,p['y']*.0254).distance(allpads)-.1524 for p in vias)
min_hole_existing=min(math.dist((p['x'],p['y']),(q['x'],q['y']))*.0254-(p['hole']+q['hole'])*.0254/2 for p in vias for q in s['vias'])
min_hole_new=min(math.dist(a,b)-.3048 for i,a in enumerate(via_points) for b in via_points[:i])
assert min_track>=.158-1e-8,min_track
assert min_via>=.158-1e-8,min_via
assert min_hole_pad>=.25-1e-8,min_hole_pad
assert min_hole_existing>=.35-1e-8,min_hole_existing
assert min_hole_new>=.35-1e-8,min_hole_new
continuity=connected([p for p in s['pads'] if p['net']==net],lines,vias);assert continuity['complete'],continuity
length=sum(p['length_mm'] for p in paths)
report=dict(source_pcb_sha256=cp['pcb_sha256'],net=net,lines=lines,vias=vias,paths=paths,length_mm=length,
            power_rework=graph.get('power_rework'),
            new_via_count=len(vias),continuity=continuity,native_imported=False,manufacturing_release=False,
            engineering_original_six_via_target_met=len(vias)<=6,
            min_edge_clearances_mm=dict(track_including_quiet=min_track,via_foreign_copper=min_via,hole_pad=min_hole_pad,hole_existing_drill=min_hole_existing,hole_new_drill=min_hole_new),
            limitations=['Geometric candidate only; requires native DRC/pour rebuild/save/reopen and real reference-plane checks.',
                         'Summed segment length includes any shared branches; not a unique copper-length optimum.'])
(OUT/'candidate.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
assert sha(pcb)==cp['pcb_sha256'];print('CANDIDATE',len(vias),length,report['min_edge_clearances_mm'],flush=True)
