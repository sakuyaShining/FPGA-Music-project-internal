"""Length-bounded two-via INV2 fanout using true free-space holes, never minimum-via-only routing."""
from pathlib import Path
import sys,json,math,re,hashlib
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,str(ROOT/'inv2-comparison-20261021-r16'))
from exchange import read
from four_layer_geometry import copper,connected
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
from shapely.strtree import STRtree
sys.path.insert(0,str(ROOT/'control-closure-20261021-r8'))
from mesh_fanout import route as mesh_route
cp,pcb,s=read();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert cp['pcb_sha256']=='5029ca7091053a207a08908edfbe4b2716058640fa654b720c08c2bc0333cacb'
assert not [p for p in s['lines'] if p['net']=='INV2']
target=next(p for p in s['lines'] if p['id']=='bb69c07a4390ff26')
assert target['net']=='3V3_PERIPH' and target['layer']==1 and target['width']==15.74
original_y=target['y1']*.0254
assert abs(target['y1']-target['y2'])<1e-7
left=min(target['x1'],target['x2'])*.0254;right=max(target['x1'],target['x2'])*.0254
# Reserve an explicit prospective U7.6 fanout rather than moving power blindly.
u7=next(p for p in s['pads'] if p['ref']=='U7' and p['n']=='6')
reserve_xy=(u7['x']*.0254,u7['y']*.0254-1.3)
reserve=unary_union([Point(reserve_xy).buffer(.3048,quad_segs=32),LineString([(u7['x']*.0254,u7['y']*.0254),reserve_xy]).buffer(.0762,quad_segs=32)])
powerforeign=unary_union(copper(s,'3V3_PERIPH')[0][1]+[reserve])
powercandidates=[];screened=0
for ia in range(9):
 for ih in range(10):
  for ic in range(8):
   x=53.4+ia*.1;h=.8+ih*.15;c=56.2+ic*.15
   if x+h>=c:continue
   points=[(left,original_y),(x,original_y),(x+h,original_y-h),(c,original_y-h),(c+h,original_y),(right,original_y)]
   gap=min(LineString([a,b]).distance(powerforeign)-target['width']*.0254/2 for a,b in zip(points,points[1:]))
   screened+=1
   if gap>=.165:powercandidates.append(dict(points=points,gap=gap,delta=sum(math.dist(a,b) for a,b in zip(points,points[1:]))-(right-left)))
