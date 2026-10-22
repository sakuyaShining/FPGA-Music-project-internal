"""Relocate R30 bias resistor, retain explicit original power-bus junction."""
from pathlib import Path
import sys,json,math,hashlib,copy
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,str(ROOT/'freerouting-comparison-20261021-r14'))
from exchange import read
from physical_geometry import actual_pad
from four_layer_geometry import copper,connected
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union,nearest_points
from shapely.affinity import rotate,translate
sys.path.insert(0,str(ROOT/'control-closure-20261021-r8'));from mesh_fanout import route as mesh_route
cp,PCB,s=read()
route=json.loads((ROOT/'freerouting-comparison-20261021-r14/selected-copper.json').read_text(encoding='utf-8'))
validation=json.loads((ROOT/'freerouting-comparison-20261021-r14/independent-validation.json').read_text(encoding='utf-8'))
assert validation['source_pcb_sha256']==cp['pcb_sha256'] and not validation['geometric_failures']
oldpads=[p for p in s['pads'] if p['ref']=='R30'];cx=sum(p['x'] for p in oldpads)/2;cy=sum(p['y'] for p in oldpads)/2
oldangle=90;assert {p['rotation'] for p in oldpads}=={oldangle}
docs={};current=None
for text in PCB.read_text(encoding='utf-8').splitlines():
    if '||' not in text:continue
    h,b=text.split('||',1);h=json.loads(h);v=json.loads(b.rstrip('|')) if b.rstrip('|').strip() else None
    if h['type']=='DOCHEAD':current=v['uuid'];docs.setdefault(current,{})
    if current:docs[current][h['type'],h.get('id')]=v
from resume_offline import read_native
raw=read_native(PCB)
def points(path):
    if path and path[0]=='CIRCLE':
        _,x,y,r=path;return [(x-r,y-r),(x+r,y+r)]
    if not path or not isinstance(path[0],(int,float)):return []
    x,y=path[:2];out=[(x,y)];i=2;mode=None
    while i<len(path):
        if isinstance(path[i],str):mode=path[i];i+=1
        if mode=='L':x,y=path[i:i+2];i+=2;out.append((x,y))
        elif mode=='ARC':
            angle,tx,ty=path[i:i+3];i+=3;t=math.radians(angle);dx,dy=tx-x,ty-y
            if abs(t)>1e-8:
                ax=(x+tx)/2-dy/(2*math.tan(t/2));ay=(y+ty)/2+dx/(2*math.tan(t/2));radius=math.hypot(x-ax,y-ay);out.extend([(ax-radius,ay-radius),(ax+radius,ay+radius)])
            x,y=tx,ty;out.append((x,y))
        else:break
    return out
attrs={}
for (k,i),v in raw.items():
    if k=='ATTR':attrs.setdefault(v['parentId'],{})[v['key']]=v['value']
boxes={};local_r=None
for cid,a in attrs.items():
    if 'Designator' not in a or 'Footprint' not in a or ('COMPONENT',cid) not in raw:continue
    geoms=[]
    for (k,i),p in docs[a['Footprint']].items():
        if not p:continue
        if k=='POLY':
            pts=points(p.get('path',[]));sw=p.get('width',0)/2
            if pts:geoms.append(box(min(x for x,y in pts)-sw,min(y for x,y in pts)-sw,max(x for x,y in pts)+sw,max(y for x,y in pts)+sw))
        if k=='PAD':
            q=p['defaultPad'];x,y=p['centerX'],p['centerY'];geoms.append(rotate(box(x-q['width']/2,y-q['height']/2,x+q['width']/2,y+q['height']/2),p.get('padAngle',0),origin=(x,y)))
    if not geoms:continue
    geometry=unary_union(geoms);c=raw['COMPONENT',cid]
    q=translate(rotate(geometry,c['angle'],origin=(0,0)),c['x'],c['y']);boxes[a['Designator']]=box(*[v*.0254 for v in q.bounds])
    if a['Designator']=='R30':local_r=geometry
assert local_r is not None
w={**s,'pads':[p for p in s['pads'] if p['ref']!='R30'],'lines':s['lines']+route['lines'],'vias':s['vias']+route['vias']}
foreign={}
for net in ['HARM_CS_N','3V3_IO']:
    f,_=copper(w,net);foreign[net]=unary_union(f[1])
