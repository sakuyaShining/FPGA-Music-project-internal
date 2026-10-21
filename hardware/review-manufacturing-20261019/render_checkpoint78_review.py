"""Render measured saved copper for inspection; never edits the EDA project."""
import collections
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
from shapely.geometry import Polygon, LineString, Point
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path as MPath
from matplotlib.patches import PathPatch, Circle, Rectangle
from matplotlib.collections import PolyCollection, LineCollection
from physical_geometry import actual_pad
from native_review import ROOT, PROJECT
from resume_offline import read_native

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',default='controls-final-source-78.json')
parser.add_argument('--checkpoint',default='route-checkpoint-0clear-78open.json')
parser.add_argument('--output',default='visual-review-78open')
parser.add_argument('--compare-source')
parser.add_argument('--inspect-via',nargs='*',default=[])
parser.add_argument('--geometry-only',action='store_true')
args=parser.parse_args()
OUT=ROOT/args.output
OUT.mkdir(exist_ok=True)
pcb=PROJECT/'pcb/PCB1.epcb2'
sha=hashlib.sha256(pcb.read_bytes()).hexdigest()
checkpoint=json.loads((ROOT/args.checkpoint).read_text())
assert sha==checkpoint['pcb_sha256']
source=json.loads((ROOT/args.source).read_text())
native=read_native(pcb)
lines=[dict(id=i,net=b['netName'],layer=b['layerId'],x1=b['startX'],y1=b['startY'],x2=b['endX'],y2=b['endY'],width=b['width']) for (k,i),b in native.items() if k=='LINE' and b['layerId'] in [1,2]]
assert len(source['lines'])==checkpoint['lines'] and len(source['vias'])==checkpoint['vias']

def ring(source):
    x,y=source[:2];pts=[(x,y)];i=2;mode=None
    while i<len(source):
        if isinstance(source[i],str):mode=source[i];i+=1
        if mode=='L':x,y=source[i:i+2];i+=2;pts.append((x,y))
        elif mode=='ARC':
            angle,tx,ty=source[i:i+3];i+=3;theta=math.radians(angle);dx,dy=tx-x,ty-y
            if abs(theta)<1e-10:pts.append((tx,ty))
            else:
                cx=(x+tx)/2-dy/(2*math.tan(theta/2));cy=(y+ty)/2+dx/(2*math.tan(theta/2))
                radius=math.hypot(x-cx,y-cy);start=math.atan2(y-cy,x-cx)
                error=.001/.254
                step=2*math.acos(max(-1,min(1,1-error/max(radius,error))))
                count=max(2,math.ceil(abs(theta)/max(step,1e-6)))
                pts.extend((cx+radius*math.cos(start+theta*j/count),cy+radius*math.sin(start+theta*j/count)) for j in range(1,count+1))
            x,y=tx,ty
        else:raise ValueError(mode)
    return [(x*.254,y*.254) for x,y in pts]

planes={}
for (kind,identity),body in native.items():
    if kind!='POURED':continue
    pour_id=json.loads(identity)[1]
    layer=native[('POUR',pour_id)]['layerId']
    shapes=[]
    for fill in body['pourFill']:
        paths=fill['path']
        if not fill['fill']:
            shapes.extend(LineString(ring(p)).buffer(fill['strokeWidth']*.254/2) for p in paths)
            continue
        assert fill['strokeWidth']==0
        outer=shapely.make_valid(Polygon(ring(paths[0])))
        holes=unary_union([shapely.make_valid(Polygon(ring(p))) for p in paths[1:]])
        shapes.append(outer.difference(holes))
    planes[layer]=unary_union(shapes)

def polygons(g):
    if g.geom_type=='Polygon':yield g
    elif hasattr(g,'geoms'):
        for child in g.geoms:yield from polygons(child)

if args.inspect_via:
    results=[]
    for ident in args.inspect_via:
        v=native[('VIA',ident)];center=Point(v['centerX']*.0254,v['centerY']*.0254)
        outer=center.buffer(v['viaDiameter']*.0254/2,resolution=96)
        annulus=outer.difference(center.buffer(v['holeDiameter']*.0254/2,resolution=96))
        results.append({'id':ident,'net':v['netName'],'layers':{str(l):{
            'annulus_intersection_area_mm2':annulus.intersection(g).area,
            'annulus_to_pour_distance_mm':annulus.distance(g),
            'contact_polygon_areas_mm2':[p.area for p in polygons(g) if annulus.distance(p)<=.002]
        } for l,g in planes.items()}})
    (OUT/'plane-contact-audit.json').write_text(json.dumps({'pcb_sha256':sha,'native_poured_scale_mm':.254,
        'arc_sampling_error_mm':.001,'via_contacts':results,'requires_native_drc':True,
        'not_a_full_signal_return_path_signoff':True},indent=2),encoding='utf-8')
    print('LOCAL VIA PLANE CONTACT',json.dumps(results),flush=True)
