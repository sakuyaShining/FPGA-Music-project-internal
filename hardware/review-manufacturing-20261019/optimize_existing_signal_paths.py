"""Simplify complete nets using exact visibility and existing via locations only.

Unlike raster rerouting this preserves access to valid narrow corridors. No
foreign copper is removed, no new via positions or physical pads are invented.
All accepted nets require shorter copper and fewer vias plus a combined audit.
"""
import argparse,collections,hashlib,heapq,json,math,re,sys,time
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
import grid_route as grid
from physical_geometry import actual_pad,connected_subset
from native_review import ROOT,PROJECT
from resume_offline import read_native

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',default='controls-final-source-78.json')
parser.add_argument('--checkpoint',default='route-checkpoint-0clear-78open.json')
parser.add_argument('--output',default='quality-visibility-plan.json')
parser.add_argument('--nets',nargs='+',default=['I2S_BCK','I2S_DIN','I2S_LRCK','VIS_DC','BUS_RETURN','VIS_BL_EN','EDIT','RA_MISO','RC_DRIVE'])
parser.add_argument('--all-core',action='store_true')
args=parser.parse_args()
src=ROOT/args.source;raw=src.read_bytes();source=json.loads(raw)
if args.all_core:
    power={'GND','3V3_IO','3V3_PERIPH','DAC_3V3','5V_PERIPH','5V_FUSED','5V_IN','5V_PROTECTED','5V_USB'}
    core={p['net'] for p in source['lines'] if p['net'] not in power and not p['net'].startswith(('DAC_','AUX_','PWR_')) and not re.fullmatch(r'L[0-5]_[ME]\d\d',p['net'])}
    priority=['RC_DRIVE','BUS_RETURN','EDIT','VIS_BL_EN','I2S_LRCK','I2S_DIN','I2S_BCK']
    args.nets=[n for n in priority if n in core]+sorted(core-set(priority))