powerline_shapes=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]) for p in s['lines'] if p['net']=='3V3_IO' and p['layer']==1]
powermetal=unary_union([q.buffer(p['width']*.0254/2,quad_segs=32) for p,q in zip([p for p in s['lines'] if p['net']=='3V3_IO' and p['layer']==1],powerline_shapes)])
harm_shapes=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]) for p in route['lines'] if p['layer']==1]
oldpower=next(p for p in oldpads if p['n']=='1');oldpoint=Point(oldpower['x']*.0254,oldpower['y']*.0254);oldshape=actual_pad(oldpower)
def line(net,a,b,width):return dict(net=net,layer=1,x1=a[0]/.0254,y1=a[1]/.0254,x2=b[0]/.0254,y2=b[1]/.0254,width=width/.0254)
junction=[]
for p,q in zip([p for p in s['lines'] if p['net']=='3V3_IO' and p['layer']==1],powerline_shapes):
    if q.buffer(p['width']*.0254/2).distance(oldshape)<.003:
        pt=nearest_points(oldpoint,q)[1]
        if pt.distance(oldpoint)>.003:junction.append(line('3V3_IO',(oldpoint.x,oldpoint.y),(pt.x,pt.y),min(.33528,p['width']*.0254)))
for p in junction:
    q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)])
    assert q.distance(foreign['3V3_IO'])-p['width']*.0254/2>=.165
candidates=[]
for angle in [180,0,90,270]:
    delta=math.radians(angle-oldangle)
    for ix in range(33):
        x=87.4+ix*.1
        for iy in range(46):
            y=40.5+iy*.1
            cb=translate(rotate(local_r,angle,origin=(0,0)),x/.0254,y/.0254);cb=box(*[v*.0254 for v in cb.bounds])
            devicegap=min(cb.distance(q) for ref,q in boxes.items() if ref!='R30')
            if devicegap<.55:continue
            ps=[]
            for p in oldpads:
                u=(p['x']-cx)*.0254;v=(p['y']-cy)*.0254
                ps.append({**p,'x':(x+u*math.cos(delta)-v*math.sin(delta))/.0254,'y':(y+u*math.sin(delta)+v*math.cos(delta))/.0254,'rotation':angle})
            pp=next(p for p in ps if p['n']=='1');hp=next(p for p in ps if p['n']=='2')
            if actual_pad(pp).distance(powermetal)>.0001:continue
            if any(actual_pad(p).distance(foreign[p['net']])<.165 for p in ps):continue
            if any(actual_pad(p).distance(Point(v['x']*.0254,v['y']*.0254))-v['hole']*.0254/2<.25 for p in ps for v in w['vias']):continue
            start=(hp['x']*.0254,hp['y']*.0254);targets=[]
            for q in harm_shapes:
                pt=nearest_points(Point(start),q)[1];targets +=[(pt.x,pt.y),q.coords[0],q.coords[-1]]
            best=None
            for end in sorted(set(targets),key=lambda q:math.dist(start,q)):
                q=LineString([start,end])
                if q.distance(foreign['HARM_CS_N'])>=.0762+.165 and q.distance(actual_pad(pp))>=.0762+.165:
                    best=[start,end];break
            if best is None:continue
            candidates.append(dict(x=x,y=y,rotation=angle,pads=ps,device_bbox_gap_mm=devicegap,branch_points_mm=best,branch_mm=math.dist(*best)))
assert candidates,'No direct R30 pocket met current footprint/copper/hole constraints'
best=min(candidates,key=lambda p:p['branch_mm']);branch=line('HARM_CS_N',*best['branch_points_mm'],.1524)
working={**w,'pads':w['pads']+best['pads'],'lines':w['lines']+junction+[branch]}
proofs={net:connected([p for p in working['pads'] if p['net']==net],[p for p in working['lines'] if p['net']==net],[p for p in working['vias'] if p['net']==net]) for net in ['HARM_CS_N','3V3_IO']}
assert all(p['complete'] for p in proofs.values()),proofs
plan=dict(source_pcb_sha256=cp['pcb_sha256'],component='R30',component_x_mm=best['x'],component_y_mm=best['y'],component_rotation=best['rotation'],pads=best['pads'],
          remove_line_ids=[],remove_via_ids=[],lines=route['lines']+junction+[branch],vias=route['vias'],bias_bus_junction_lines=junction,
          original_value_footprint_nets_preserved=True,other229_components_unchanged=True,connectivity=proofs,device_bbox_gap_mm=best['device_bbox_gap_mm'],
          total_harm_length_mm=validation['summed_length_mm']+best['branch_mm'],new_signal_vias=len(route['vias']),new_power_vias=0,
          resistor_branch_mm=best['branch_mm'],candidates=len(candidates),native_imported=False,manufacturing_release=False,requires_native_device_spacing_and_full_drc=True)
(OUT/'plan.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8');(OUT/'working.json').write_text(json.dumps(working),encoding='utf-8')
print(json.dumps({k:v for k,v in plan.items() if k not in ['pads','lines','bias_bus_junction_lines']},indent=2),flush=True)
