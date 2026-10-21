"""Four-layer component graph; lower-bound via tree, never a native route."""
from pathlib import Path
import sys, json, hashlib, re, math, heapq
ROOT=Path(__file__).resolve().parent.parent
OUT=Path(__file__).resolve().parent
case=sys.argv[1] if len(sys.argv)>1 else None
if case is not None:
    assert case in ['bounded-local','bounded-medium','power-rework']
    OUT=OUT/case;OUT.mkdir(exist_ok=False)
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union,nearest_points
from shapely.strtree import STRtree
sys.path.insert(0,str(ROOT))
from resume_offline import read_native
from four_layer_geometry import copper,connected
from physical_geometry import actual_pad
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cp=json.loads((ROOT/'ACTIVE-ROUTING-CANDIDATE.json').read_text(encoding='utf-8'))
pcb=Path(cp['project'])/'pcb/PCB1.epcb2'
assert sha(pcb)==cp['pcb_sha256']
s=json.loads((ROOT/cp['source_capture']).read_text(encoding='utf-8'))
raw=read_native(pcb)
s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in raw.items() if k=='VIA']
rework=None
if case=='power-rework':
    bridgefile=ROOT/'offset-power-bridges-20261021-r13/local-bridge-candidates.json'
    data=json.loads(bridgefile.read_text(encoding='utf-8'))
    selected=[r for r in data['representatives'] if r['remove_line_id'] in ['0627c567e9e38694','723148871d7c2e07','86c39d6dad90db80']]
    assert len(selected)==3
    removed={r['remove_line_id'] for r in selected}
    s['lines']=[p for p in s['lines'] if p['id'] not in removed]
    for i,r in enumerate(selected):
        s['lines'] +=[{**q,'id':f'rework-line-{i}-{j}'} for j,q in enumerate(r['lines'])]
        s['vias'] +=[{**q,'id':f'rework-via-{i}-{j}'} for j,q in enumerate(r['vias'])]
    proof=connected([p for p in s['pads'] if p['net']=='3V3_IO'],[p for p in s['lines'] if p['net']=='3V3_IO'],[p for p in s['vias'] if p['net']=='3V3_IO'])
    assert proof['complete'],proof
    rework=dict(source_file=str(bridgefile),source_file_sha256=sha(bridgefile),bridges=selected,power_pad_connectivity=proof)
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
quiet=unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+(.6 if p['net'].startswith('I2S_') else .5),quad_segs=32) for p in s['lines'] if p['layer']==2 and (p['net'].startswith('I2S_') or re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net']))])
board=box(*({'bounded-local':(48,35,90,70),'bounded-medium':(44,31,94,74),'power-rework':(44,31,94,74)}.get(case,(.5,.5,139.5,99.5))))
def polys(q):
    if q.geom_type=='Polygon': yield q
    elif hasattr(q,'geoms'):
        for g in q.geoms: yield from polys(g)
net='HARM_CS_N'
f,allpads=copper(s,net)
obs={l:unary_union(f[l]+[mount]+([quiet] if l==16 else [])) for l in [1,16]}
regions={l:sorted(polys(board.difference(obs[l].buffer(.0762+.1605,quad_segs=32))),key=lambda p:p.area,reverse=True) for l in [1,16]}
trees={l:STRtree(regions[l]) for l in regions}
offset={1:0,16:len(regions[1])}
nodes=[dict(id=offset[l]+i,layer=l,region=i,area_mm2=q.area,bounds_mm=q.bounds) for l in regions for i,q in enumerate(regions[l])]
def where(l,point):
    return next((offset[l]+int(i) for i in trees[l].query(point) if regions[l][int(i)].covers(point)),None)
print('REGIONS', {l:len(v) for l,v in regions.items()},flush=True)
allforeign=unary_union([q for a in f.values() for q in a])
drills=unary_union([Point(p['x']*.0254,p['y']*.0254).buffer((12+p['hole'])*.0254/2+.35,quad_segs=32) for p in s['vias']])
legal=board.difference(allforeign.buffer(.3048+.158,quad_segs=32)).difference(unary_union(allpads).buffer(.1524+.25,quad_segs=32)).difference(drills).difference(quiet.buffer(.3048+.158,quad_segs=32)).difference(mount.buffer(.3048+.15,quad_segs=32))
ports=[]
for p in polys(legal):
    # Stay off exact boundary contacts before choosing an actual circular barrel.
    for q in polys(p.buffer(-.005,quad_segs=24)):
        point=q.representative_point();a,b=where(1,point),where(16,point)
        if a is not None and b is not None:ports.append(dict(a=a,b=b,area_mm2=q.area,geometry=q))
print('LEGAL PORT AREAS',len(ports),flush=True)
edges=[];pairs={}
for i,p in enumerate(ports):pairs.setdefault((p['a'],p['b']),[]).append(i)
for (a,b),indices in pairs.items():edges.append(dict(id=len(edges),a=a,b=b,cost=1,type='new_through_via',port_indices=indices))
pads=[p for p in s['pads'] if p['net']==net]
terms=[]
for p in pads:
    point=Point(p['x']*.0254,p['y']*.0254)
    layers=[1,16] if p['layer']==12 else [p['layer']]
    locations={l:where(l,point) for l in layers}
    assert all(v is not None for v in locations.values()),(p['ref'],p['n'],locations)
    terms.append(dict(ref=p['ref'],pin=p['n'],xy_mm=[point.x,point.y],nodes=locations))
    if len(locations)==2:
        edges.append(dict(id=len(edges),a=locations[1],b=locations[16],cost=0,type='existing_plated_pad',xy_mm=[point.x,point.y],ref=p['ref'],pin=p['n']))
adj={i:[] for i in range(len(nodes))}
for e in edges:
    adj[e['a']].append((e['b'],e['cost'],e['id']));adj[e['b']].append((e['a'],e['cost'],e['id']))
# Exact Steiner dynamic program on the declared region graph (not on full PCB).
n=len(nodes);k=len(terms);dp={};parent={}
for mask in range(1,1<<k):
    dist=[math.inf]*n;prev={}
    if mask&(mask-1)==0:
        t=terms[mask.bit_length()-1]
        for v in t['nodes'].values():dist[v]=0;prev[v]=('terminal',mask.bit_length()-1)
    else:
        sub=(mask-1)&mask
        while sub:
            other=mask^sub
            if other and sub<other:
                for v in range(n):
                    candidate=dp[sub][v]+dp[other][v]
                    if candidate<dist[v]:dist[v]=candidate;prev[v]=('merge',sub,other)
            sub=(sub-1)&mask
    heap=[(d,v) for v,d in enumerate(dist) if math.isfinite(d)];heapq.heapify(heap)
    while heap:
        d,v=heapq.heappop(heap)
        if d!=dist[v]:continue
        for w,cost,eid in adj[v]:
            nd=d+cost
            if nd<dist[w]:dist[w]=nd;prev[w]=('edge',v,eid);heapq.heappush(heap,(nd,w))
    dp[mask]=dist;parent[mask]=prev
mask=(1<<k)-1;goal=min(range(n),key=lambda v:dp[mask][v]);value=dp[mask][goal]
used=set();visited=set()
def walk(mask,v):
    if (mask,v) in visited:return
    visited.add((mask,v));p=parent[mask][v]
    if p[0]=='merge':walk(p[1],v);walk(p[2],v)
    elif p[0]=='edge':used.add(p[2]);walk(mask,p[1])
if math.isfinite(value):walk(mask,goal)
selected=[edges[i] for i in sorted(used)]
center=Point(sum(p['x']*.0254 for p in pads)/len(pads),sum(p['y']*.0254 for p in pads)/len(pads))
for e in selected:
    if e['type']=='new_through_via':
        candidates=[]
        for idx in e['port_indices']:
            q=ports[idx]['geometry'];pt=nearest_points(center,q)[1]
            candidates.append((pt.distance(center),idx,pt))
        _,idx,pt=min(candidates,key=lambda x:x[0]);e['representative_port_index']=idx;e['candidate_xy_mm']=[pt.x,pt.y]
report=dict(source_pcb_sha256=cp['pcb_sha256'],net=net,layers_used=[1,16],native_imported=False,manufacturing_release=False,
            routing_bounds_mm=list(board.bounds),case=case,
            power_rework=rework,
            design_complexity=dict(level='intermediate',triggers=['multiple power rails','high impedance84-electrode sensing','FPGA and display interfaces'],unverified=['actual edge rates','sensing parasitics','factory stack approval']),
            nodes=nodes,edges=edges,terminals=terms,selected_edges=selected,
            minimum_new_vias_in_component_graph=None if not math.isfinite(value) else value,
            engineering_target_max_new_vias=6,
            limitations=['Graph omits route length and inter-new-via drill clearance; geometric realization still required.',
                         'Existing foreign copper, sensing/audio projection guards and all-layer via eligibility retained.',
                         'Buffers approximate circles; no native DRC, real plane rebuild, return signoff or physical measurements performed.'])
(OUT/'graph.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
geoms=dict(regions={str(l):[q.wkb_hex for q in regions[l]] for l in regions},ports=[{**{k:v for k,v in p.items() if k!='geometry'},'wkb':p['geometry'].wkb_hex} for p in ports],obstacles={str(l):q.wkb_hex for l,q in obs.items()})
(OUT/'geometry.json').write_text(json.dumps(geoms),encoding='utf-8')
assert sha(pcb)==cp['pcb_sha256']
print('GRAPH MINIMUM NEW VIAS',value,'selected',[(e['type'],e.get('candidate_xy_mm',e.get('xy_mm'))) for e in selected],flush=True)