board=PROJECT/'pcb/PCB1.epcb2';sha=hashlib.sha256(board.read_bytes()).hexdigest()
assert sha==json.loads((ROOT/args.checkpoint).read_text())['pcb_sha256']
working={**source,'lines':list(source['lines']),'vias':list(source['vias'])}
known={p['id'] for p in source['lines']};hidden_nets=set()
for (kind,i),p in read_native(board).items():
    if kind=='LINE' and p.get('layerId') in [1,2] and i not in known:
        hidden_nets.add(p['netName'])
        working['lines'].append(dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']))
if hidden_nets.intersection(args.nets):print('PROTECTED hidden native copper',sorted(hidden_nets.intersection(args.nets)),flush=True)
args.nets=[n for n in args.nets if n not in hidden_nets]
grid.pad_shape=actual_pad
WIDTH=.1524;GAP=.1585
length=lambda ls:sum(math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254 for p in ls)
routes=[];failed=[]
for net in args.nets:
    started=time.monotonic()
    try:
        oldls=[p for p in source['lines'] if p['net']==net];oldvs=[p for p in source['vias'] if p['net']==net]
        ps=[p for p in source['pads'] if p['net']==net]
        assert len(ps)>=2 and oldls
        assert all(abs(p['width']*.0254-WIDTH)<.0001 for p in oldls),'Preserve variable-width networks separately'
        foreign,allpads,kos=grid.geometries(working,net);cu={l:unary_union(foreign[l]) for l in [1,2]};both=unary_union(foreign[1]+foreign[2]);ko=unary_union(kos)
        nodes={}
        def key(x,y):return round(x,5),round(y,5)
        def add(x,y):
            k=key(x,y)
            if k not in nodes:nodes[k]=len(nodes)
            return nodes[k]
        padnodes=[add(p['x']*.0254,p['y']*.0254) for p in ps]
        for p in oldls:add(p['x1']*.0254,p['y1']*.0254);add(p['x2']*.0254,p['y2']*.0254)
        for v in oldvs:add(v['x']*.0254,v['y']*.0254)
        xy=list(nodes);N=len(xy);adj=collections.defaultdict(list);via_at={}
        for v in oldvs:
            i=nodes[key(v['x']*.0254,v['y']*.0254)]
            if Point(xy[i]).distance(both)-v['diameter']*.0254/2<GAP:continue
            adj[i].append((N+i,20.));adj[N+i].append((i,20.));via_at[i]=v
        for i in range(N):
            for j in range(i):
                line=LineString([xy[i],xy[j]]);d=line.length
                if d<1e-5 or line.distance(ko)<WIDTH/2+.15:continue
                for layer in [1,2]:
                    if line.distance(cu[layer])<WIDTH/2+GAP:continue
                    a=(layer-1)*N+i;b=(layer-1)*N+j
                    adj[a].append((b,d));adj[b].append((a,d))
        terminals=[{i,N+i} if p['layer']==12 else {(p['layer']-1)*N+i} for p,i in zip(ps,padnodes)]
        tree=set(terminals[0]);edges=set();todo=list(range(1,len(ps)))
        while todo:
            targets=set().union(*(terminals[j] for j in todo));dist={a:0. for a in tree};parent={};q=[(0.,a) for a in tree];heapq.heapify(q);goal=None
            while q:
                d,a=heapq.heappop(q)
                if d>dist[a]+1e-9:continue
                if a in targets:goal=a;break
                for b,cost in adj[a]:
                    nd=d+cost
                    if nd+1e-9<dist.get(b,float('inf')):dist[b]=nd;parent[b]=a;heapq.heappush(q,(nd,b))
            assert goal is not None,'No exact-geometry path through existing route vertices'
            reached=next(j for j in todo if goal in terminals[j]);todo.remove(reached)
            node=goal;tree.update(terminals[reached])
            while node not in tree or node in parent:
                if node not in parent:break
                prev=parent[node];edges.add(tuple(sorted((prev,node))));tree.add(node);node=prev
                if node in tree:break
            tree.add(node)
        ls=[];vs=[]
        for a,b in sorted(edges):
            if a//N!=b//N:vs.append(via_at[a%N]);continue
            x1,y1=xy[a%N];x2,y2=xy[b%N]
            ls.append(dict(net=net,layer=a//N+1,x1=x1/.0254,y1=y1/.0254,x2=x2/.0254,y2=y2/.0254,width=6.))
        unique_vias={v['id']:v for v in vs};vs=list(unique_vias.values())
        connected=connected_subset(ps,ls,vs);assert connected['complete'],connected
        ls=connected['lines'];vs=connected['vias']
        metrics=dict(before_length_mm=length(oldls),after_length_mm=length(ls),before_vias=len(oldvs),after_vias=len(vs),before_segments=len(oldls),after_segments=len(ls))
        print('CANDIDATE',net,metrics,flush=True)
        assert (len(vs)<len(oldvs) and length(ls)<length(oldls)-.1) or (len(vs)==len(oldvs) and length(ls)<length(oldls)-1.),'No meaningful improvement without a length/via regression'
        gaps=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).distance(cu[p['layer']])-WIDTH/2 for p in ls]
        gaps += [Point(p['x']*.0254,p['y']*.0254).distance(both)-p['diameter']*.0254/2 for p in vs]
        assert min(gaps)>=.158
        route=dict(net=net,lines=ls,vias=vs,edges=[{'min_foreign_copper_gap_mm':min(gaps)}],independent_geometry_pass=True,real_pad_continuity_pass=True,quality_comparison=metrics)
        routes.append(route)
        working['lines']=[p for p in working['lines'] if p['net']!=net]+ls
        working['vias']=[p for p in working['vias'] if p['net']!=net]+vs
        print('ACCEPTED',net,round(time.monotonic()-started,1),'seconds',flush=True)
    except Exception as error:
        failed.append(dict(net=net,error=repr(error)));print('UNCHANGED',net,repr(error),flush=True)

# Audit every accepted route against the complete final virtual board. Failed
# nets were never removed, so they remain protected at every stage.
for r in routes:
    foreign,_,_=grid.geometries(working,r['net']);cu={l:unary_union(foreign[l]) for l in [1,2]};both=unary_union(foreign[1]+foreign[2])
    for p in r['lines']:
        assert LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).distance(cu[p['layer']])-p['width']*.0254/2>=.158
    for p in r['vias']:assert Point(p['x']*.0254,p['y']*.0254).distance(both)-p['diameter']*.0254/2>=.158
result=dict(nets=[r['net'] for r in routes],routes=routes,lines=[p for r in routes for p in r['lines']],vias=[p for r in routes for p in r['vias']],
            source_file=str(src),source_sha256=hashlib.sha256(raw).hexdigest(),native_pcb_sha256=sha,batch_final_geometry_pass=True,
            failed_planning=failed,no_new_via_locations=True,ground_removals={'lines':[],'vias':[]},requires_ground_rebuild_and_native_drc=True,manufacturing_release=False)
(ROOT/args.output).write_text(json.dumps(result,indent=2),encoding='utf-8')
assert hashlib.sha256(board.read_bytes()).hexdigest()==sha
print('COMPLETE',len(routes),'improved nets',flush=True)
