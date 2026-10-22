"""Local two-layer routing trial on actual native pads/copper, with DRC margins.

Ground pours are regenerated after routing. This planner treats every foreign
pad, track, via and mounting keepout as an obstacle. A continuous geometry check
independent of the raster search rejects insufficient clearance before import.
"""
import heapq
import json
import math
import sys
import time
from collections import deque
from pathlib import Path
sys.path.insert(0,'D:/FPGA-Project/codex-tools/shapely')
import numpy as np
from PIL import Image,ImageDraw
from shapely.geometry import box,Point,LineString,GeometryCollection
from shapely.affinity import rotate
from shapely.ops import unary_union
from native_review import ROOT,PROJECT,invoke

MM=.0254
GRID=.025
# Use the unchanged native 6 mil signal minimum; retain extra clearance margin.
WIDTH=.1524
GAP=.18
VIA_D=.6096
VIA_H=.3048
# None preserves the historical 50-grid-step penalty. Quality-focused trials
# can specify a physical cost so changing raster resolution does not make vias
# cheaper relative to trace length.
VIA_COST_MM=None
SEARCH_MARGINS=[4,10,22,50]

class SealedEscape(RuntimeError):
    pass

def capture():
    return invoke('grid-capture-'+str(time.time_ns()),"""
const pads=[],seen=new Set();for(const c of await eda.pcb_PrimitiveComponent.getAll())for(const p of await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId())){seen.add(p.getState_PrimitiveId());pads.push({id:p.getState_PrimitiveId(),ref:c.getState_Designator(),n:p.getState_PadNumber(),net:p.getState_Net(),layer:p.getState_Layer(),x:p.getState_X(),y:p.getState_Y(),rotation:p.getState_Rotation(),shape:p.getState_Pad()});}
for(const p of await eda.pcb_PrimitivePad.getAll())if(!seen.has(p.getState_PrimitiveId()))pads.push({id:p.getState_PrimitiveId(),ref:p.getState_PadNumber(),n:p.getState_PadNumber(),net:p.getState_Net(),layer:p.getState_Layer(),x:p.getState_X(),y:p.getState_Y(),rotation:p.getState_Rotation(),shape:p.getState_Pad()});
return {pads,lines:(await eda.pcb_PrimitiveLine.getAll()).map(p=>({id:p.getState_PrimitiveId(),net:p.getState_Net(),layer:p.getState_Layer(),x1:p.getState_StartX(),y1:p.getState_StartY(),x2:p.getState_EndX(),y2:p.getState_EndY(),width:p.getState_LineWidth()})),vias:(await eda.pcb_PrimitiveVia.getAll()).map(p=>({id:p.getState_PrimitiveId(),net:p.getState_Net(),x:p.getState_X(),y:p.getState_Y(),diameter:p.getState_Diameter(),hole:p.getState_HoleDiameter()}))};
""",timeout=180)

def pad_shape(p):
    x,y=p['x']*MM,p['y']*MM;w,h=p['shape'][1]*MM,p['shape'][2]*MM
    # Bounding rectangles are deliberately conservative for rounded/oval pads.
    return rotate(box(x-w/2,y-h/2,x+w/2,y+h/2),p['rotation'],origin=(x,y))

def geometries(data,net):
    foreign={1:[],2:[]};allpads=[]
    for p in data['pads']:
        # Virtual anchors are not physical pads; their actual round via is
        # already represented below. Square anchor boxes falsely seal gaps.
        if p['id'].startswith('anchor-'):continue
        shape=pad_shape(p);allpads.append(shape)
        if p['net']==net:continue
        for layer in ([1,2] if p['layer']==12 else [p['layer']]):
            if layer in foreign:foreign[layer].append(shape)
    for p in data['lines']:
        if p['net']!=net and p['layer'] in foreign:
            foreign[p['layer']].append(LineString([(p['x1']*MM,p['y1']*MM),(p['x2']*MM,p['y2']*MM)]).buffer(p['width']*MM/2,resolution=12))
    for p in data['vias']:
        if p['net']==net:continue
        shape=Point(p['x']*MM,p['y']*MM).buffer(p['diameter']*MM/2,resolution=16)
        foreign[1].append(shape);foreign[2].append(shape)
    keepouts=[box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]]
    return foreign,allpads,keepouts

