"""Find through anchors physically overlapping both saved main ground planes.

Native poured paths use 10-mil coordinates, unlike API pad/track coordinates
in mil. Curved contours are sampled within 0.001 mm for this diagnostic; the
final connectivity decision remains the native DRC, never this approximation.
"""
import argparse
import json
import math
import sys

sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
from shapely.geometry import Polygon,Point
from shapely.ops import unary_union
from physical_geometry import actual_pad
from native_review import ROOT,PROJECT
from resume_offline import read_native

def ring(source):
    x,y=source[:2];points=[(x,y)];i=2;mode=None
    while i<len(source):
        if isinstance(source[i],str):mode=source[i];i+=1
        if mode=='L':
            x,y=source[i:i+2];i+=2;points.append((x,y))
        elif mode=='ARC':
            angle,tx,ty=source[i:i+3];i+=3
            theta=math.radians(angle);dx,dy=tx-x,ty-y
            if abs(theta)<1e-10:points.append((tx,ty))
            else:
                cx=(x+tx)/2-dy/(2*math.tan(theta/2))
                cy=(y+ty)/2+dx/(2*math.tan(theta/2))
                radius=math.hypot(x-cx,y-cy);start=math.atan2(y-cy,x-cx)
                error=.001/.254
                step=2*math.acos(max(-1,min(1,1-error/max(radius,error))))
                count=max(2,math.ceil(abs(theta)/max(step,1e-6)))
                for j in range(1,count+1):
                    a=start+theta*j/count;points.append((cx+radius*math.cos(a),cy+radius*math.sin(a)))
            x,y=tx,ty
        else:raise ValueError('Unsupported native contour mode '+str(mode))
    return [(x*.254,y*.254) for x,y in points]

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',default='resume-ground-round2-source.json')
parser.add_argument('--output',default='resume-ground-main-anchors.json')
options=parser.parse_args()
native=read_native(PROJECT/'pcb/PCB1.epcb2')
planes=[]
for (kind,identity),body in native.items():
    if kind!='POURED':continue
    paths=body['pourFill'][0]['path']
    # Native cutouts can touch or extend outside the outer contour; construct
    # their difference explicitly. Erode copper and enlarge all cutouts beyond
    # the sampling error so candidate anchor membership is conservative.
    shell=shapely.make_valid(Polygon(ring(paths[0]))).buffer(-.005)
    holes=unary_union([shapely.make_valid(Polygon(ring(p))).buffer(.005) for p in paths[1:]])
    polygon=shell.difference(holes)
    if polygon.geom_type=='MultiPolygon':polygon=max(polygon.geoms,key=lambda p:p.area)
    assert polygon.is_valid and not polygon.is_empty
    planes.append(polygon)
assert len(planes)==2
source=json.loads((ROOT/options.source).read_text())
anchors=[]
for pad in source['pads']:
    if pad['net']=='GND' and pad['layer']==12:
        shape=actual_pad(pad)
        areas=[shape.intersection(plane).area for plane in planes]
        if min(areas)>.01:anchors.append({'id':pad['id'],'ref':pad['ref'],'areas_mm2':areas})
for via in source['vias']:
    if via['net']=='GND':
        shape=Point(via['x']*.0254,via['y']*.0254).buffer(via['diameter']*.0254/2,resolution=32)
        areas=[shape.intersection(plane).area for plane in planes]
        if min(areas)>.01:anchors.append({'id':via['id'],'ref':'VIA','areas_mm2':areas})
result={'main_plane_areas_mm2':[p.area for p in planes],'anchors':anchors,
        'native_poured_scale_mm':.254,'approximation_error_mm':.001,'conservative_inset_mm':.005,
        'requires_native_drc':True}
(ROOT/options.output).write_text(json.dumps(result,indent=2),encoding='utf-8')
print('GROUND MAIN ANCHORS',len(anchors),[(a['ref'],a['id']) for a in anchors],flush=True)
