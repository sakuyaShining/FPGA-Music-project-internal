"""Rejoin the supply islands and move the U15-side supply rail out of the fanout corridor."""
from pathlib import Path
import sys,json,math,hashlib
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,str(BASE));import exchange
from native_project import PROJECT
from resume_offline import read_native
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
from physical_geometry import actual_pad
from four_layer_geometry import copper,connected
s=json.loads((BASE/'native-final-capture.json').read_text());raw=read_native(PROJECT/'pcb/PCB1.epcb2')
s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
oldids={'b7e6698ce09b9487','c9a40e90da34e1e7','a293d08ae29e6105','cd007f8673859f20','76900c2f75d00b5a'}
remove=[p for p in s['lines'] if p['id'] in oldids];assert len(remove)==5 and all(p['net']=='3V3_IO' for p in remove)
old_upper=next(p for p in s['lines'] if p['id']=='cd007f8673859f20')
main=next(p for p in s['lines'] if p['id']=='67397a11b11e19a2')
upper_rail=next(p for p in s['lines'] if p['id']=='723148871d7c2e07')
p17=next(p for p in s['pads'] if p['ref']=='U15' and p['n']=='17')
p20=next(p for p in s['pads'] if p['ref']=='U15' and p['n']=='20')
cap=next(p for p in s['pads'] if p['ref']=='C35' and p['n']=='1')
width=13.2;x=90.6
mainxy=(main['x2']*.0254,main['y2']*.0254)
upperxy=(upper_rail['x2']*.0254,upper_rail['y2']*.0254)
bypass=[(old_upper['x2']*.0254,old_upper['y2']*.0254),(x-.8,old_upper['y2']*.0254),(x,old_upper['y2']*.0254+.8),(x,48.5),(89,48.5),(87.575029,47.074971),(87.216775,47.074971)]
join=[mainxy,(mainxy[0],38.1),(upperxy[0]-(38.1-upperxy[1]),38.1),upperxy]
branch=[(p17['x']*.0254,p17['y']*.0254),(x,p17['y']*.0254)]
decouple=[(p20['x']*.0254,p20['y']*.0254),(cap['x']*.0254,cap['y']*.0254)]
paths=[('3V3_IO',bypass),('3V3_IO',join),('3V3_IO',branch),('3V3_PERIPH',decouple)]
added=[dict(net=n,layer=1,x1=a[0]/.0254,y1=a[1]/.0254,x2=z[0]/.0254,y2=z[1]/.0254,width=width) for n,ps in paths for a,z in zip(ps,ps[1:])]
ground_remove=[];ground_retained=[];trimmed=0
for p in s['lines']:
    if p['net']!='GND' or p['layer']!=1:continue
    g=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)])
    corridor=unary_union([LineString(ps).buffer((p['width']+width)*.0254/2+.175,quad_segs=32) for n,ps in paths])
    if not g.intersects(corridor):continue
    ground_remove.append(p);rest=g.difference(corridor);trimmed+=g.length-rest.length
    for v in (list(rest.geoms) if hasattr(rest,'geoms') else [rest]):
        if v.is_empty or v.length<.01:continue
        a,z=v.coords[0],v.coords[-1]
        ground_retained.append(dict(net='GND',layer=1,x1=a[0]/.0254,y1=a[1]/.0254,x2=z[0]/.0254,y2=z[1]/.0254,width=p['width']))
remove+=ground_remove
work={**s,'lines':[p for p in s['lines'] if p not in remove]+added+ground_retained}
gaps={}
for net,ps in paths:
    f,_=copper(work,net);q=LineString(ps);gap=q.distance(unary_union(f[1]))-width*.0254/2
    assert gap>=.165,(net,ps,gap)
    gaps.setdefault(net,[]).append(gap)
proof={}
for net in ['3V3_IO','3V3_PERIPH']:
    proof[net]={stage:connected([p for p in s['pads'] if p['net']==net],[p for p in data['lines'] if p['net']==net],[p for p in data['vias'] if p['net']==net]) for stage,data in [('before',s),('after',work)]}
assert proof['3V3_IO']['after']['complete']
assert proof['3V3_PERIPH']['after']['pad_islands']<proof['3V3_PERIPH']['before']['pad_islands']
result=dict(source_pcb_sha256=hashlib.sha256((PROJECT/'pcb/PCB1.epcb2').read_bytes()).hexdigest(),remove_lines=remove,lines=added+ground_retained,proof=proof,minimum_clearances_mm=gaps,trimmed_ground_record_length_mm=trimmed,new_vias=0,manufacturing_release=False,scope='Same MPNs, placements, interfaces, outline, layers and original power width. No audio copper, signal copper, pads or vias moved/deleted. Supply bypass opens right-side fanout room; actual future fanout is not claimed complete.')
(BASE/'power-corridor-plan.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in result.items() if k not in ['remove_lines','lines']},indent=2));print('remove',len(remove),'new lines',len(result['lines']))