def pieces(g):
    if g.is_empty:return []
    return list(g.geoms) if hasattr(g,'geoms') else [g]

def raster(geoms,bounds,inflate,shape):
    x0,y0,_,_=bounds;ny,nx=shape
    image=Image.new('1',(nx,ny),0);draw=ImageDraw.Draw(image)
    for g in geoms:
        if g.is_empty:continue
        if g.bounds[2]<bounds[0]-inflate or g.bounds[0]>bounds[2]+inflate or g.bounds[3]<bounds[1]-inflate or g.bounds[1]>bounds[3]+inflate:continue
        for poly in pieces(g.buffer(inflate,resolution=12)):
            if not hasattr(poly,'exterior'):continue
            pts=[((x-x0)/GRID,(y-y0)/GRID) for x,y in poly.exterior.coords]
            draw.polygon(pts,fill=1)
            # No hole needs to become routable: ignoring holes is conservative.
    return np.asarray(image,dtype=np.bool_).copy()

def search(data,net,start,end,margin):
    foreign,allpads,keepouts=geometries(data,net)
    sx,sy=start['x']*MM,start['y']*MM;tx,ty=end['x']*MM,end['y']*MM
    x0=max(.45,math.floor((min(sx,tx)-margin)/GRID)*GRID);y0=max(.45,math.floor((min(sy,ty)-margin)/GRID)*GRID)
    x1=min(139.55,math.ceil((max(sx,tx)+margin)/GRID)*GRID);y1=min(99.55,math.ceil((max(sy,ty)+margin)/GRID)*GRID)
    bounds=(x0,y0,x1,y1);nx=round((x1-x0)/GRID)+1;ny=round((y1-y0)/GRID)+1;shape=(ny,nx)
    blocked=[]
    for layer in [1,2]:blocked.append(raster(foreign[layer],bounds,WIDTH/2+GAP,shape)|raster(keepouts,bounds,WIDTH/2+.15,shape))
    via_block=raster(foreign[1]+foreign[2],bounds,VIA_D/2+GAP,shape)|raster(allpads,bounds,VIA_H/2+.25,shape)|raster(keepouts,bounds,VIA_D/2+.15,shape)
    via_block|=raster(data.get('routing_extra_via_obstacles',[]),bounds,VIA_D/2+GAP,shape)
    own_drills=[Point(p['x']*MM,p['y']*MM).buffer(p['hole']*MM/2,resolution=12) for p in data['vias']+data.get('reserved_drills',[]) if p['net']==net]
    via_block|=raster(own_drills,bounds,VIA_H/2+.35,shape)
    if not data.get('routing_allow_new_vias',True):
        via_block[:]=True
    yy,xx=np.ogrid[:ny,:nx];via_block|=((x0+xx*GRID)<.7)|((x0+xx*GRID)>139.3)|((y0+yy*GRID)<.7)|((y0+yy*GRID)>99.3)
    sxg,syg=round((sx-x0)/GRID),round((sy-y0)/GRID);txg,tyg=round((tx-x0)/GRID),round((ty-y0)/GRID)
    starts=[0,1] if start['layer']==12 else [start['layer']-1];goals=[0,1] if end['layer']==12 else [end['layer']-1]
    print('Search',net,'margin',margin,'start blocked',[bool(blocked[l][syg,sxg]) for l in starts],'goal blocked',[bool(blocked[l][tyg,txg]) for l in goals],flush=True)
    N=nx*ny
    encode=lambda layer,x,y:layer*N+y*nx+x
    directions=[(1,0,1),(-1,0,1),(0,1,1),(0,-1,1),(1,1,math.sqrt(2)),(1,-1,math.sqrt(2)),(-1,1,math.sqrt(2)),(-1,-1,math.sqrt(2))]
    for label,xx0,yy0,layers,xx1,yy1,opposite in [('start',sxg,syg,starts,txg,tyg,goals),('goal',txg,tyg,goals,sxg,syg,starts)]:
        frontier=deque(encode(ll,xx0,yy0) for ll in layers if not blocked[ll][yy0,xx0]);seen=set(frontier);touched=False;hit=False
        targets={encode(ll,xx1,yy1) for ll in opposite}
        while frontier and len(seen)<6000:
            node=frontier.popleft()
            if node in targets:hit=True;break
            ll=node//N;yy,xx=divmod(node%N,nx)
            if xx in [0,nx-1] or yy in [0,ny-1]:touched=True
            adjacent=[]
            for dx,dy,_ in directions:
                a,b=xx+dx,yy+dy
                if not(0<=a<nx and 0<=b<ny) or blocked[ll][b,a]:continue
                if dx and dy and (blocked[ll][yy,a] or blocked[ll][b,xx]):continue
                adjacent.append(encode(ll,a,b))
            if not via_block[yy,xx] and not blocked[1-ll][yy,xx]:adjacent.append(encode(1-ll,xx,yy))
            for other in adjacent:
                if other not in seen:seen.add(other);frontier.append(other)
        if not hit and not frontier and not touched:raise SealedEscape('Locally sealed '+label+': '+net)
    dist=np.full(2*N,np.inf,dtype=np.float64);parent=np.full(2*N,-1,dtype=np.int32);closed=np.zeros(2*N,dtype=np.bool_);queue=[]
    for layer in starts:
        if blocked[layer][syg,sxg]:continue
        node=encode(layer,sxg,syg);dist[node]=0;heapq.heappush(queue,(math.hypot(txg-sxg,tyg-syg),0,node))
    goal=None;expanded=0;boundary_touched=False
    directions=[(1,0,1),(-1,0,1),(0,1,1),(0,-1,1),(1,1,math.sqrt(2)),(1,-1,math.sqrt(2)),(-1,1,math.sqrt(2)),(-1,-1,math.sqrt(2))]
    while queue and expanded<1500000:
        _,cost,node=heapq.heappop(queue)
        if closed[node] or cost>float(dist[node])+1e-9:continue
        closed[node]=True
        layer=node//N;local=node%N;y,x=divmod(local,nx)
        if x in [0,nx-1] or y in [0,ny-1]:boundary_touched=True
        if x==txg and y==tyg and layer in goals:goal=node;break
        expanded+=1
        options=[]
        for dx,dy,step in directions:
            a,b=x+dx,y+dy
            if not(0<=a<nx and 0<=b<ny) or blocked[layer][b,a]:continue
            if dx and dy and (blocked[layer][y,a] or blocked[layer][b,x]):continue
            options.append((layer,a,b,step))
        if not via_block[y,x] and not blocked[1-layer][y,x]:options.append((1-layer,x,y,50 if VIA_COST_MM is None else VIA_COST_MM/GRID))
        for ll,a,b,step in options:
            other=encode(ll,a,b);new=cost+step
            if not closed[other] and new+1e-9<float(dist[other]):
                dist[other]=new;parent[other]=node
                heapq.heappush(queue,(new+math.hypot(txg-a,tyg-b),new,other))
    if goal is None:
        print('No grid path; expanded',expanded,flush=True)
        if not queue and not boundary_touched:raise SealedEscape('Locally sealed escape: '+net)
        return None
    sequence=[]
    while goal>=0:
        layer=goal//N;local=goal%N;y,x=divmod(local,nx);sequence.append((layer+1,x0+x*GRID,y0+y*GRID));goal=int(parent[goal])
    sequence.reverse();segments=[];vias=[];points=[(sx,sy)]
    unions={ll:unary_union(foreign[ll]) for ll in [1,2]};keep_union=unary_union(keepouts)
    layer=sequence[0][0]
    def flush(ps,ll):
        reduced=[]
        for p in ps:
            if reduced and math.dist(reduced[-1],p)<1e-8:continue
            while len(reduced)>1:
                a,b=reduced[-2:];cross=(b[0]-a[0])*(p[1]-b[1])-(b[1]-a[1])*(p[0]-b[0])
                if abs(cross)<1e-8:reduced.pop()
                else:break
            reduced.append(p)
        smooth=[];index=0
        while index<len(reduced)-1:
            smooth.append(reduced[index]);chosen=index+1
            for candidate in range(len(reduced)-1,index+1,-1):
                trial=LineString([reduced[index],reduced[candidate]])
                if trial.distance(unions[ll])>=WIDTH/2+GAP and trial.distance(keep_union)>=WIDTH/2+.15:
                    chosen=candidate;break
            index=chosen
        if reduced:smooth.append(reduced[-1])
        reduced=smooth
        for a,b in zip(reduced,reduced[1:]):
            if math.dist(a,b)>1e-8:segments.append(dict(net=net,layer=ll,x1=a[0]/MM,y1=a[1]/MM,x2=b[0]/MM,y2=b[1]/MM,width=WIDTH/MM))
    for ll,x,y in sequence:
        if ll!=layer:
            flush(points,layer);vias.append(dict(net=net,x=x/MM,y=y/MM,diameter=VIA_D/MM,hole=VIA_H/MM));points=[(x,y)];layer=ll
        else:points.append((x,y))
    points.append((tx,ty));flush(points,layer)
    minimum=999.
    for p in segments:
        center=LineString([(p['x1']*MM,p['y1']*MM),(p['x2']*MM,p['y2']*MM)])
        gap=center.distance(unions[p['layer']])-WIDTH/2;minimum=min(minimum,gap)
        if gap<.158:
            print('Rejected continuous track clearance',gap,flush=True)
            return None
    both=unary_union(foreign[1]+foreign[2])
    for p in vias:
        gap=Point(p['x']*MM,p['y']*MM).distance(both)-VIA_D/2;minimum=min(minimum,gap)
        if gap<.158:
            print('Rejected continuous via clearance',gap,flush=True)
            return None
    return {'lines':segments,'vias':vias,'min_foreign_copper_gap_mm':minimum,'expanded_nodes':expanded,'search_bounds_mm':bounds}