if args.geometry_only:sys.exit(0)

def draw_plane(ax,g):
    for p in polygons(g):
        p=orient(p,sign=1)
        rings=[p.exterior,*p.interiors];verts=[];codes=[]
        for r in rings:
            pts=list(r.coords);verts.extend(pts);codes.extend([MPath.MOVETO]+[MPath.LINETO]*(len(pts)-2)+[MPath.CLOSEPOLY])
        ax.add_patch(PathPatch(MPath(verts,codes),facecolor='#29474c',edgecolor='none',zorder=1))

pad_shapes={p['id']:actual_pad(p) for p in source['pads']}
refs=collections.defaultdict(list)
for p in source['pads']:refs[p['ref']].append(p)

def draw(ax,layers=(1,2),bounds=(0,140,0,100),ground=False,highlight=None,labels=True):
    ax.set_facecolor('#111f28');ax.set_aspect('equal');x0,x1,y0,y1=bounds
    ax.set_xlim(x0,x1);ax.set_ylim(y0,y1)
    ax.tick_params(colors='#c7d5da',labelsize=8)
    for s in ax.spines.values():s.set_color('#50646e')
    ax.add_patch(Rectangle((0,0),140,100,fill=False,edgecolor='#c1d5cf',linewidth=1,zorder=2))
    if ground:
        for layer in layers:draw_plane(ax,planes[layer])
    ax.figure.canvas.draw()
    pt_per_mm=ax.get_window_extent().width/(x1-x0)*72/ax.figure.dpi
    for layer,color in [(2,'#64b9fa'),(1,'#f2776d')]:
        if layer not in layers:continue
        subset=[p for p in lines if p['layer']==layer]
        for group in [False,True]:
            selected=[p for p in subset if (highlight is not None and p['net'] in highlight)==group]
            if not selected:continue
            segs=[[(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)] for p in selected]
            colors=[('#ffdf78' if group else '#56747a' if p['net']=='GND' else color) for p in selected]
            ax.add_collection(LineCollection(segs,colors=colors,linewidths=[max(.25,p['width']*.0254*pt_per_mm) for p in selected],alpha=1 if highlight is None or group else .22,zorder=3 if not group else 6,capstyle='round'))
    visible_pads=[p for p in source['pads'] if p['layer']==12 or p['layer'] in layers]
    ax.add_collection(PolyCollection([list(pad_shapes[p['id']].exterior.coords) for p in visible_pads],facecolors='#c4b379',edgecolors='none',alpha=.85 if not highlight else .38,zorder=4))
    for v in source['vias']:
        x,y=v['x']*.0254,v['y']*.0254
        if not (x0-1<x<x1+1 and y0-1<y<y1+1):continue
        col='#ffdf78' if highlight and v['net'] in highlight else '#a9b8a6'
        alpha=1 if not highlight or v['net'] in highlight else .2
        ax.add_patch(Circle((x,y),v['diameter']*.0254/2,color=col,linewidth=0,alpha=alpha,zorder=7))
        ax.add_patch(Circle((x,y),v['hole']*.0254/2,color='#111f28',linewidth=0,zorder=8))
    if labels:
        for ref,ps in refs.items():
            if not ref.startswith(('U','J','SW')):continue
            x=sum(p['x'] for p in ps)/len(ps)*.0254;y=sum(p['y'] for p in ps)/len(ps)*.0254
            if x0<x<x1 and y0<y<y1:
                ax.text(x,y,ref,color='white',fontsize=6.5 if x1-x0>90 else 8,ha='center',va='center',bbox=dict(facecolor='#101a21',edgecolor='none',alpha=.8,pad=.6),zorder=10)
    ax.set_xlabel('mm',color='#c7d5da');ax.set_ylabel('mm',color='#c7d5da')