(OUT/'power-pocket-screen.json').write_text(json.dumps(dict(source_pcb_sha256=cp['pcb_sha256'],screened=screened,accepted=len(powercandidates),prospective_U7_via_mm=reserve_xy,original_width_mil=target['width'],initial_rejected_variant='0.8mm offset hit existing VIS_DC via and approached C7 GND pad; no native change',candidates=powercandidates),indent=2),encoding='utf8')
assert powercandidates,'No full-width local power pocket clears existing copper and prospective INV2 via'
choice=min(powercandidates,key=lambda p:p['delta']);powerpoints=choice['points'];powergap=choice['gap']
powerlines=[dict(net='3V3_PERIPH',layer=1,x1=a[0]/.0254,y1=a[1]/.0254,x2=b[0]/.0254,y2=b[1]/.0254,width=target['width']) for a,b in zip(powerpoints,powerpoints[1:])]
s['lines']=[p for p in s['lines'] if p['id']!=target['id']]+powerlines
proof=connected([p for p in s['pads'] if p['net']=='3V3_PERIPH'],[p for p in s['lines'] if p['net']=='3V3_PERIPH'],[p for p in s['vias'] if p['net']=='3V3_PERIPH'])
assert proof['complete'],proof
power_delta=sum(math.dist(a,b) for a,b in zip(powerpoints,powerpoints[1:]))-(right-left)
f,padshapes=copper(s,'INV2');foreign={l:unary_union(q) for l,q in f.items()};foreignall=unary_union(list(foreign.values()));pads=unary_union(padshapes)
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
quiet=unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+(.6 if p['net'].startswith('I2S_') else .5),quad_segs=32) for p in s['lines'] if p['layer']==2 and (p['net'].startswith('I2S_') or re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net']))])
obstacles={1:unary_union([foreign[1],mount]),16:unary_union([foreign[16],mount,quiet])}
bounds=(37,39,61,56);free=box(*bounds).difference(obstacles[16].buffer(.0762+.165,quad_segs=32))
regions=[free] if free.geom_type=='Polygon' else [p for p in free.geoms if p.geom_type=='Polygon'];tree=STRtree(regions)
def where(q):return next((int(i) for i in tree.query(q) if regions[int(i)].covers(q)),None)
terminals=[p for p in s['pads'] if p['net']=='INV2'];candidates=[]
for term in terminals:
    xy=(term['x']*.0254,term['y']*.0254);points=[]
    for k in range(8):
        dx,dy=math.cos(k*math.pi/4),math.sin(k*math.pi/4)
        for ir in range(7,51):
            r=ir*.1;v=(xy[0]+r*dx,xy[1]+r*dy);q=Point(v)
            region=where(q)
            if region is None:continue
            if q.distance(foreignall)-.3048<.165 or q.distance(pads)-.1524<.25:continue
            if q.distance(quiet)-.3048<.165 or q.distance(mount)-.3048<.15:continue
            if any(math.dist(v,(o['x']*.0254,o['y']*.0254))-(12+o['hole'])*.0254/2<.35 for o in s['vias']):continue
            direct=LineString([xy,v])
            if direct.distance(obstacles[1])<.0762+.165:continue
            points.append(dict(xy_mm=v,region=region,top_length_mm=r))
    candidates.append(points)
    print('TERMINAL',term['ref'],term['n'],'candidates',len(points),'regions',sorted({p['region'] for p in points}),flush=True)
pairs=[]
for a in candidates[0]:
    for b in candidates[1]:
        if a['region']!=b['region']:continue
        lower=a['top_length_mm']+b['top_length_mm']+math.dist(a['xy_mm'],b['xy_mm'])
        if lower<=30:pairs.append((lower,a,b))
pairs.sort(key=lambda q:q[0]);trials=[];best=None
for lower,a,b in pairs[:8]:
    print('PAIR LOWER',lower,a['xy_mm'],b['xy_mm'],flush=True)
    direct=LineString([a['xy_mm'],b['xy_mm']])
    try:path=[a['xy_mm'],b['xy_mm']] if regions[a['region']].covers(direct) else mesh_route(a['xy_mm'],b['xy_mm'],obstacles[16],bounds)
    except AssertionError as e:trials.append(dict(lower_bound_mm=lower,failure=str(e)));continue
    total=a['top_length_mm']+b['top_length_mm']+sum(math.dist(u,v) for u,v in zip(path,path[1:]));trials.append(dict(lower_bound_mm=lower,length_mm=total))
    if best is None or total<best['length_mm']:best=dict(a=a,b=b,path=path,length_mm=total)
    if total<=20:break
status=dict(source_pcb_sha256=cp['pcb_sha256'],method='Two direct octilinear top fanouts and true-hole constrained-triangle inner16 path within a24x17mm local window; evaluate actual total length.',source_files=cp['files'],terminal_candidates=[len(p) for p in candidates],shared_inner_region_pairs=len(pairs),trials=trials,maximum_signal_vias=2,maximum_summed_length_mm=30,power_rework=dict(remove_line_id=target['id'],replacement_lines=powerlines,original_width_mil=target['width'],added_power_length_mm=power_delta,minimum_copper_gap_mm=powergap,continuity=proof,new_power_vias=0),native_imported=False,manufacturing_release=False)
if best and best['length_mm']<=30:
    lines=[];vias=[]
    def add(layer,points):
        for a,b in zip(points,points[1:]):
            if math.dist(a,b)>1e-7:lines.append(dict(net='INV2',layer=layer,x1=a[0]/.0254,y1=a[1]/.0254,x2=b[0]/.0254,y2=b[1]/.0254,width=6))
    for t,p in zip(terminals,[best['a'],best['b']]):
        add(1,[(t['x']*.0254,t['y']*.0254),p['xy_mm']]);vias.append(dict(net='INV2',x=p['xy_mm'][0]/.0254,y=p['xy_mm'][1]/.0254,diameter=24,hole=12))
    add(16,best['path']);continuity=connected(terminals,lines,vias);assert continuity['complete']
    mintrack=min(LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).distance(obstacles[p['layer']])-.0762 for p in lines)
    assert mintrack>=.158
    status.update(outcome='geometric_candidate',lines=lines,vias=vias,length_mm=best['length_mm'],continuity=continuity,min_track_edge_including_quiet_mm=mintrack,requires_native_drc_reference_and_copper_identity=True)
else:status.update(outcome='no_acceptable_two_via_local_candidate',next_step='Inspect legal terminal via escape regions or coordinate neighboring routes; no unchanged router rerun and no blanket extra layers.')
assert sha(pcb)==cp['pcb_sha256']
(OUT/'plan.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in status.items() if k not in ['lines','source_files']},indent=2),flush=True)