def plan(data,net):
    unique={}
    for p in data['pads']:
        key=(p['net'],p['layer'],p['x'],p['y'],p['rotation'],tuple(p['shape']))
        unique.setdefault(key,p)
    data={**data,'pads':list(unique.values()),'lines':[p for p in data['lines'] if p['net']!=net],
          'reserved_drills':[p for p in data['vias'] if p.get('routing_retained') and p['net']==net],
          'vias':[p for p in data['vias'] if p['net']!=net]}
    pads=[p for p in data['pads'] if p['net']==net and not p.get('routing_pad_exclude')]
    if len(pads)<2:raise ValueError('Need at least two real pads')
    connected={0};edges=[]
    while len(connected)<len(pads):
        _,a,b=min((math.hypot(pads[a]['x']-pads[b]['x'],pads[a]['y']-pads[b]['y']),a,b) for a in connected for b in range(len(pads)) if b not in connected)
        edges.append((a,b));connected.add(b)
    result={'net':net,'pads':[(p['ref'],p['n']) for p in pads],'lines':[],'vias':[],'edges':[]}
    for a,b in edges:
        route=None
        for margin in SEARCH_MARGINS:
            # Start at the smaller pad, so a trapped fine-pitch escape fails
            # quickly rather than exploring the entire surrounding board.
            first,second=(pads[a],pads[b]) if min(pads[a]['shape'][1:3])<=min(pads[b]['shape'][1:3]) else (pads[b],pads[a])
            route=search(data,net,first,second,margin)
            if route:break
        if not route:raise RuntimeError('No safe path '+net+' '+str((a,b)))
        result['lines']+=route['lines'];result['vias']+=route['vias'];result['edges'].append({k:v for k,v in route.items() if k not in ['lines','vias']})
        data['lines']+=route['lines'];data['vias']+=route['vias']
    return result

if __name__=='__main__':
    net=sys.argv[1] if len(sys.argv)>1 else 'L0_M00'
    data=capture();(ROOT/'grid-route-source.json').write_text(json.dumps(data),encoding='utf-8')
    route=plan(data,net);(ROOT/('grid-plan-'+net+'.json')).write_text(json.dumps(route,indent=2),encoding='utf-8')
    print({'net':net,'pads':route['pads'],'segments':len(route['lines']),'vias':len(route['vias']),'edges':route['edges']},flush=True)
