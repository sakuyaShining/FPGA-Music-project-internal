"""Retain existing short pad-to-via fanouts while ripping up a net's trunk.

Only same-layer paths <=2.5 mm from a real pad to an existing via qualify.
The physical pads remain collision obstacles; virtual through pads are solely
search anchors. No virtual geometry is written as a native component or pad.
"""
import heapq
import math
from grid_route import MM,WIDTH,GAP,VIA_D,VIA_H,geometries,pad_shape,plan
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
from grid_route import raster,GRID
import numpy as np

def reserve(source, working, net):
    lines=[p for p in source['lines'] if p['net']==net]
    vias=[p for p in source['vias'] if p['net']==net]
    key=lambda x,y:(round(x,2),round(y,2))
    kept_lines={};kept_vias={};replacements={};anchors=[]
    for pad in [p for p in source['pads'] if p['net']==net and p['layer']!=12]:
        adjacency={}
        for line in lines:
            if line['layer']!=pad['layer']:continue
            a=key(line['x1'],line['y1']);b=key(line['x2'],line['y2'])
            length=math.dist(a,b)*MM
            adjacency.setdefault(a,[]).append((b,length,line))
            adjacency.setdefault(b,[]).append((a,length,line))
        targets={key(v['x'],v['y']):v for v in vias}
        start=key(pad['x'],pad['y']);queue=[(0,start,[])];seen=set();found=None
        while queue:
            distance,node,path=heapq.heappop(queue)
            if distance>2.5:break
            if node in seen:continue
            seen.add(node)
            if node in targets:found=(targets[node],path);break
            for other,length,line in adjacency.get(node,[]):
                if other not in seen:heapq.heappush(queue,(distance+length,other,path+[line]))
        if not found:continue
        via,path=found
        if not path:continue
        kept_vias[via['id']]={**via,'routing_retained':True}
        for line in path:kept_lines[line['id']]=line
        replacements[pad['id']]={**pad,'routing_pad_exclude':True}
        anchors.append({**pad,'id':'anchor-'+pad['id'],'ref':'FANOUT-'+pad['ref'],
                        'x':via['x'],'y':via['y'],'rotation':0,'layer':12,
                        'shape':['ELLIPSE',via['diameter'],via['diameter'],0]})
    working['pads']=[replacements.get(p['id'],p) for p in working['pads']]+anchors
    working['lines']+=list(kept_lines.values());working['vias']+=list(kept_vias.values())
    return {'net':net,'pads':[], 'lines':list(kept_lines.values()),'vias':list(kept_vias.values()),
            'edges':[], 'reserved_real_pad_fanouts':len(anchors)}

