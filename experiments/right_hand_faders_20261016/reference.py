"""Independent behavioral oracle. Pixel Y increases downwards, no audio writes."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Touch:
    id: int
    x: int
    y: int

def resolve(axes, zones, touches, held, radius, lo=0, hi=479):
    if lo > hi or radius < 0 or len(axes) != len(held) or len(zones)!=len(axes):
        raise ValueError('Invalid geometry')
    if any(not a<=x<b for (a,b),x in zip(zones,axes)) or any(zones[i-1][1]>zones[i][0] for i in range(1,len(zones))):
        raise ValueError('Zones must be ordered and disjoint, each containing its axis')
    if len({t.id for t in touches}) != len(touches):
        raise ValueError('Touch IDs must be unique in a complete report')
    result=list(held);selected=[]
    for i,axis in enumerate(axes):
        a,b=zones[i]
        near=[t for t in touches if a<=t.x<b and abs(t.x-axis)<=radius]
        left=sorted((t for t in near if t.x<=axis),key=lambda t:(abs(t.x-axis),t.id))
        right=sorted((t for t in near if t.x>=axis),key=lambda t:(abs(t.x-axis),t.id))
        l=left[0] if left else None;r=right[0] if right else None
        if l and r: value=(l.y+r.y)//2
        elif l or r:value=(l or r).y
        else:value=None
        if value is not None:result[i]=max(lo,min(hi,value))
        selected.append((l.id if l else None,r.id if r else None))
    return result,selected
