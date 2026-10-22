"""Actual pad shapes and same-net two-layer continuity for exchange QA."""
import grid_route as grid
from shapely.geometry import Point,LineString,box
from shapely.affinity import scale,rotate,translate

def actual_pad(p):
    kind,w,h,*rest=p['shape'];w*=grid.MM;h*=grid.MM
    if kind=='ELLIPSE':g=scale(Point(0,0).buffer(1,resolution=32),xfact=w/2,yfact=h/2,origin=(0,0))
    elif kind=='OVAL':
        radius=min(w,h)/2
        ends=[(-(w-h)/2,0),((w-h)/2,0)] if w>h else [(0,-(h-w)/2),(0,(h-w)/2)]
        g=LineString(ends).buffer(radius,resolution=32)
    else:g=box(-w/2,-h/2,w/2,h/2)
    return translate(rotate(g,p['rotation'],origin=(0,0)),p['x']*grid.MM,p['y']*grid.MM)

def connected_subset(pads,lines,vias):
    if len(pads)<2:return {'complete':False,'reason':'fewer_than_two_pads'}
    objects=[]
    for p in pads:objects.append((3 if p['layer']==12 else 1<<(p['layer']-1),actual_pad(p),'pad',p))
    for p in lines:objects.append((1<<(p['layer']-1),LineString([(p['x1']*grid.MM,p['y1']*grid.MM),(p['x2']*grid.MM,p['y2']*grid.MM)]).buffer(p['width']*grid.MM/2,resolution=16),'line',p))
    for p in vias:objects.append((3,Point(p['x']*grid.MM,p['y']*grid.MM).buffer(p['diameter']*grid.MM/2,resolution=16),'via',p))
    parents=list(range(len(objects)))
    def root(i):
        while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
        return i
    for i,(layers,shape,kind,p) in enumerate(objects):
        for j in range(i):
            if layers&objects[j][0] and root(i)!=root(j) and shape.distance(objects[j][1])<=.003:
                parents[root(i)]=root(j)
    components={root(i) for i in range(len(pads))}
    if len(components)!=1:return {'complete':False,'pad_islands':len(components)}
    target=next(iter(components));keep=[(kind,p) for i,(_,_,kind,p) in enumerate(objects) if root(i)==target]
    return {'complete':True,'lines':[p for k,p in keep if k=='line'],'vias':[p for k,p in keep if k=='via'],
            'orphan_objects_removed':sum(root(i)!=target for i in range(len(objects)))}