def new_mux_fanouts(working,nets,refs=None,max_pad_short_mm=.6):
    """Reserve short, continuously checked outward escapes before trunk routing."""
    refs=set(refs or ['U1','U2','U3','U4','U5','U6'])
    result={'net':None,'pads':[],'lines':[],'vias':[],'edges':[],'new_fanouts':[]}
    for pad in sorted(list(working['pads']),key=lambda p:nets.index(p['net']) if p['net'] in nets else len(nets)):
        if pad['net'] not in nets or pad.get('routing_pad_exclude') or pad['ref'] not in refs:continue
        if min(pad['shape'][1:3])*MM>max_pad_short_mm:continue
        siblings=[p for p in working['pads'] if p['ref']==pad['ref'] and not p['id'].startswith('anchor-')]
        cx=sum(p['x'] for p in siblings)/len(siblings);cy=sum(p['y'] for p in siblings)/len(siblings)
        dx,dy=pad['x']-cx,pad['y']-cy
        angle=math.radians(pad['rotation'])
        axis=(math.cos(angle),math.sin(angle)) if pad['shape'][1]>=pad['shape'][2] else (-math.sin(angle),math.cos(angle))
        sign=1 if axis[0]*dx+axis[1]*dy>=0 else -1
        out=(axis[0]*sign,axis[1]*sign)
        foreign,allpads,keepouts=geometries(working,pad['net'])
        copper=unary_union(foreign[1]+foreign[2]);top=unary_union(foreign[pad['layer']]);pads_union=unary_union(allpads);ko=unary_union(keepouts)
        start=(pad['x']*MM,pad['y']*MM);selected=None
        # Tented vias beneath the plastic TSSOP body can free the outer pin
        # row. Every candidate still clears all actual copper pads and holes.
        for direction in [(-out[0],-out[1]),out]:
          for distance in [1.25+i*.125 for i in range(19)]:
            for lateral in [0,.1,-.1,.2,-.2,.3,-.3,.5,-.5]:
                point=(start[0]+direction[0]*distance-direction[1]*lateral,start[1]+direction[1]*distance+direction[0]*lateral)
                if not(.7<point[0]<139.3 and .7<point[1]<99.3):continue
                path=LineString([start,point]);via=Point(point)
                if path.distance(top)<WIDTH/2+GAP or via.distance(copper)<VIA_D/2+GAP:continue
                if via.distance(pads_union)<VIA_H/2+.25:continue
                if path.distance(ko)<WIDTH/2+.15 or via.distance(ko)<VIA_D/2+.15:continue
                selected=(point,min(path.distance(top)-WIDTH/2,via.distance(copper)-VIA_D/2));break
            if selected:break
          if selected:break
        if not selected:continue
        point,gap=selected
        line={'net':pad['net'],'layer':pad['layer'],'x1':pad['x'],'y1':pad['y'],'x2':point[0]/MM,'y2':point[1]/MM,'width':WIDTH/MM}
        via={'net':pad['net'],'x':point[0]/MM,'y':point[1]/MM,'diameter':VIA_D/MM,'hole':VIA_H/MM,'routing_retained':True}
        working['lines'].append(line);working['vias'].append(via)
        working['pads']=[{**p,'routing_pad_exclude':True} if p['id']==pad['id'] else p for p in working['pads']]
        working['pads'].append({**pad,'id':'anchor-'+pad['id'],'ref':'FANOUT-'+pad['ref'],'x':via['x'],'y':via['y'],
                               'rotation':0,'layer':12,'shape':['ELLIPSE',VIA_D/MM,VIA_D/MM,0]})
        result['lines'].append(line);result['vias'].append(via);result['edges'].append({'min_foreign_copper_gap_mm':gap})
        result['new_fanouts'].append((pad['net'],pad['ref'],pad['n']))
    return result

def probe_mux_escapes(working,nets):
    """Keep only the short first/last fanout from a successful full-net trial."""
    results=[]
    for net in nets:
        unescaped=[p for p in working['pads'] if p['net']==net and not p.get('routing_pad_exclude')
                   and p['ref'] in ['U1','U2','U3','U4','U5','U6'] and min(p['shape'][1:3])*MM<=.6]
        if not unescaped:continue
        trial=plan(working,net)
        probe={**working,'lines':[{**p,'id':f'probe-line-{i}'} for i,p in enumerate(trial['lines'])],
               'vias':[{**p,'id':f'probe-via-{i}'} for i,p in enumerate(trial['vias'])]}
        escape=reserve(probe,working,net)
        escape['edges']=trial['edges']
        print('PROBE FANOUT',net,escape['reserved_real_pad_fanouts'],flush=True)
        results.append(escape)
    return results