fig,axs=plt.subplots(1,2,figsize=(20,8),facecolor='#111f28',dpi=150)
fig.subplots_adjust(left=.035,right=.985,bottom=.08,top=.90,wspace=.08)
for ax,layer in zip(axs,[1,2]):
    draw(ax,(layer,),ground=True)
    ax.set_title(('TOP' if layer==1 else 'BOTTOM')+' copper | same top-view coordinates',color='white',fontsize=13)
fig.suptitle(f"CURRENT PCB: 140 x 100 mm | 230 parts | {len(source['vias'])} vias | {checkpoint['unconnected_errors']} open objects | actual saved copper",color='white',fontsize=15)
fig.savefig(OUT/'current-layers.png',facecolor=fig.get_facecolor());plt.close(fig)

fig,axs=plt.subplots(1,2,figsize=(18,5.6),facecolor='#111f28',dpi=165)
fig.subplots_adjust(left=.045,right=.985,bottom=.08,top=.90,wspace=.10)
draw(axs[0],bounds=(17,112,29,67),ground=False)
axs[0].set_title('Control / power / DAC congestion | top red, bottom blue',color='white')
draw(axs[1],bounds=(24,109,24,61),ground=False,highlight={'I2S_BCK','I2S_DIN','I2S_LRCK'})
axs[1].set_title('I2S paths highlighted | vias 9 / 8 / 10',color='white')
fig.suptitle('CURRENT CHECKPOINT: diagnostic rendering from native tracks and real pads; pours hidden here',color='white',fontsize=14)
fig.savefig(OUT/'current-core-and-i2s.png',facecolor=fig.get_facecolor());plt.close(fig)

if args.compare_source:
    current_source,current_lines=source,lines
    previous=json.loads((ROOT/args.compare_source).read_text())
    fig,axs=plt.subplots(1,2,figsize=(18,7.8),facecolor='#111f28',dpi=160)
    fig.subplots_adjust(left=.04,right=.985,bottom=.08,top=.88,wspace=.10)
    for ax,data,title in [(axs[0],previous,'BEFORE: RC_DRIVE + BUS_RETURN'),(axs[1],current_source,'AFTER: shorter complete networks')]:
        source=data;lines=data['lines']
        draw(ax,bounds=(24,133,15,82),highlight={'RC_DRIVE','BUS_RETURN'})
        selected=[p for p in lines if p['net'] in {'RC_DRIVE','BUS_RETURN'}]
        mm=sum(math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254 for p in selected)
        vc=sum(p['net'] in {'RC_DRIVE','BUS_RETURN'} for p in source['vias'])
        ax.set_title(f'{title}\n{mm:.1f} mm copper, {vc} vias',color='white',fontsize=12)
    source,lines=current_source,current_lines
    fig.suptitle('Quality refactor: two representative networks highlighted; ground pours hidden for inspection',color='white',fontsize=14)
    fig.savefig(OUT/'quality-before-after.png',facecolor=fig.get_facecolor());plt.close(fig)

via_counts=collections.Counter(v['net'] for v in source['vias'])
lengths=collections.defaultdict(float)
for p in lines:lengths[p['net']]+=math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254
details={}
for net in ['I2S_BCK','I2S_DIN','I2S_LRCK','VIS_DC','VIS_BL_EN','EDIT','RA_MISO','BUS_RETURN','RC_DRIVE']:
    ps=[p for p in source['pads'] if p['net']==net]
    # Euclidean MST is a lower bound, not a claimed legal route or exact route stretch.
    chosen={0};mst=0
    while len(chosen)<len(ps):
        d,j=min((math.hypot(ps[i]['x']-ps[j]['x'],ps[i]['y']-ps[j]['y'])*.0254,j) for i in chosen for j in range(len(ps)) if j not in chosen)
        chosen.add(j);mst+=d
    details[net]={'vias':via_counts[net],'total_track_mm':lengths[net],'pad_euclidean_mst_lower_bound_mm':mst,'length_divided_by_lower_bound':lengths[net]/mst}
metrics={'source_pcb_sha256':sha,'api_tracks':len(source['lines']),'native_tracks_including_microsegments':len(lines),'vias':len(source['vias']),'ground_vias':via_counts['GND'],'total_track_mm':sum(lengths.values()),'selected_nets':details,'ground_copper':{str(l):{'area_mm2':g.area,'polygon_count':len(list(polygons(g)))} for l,g in planes.items()},'not_a_signal_integrity_or_power_integrity_signoff':True}
(OUT/'visual-review-metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
assert hashlib.sha256(pcb.read_bytes()).hexdigest()==sha
print(json.dumps(metrics,indent=2),flush=True)