def grid_mux_fanouts(working,nets,refs=None,max_pad_short_mm=.6):
    """Find a short top-layer escape to the nearest valid through via by Dijkstra."""
    refs=set(refs or ['U1','U2','U3','U4','U5','U6'])
    result={'net':None,'pads':[],'lines':[],'vias':[],'edges':[],'new_fanouts':[]}
    ordered=sorted(list(working['pads']),key=lambda p:nets.index(p['net']) if p['net'] in nets else len(nets))
    for pad in ordered:
        if pad['net'] not in nets or pad.get('routing_pad_exclude') or pad['ref'] not in refs:continue
        if min(pad['shape'][1:3])*MM>max_pad_short_mm:continue
        foreign,allpads,keepouts=geometries(working,pad['net'])
        corridors=[]
        siblings=[p for p in working['pads'] if p['ref']==pad['ref'] and not p['id'].startswith('anchor-')]
        cx=sum(p['x'] for p in siblings)/len(siblings);cy=sum(p['y'] for p in siblings)/len(siblings)
        for other in siblings:
            if other['net'] not in nets or other['net']==pad['net'] or other.get('routing_pad_exclude'):continue
            a=math.radians(other['rotation']);axis=(math.cos(a),math.sin(a)) if other['shape'][1]>=other['shape'][2] else (-math.sin(a),math.cos(a))
            sign=-1 if axis[0]*(other['x']-cx)+axis[1]*(other['y']-cy)>=0 else 1
            origin=(other['x']*MM,other['y']*MM)
            corridors.append(LineString([origin,(origin[0]+axis[0]*sign*1.7,origin[1]+axis[1]*sign*1.7)]))
        sx,sy=pad['x']*MM,pad['y']*MM
        x0=max(.7,math.floor((sx-4)/GRID)*GRID);y0=max(.7,math.floor((sy-4)/GRID)*GRID)
        x1=min(139.3,sx+4);y1=min(99.3,sy+4)
        nx=round((x1-x0)/GRID)+1;ny=round((y1-y0)/GRID)+1;shape=(ny,nx);bounds=(x0,y0,x1,y1)
        blocked=raster(foreign[pad['layer']]+keepouts,bounds,WIDTH/2+GAP,shape)|raster(corridors,bounds,WIDTH+GAP,shape)
        via_block=raster(foreign[1]+foreign[2]+keepouts,bounds,VIA_D/2+GAP,shape)|raster(allpads,bounds,VIA_H/2+.25,shape)
        via_block|=raster(corridors,bounds,VIA_D/2+GAP+WIDTH/2,shape)
        x,y=round((sx-x0)/GRID),round((sy-y0)/GRID);start=y*nx+x
        if blocked[y,x]:continue
        dist={start:0};parents={};queue=[(0,start)];goal=None
        directions=[(1,0,1),(-1,0,1),(0,1,1),(0,-1,1),(1,1,2**.5),(1,-1,2**.5),(-1,1,2**.5),(-1,-1,2**.5)]
        while queue:
            cost,node=heapq.heappop(queue)
            if cost>dist[node]+1e-9:continue
            if cost*GRID>4:break
            y,x=divmod(node,nx)
            if not via_block[y,x]:goal=node;break
            for dx,dy,step in directions:
                a,b=x+dx,y+dy
                if not(0<=a<nx and 0<=b<ny) or blocked[b,a]:continue
                if dx and dy and (blocked[y,a] or blocked[b,x]):continue
                other=b*nx+a;new=cost+step
                if new+1e-9<dist.get(other,float('inf')):
                    dist[other]=new;parents[other]=node;heapq.heappush(queue,(new,other))
        if goal is None:continue
        path=[];node=goal
        while True:
            y,x=divmod(node,nx);path.append((x0+x*GRID,y0+y*GRID))
            if node==start:break
            node=parents[node]
        path.reverse();path[0]=(sx,sy);point=path[-1]
        union=unary_union(foreign[pad['layer']]);both=unary_union(foreign[1]+foreign[2]);ko=unary_union(keepouts)
        smooth=[path[0]];index=0
        while index<len(path)-1:
            chosen=index+1
            for candidate in range(len(path)-1,index+1,-1):
                line=LineString([path[index],path[candidate]])
                if line.distance(union)>=WIDTH/2+GAP and line.distance(ko)>=WIDTH/2+.15 and all(line.distance(c)>=WIDTH+GAP for c in corridors):chosen=candidate;break
            smooth.append(path[chosen]);index=chosen
        gap=min([LineString([a,b]).distance(union)-WIDTH/2 for a,b in zip(smooth,smooth[1:])]+[Point(point).distance(both)-VIA_D/2])
        if gap<.158:continue
        lines=[{'net':pad['net'],'layer':pad['layer'],'x1':a[0]/MM,'y1':a[1]/MM,'x2':b[0]/MM,'y2':b[1]/MM,'width':WIDTH/MM} for a,b in zip(smooth,smooth[1:]) if math.dist(a,b)>1e-8]
        via={'net':pad['net'],'x':point[0]/MM,'y':point[1]/MM,'diameter':VIA_D/MM,'hole':VIA_H/MM,'routing_retained':True}
        working['lines']+=lines;working['vias'].append(via)
        working['pads']=[{**p,'routing_pad_exclude':True} if p['id']==pad['id'] else p for p in working['pads']]
        working['pads'].append({**pad,'id':'anchor-'+pad['id'],'ref':'FANOUT-'+pad['ref'],'x':via['x'],'y':via['y'],'rotation':0,'layer':12,'shape':['ELLIPSE',VIA_D/MM,VIA_D/MM,0]})
        result['lines']+=lines;result['vias'].append(via);result['edges'].append({'min_foreign_copper_gap_mm':gap})
        result['new_fanouts'].append((pad['net'],pad['ref'],pad['n']))
    return result
