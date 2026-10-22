"""Diagnostic plots and measured reference-plane coverage of saved native r4."""
import sys,json,math,hashlib,collections
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;OUT=BASE/'visual-native';OUT.mkdir(exist_ok=True)
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
import numpy as np
from shapely.geometry import Point,LineString,Polygon
from shapely.ops import unary_union
from shapely.geometry.polygon import orient
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Polygon as PatchPoly,Circle,PathPatch
from matplotlib.path import Path as MPath
sys.path.insert(0,str(BASE));sys.path.insert(0,str(ROOT))
from candidate_native import PROJECT,info
from resume_offline import read_native
from physical_geometry import actual_pad
cp=json.loads((BASE/'native-candidate-checkpoint.json').read_text());PCB=PROJECT/'pcb/PCB1.epcb2';assert hashlib.sha256(PCB.read_bytes()).hexdigest()==cp['pcb_sha256']
new=read_native(PCB);old=read_native(Path(info['source_project'])/'pcb/PCB1.epcb2');capture=json.loads((BASE/'native-verified-capture.json').read_text());selected=set(json.loads((BASE/'native-apply-audit.json').read_text())['nets'])
def ring(src):
 x,y=src[:2];pts=[(x,y)];i=2;mode=None
 while i<len(src):
  if isinstance(src[i],str):mode=src[i];i+=1
  if mode=='L':x,y=src[i:i+2];i+=2;pts.append((x,y))
  elif mode=='ARC':
   angle,tx,ty=src[i:i+3];i+=3;theta=math.radians(angle);dx,dy=tx-x,ty-y
   if abs(theta)<1e-10:pts.append((tx,ty))
   else:
    cx=(x+tx)/2-dy/(2*math.tan(theta/2));cy=(y+ty)/2+dx/(2*math.tan(theta/2));rad=math.hypot(x-cx,y-cy);start=math.atan2(y-cy,x-cx);step=2*math.acos(max(-1,min(1,1-.001/.254/max(rad,.001/.254))));num=max(2,math.ceil(abs(theta)/max(step,1e-6)));pts.extend((cx+rad*math.cos(start+theta*j/num),cy+rad*math.sin(start+theta*j/num)) for j in range(1,num+1))
   x,y=tx,ty
  else:raise ValueError(mode)
 return [(x*.254,y*.254) for x,y in pts]
planes={}
for (kind,i),p in new.items():
 if kind!='POURED':continue
 ident=json.loads(i)[1];layer=new['POUR',ident]['layerId'];shapes=[]
 for fill in p['pourFill']:
  ps=fill['path']
  if not fill['fill']:shapes.extend(LineString(ring(q)).buffer(fill['strokeWidth']*.254/2) for q in ps);continue
  a=shapely.make_valid(Polygon(ring(ps[0])));b=unary_union([shapely.make_valid(Polygon(ring(q))) for q in ps[1:]]);shapes.append(a.difference(b))
 planes[layer]=unary_union(shapes)
def polys(g):
 if g.geom_type=='Polygon':yield g
 elif hasattr(g,'geoms'):
  for q in g.geoms:yield from polys(q)
def drawplane(ax,g):
 for po in polys(g):
  po=orient(po,1);vs=[];cs=[]
  for ring_ in [po.exterior,*po.interiors]:
   xy=list(ring_.coords);vs+=xy;cs +=[MPath.MOVETO]+[MPath.LINETO]*(len(xy)-2)+[MPath.CLOSEPOLY]
  ax.add_patch(PathPatch(MPath(vs,cs),facecolor='#365b52',edgecolor='none',alpha=.9,zorder=0))
def tracks(ax,native,layers,highlight=False):
 for l in layers:
  for yes in ([False,True] if highlight else [False]):
   lines=[];widths=[]
   for (k,i),p in native.items():
    if k!='LINE' or p.get('layerId')!=l:continue
    if highlight and (p.get('netName') in selected)!=yes:continue
    lines.append([(p['startX']*.0254,p['startY']*.0254),(p['endX']*.0254,p['endY']*.0254)]);widths.append(max(.3,p['width']*.0254*2.7))
   ax.add_collection(LineCollection(lines,colors='#f6cf56' if yes else {1:'#f0776d',2:'#59a8dc',16:'#b1e08a'}[l],linewidths=widths,alpha=1 if yes or not highlight else .35,zorder=2))
def pads(ax,inner=False):
 for p in capture['pads']:
  if inner and p['layer']!=12:continue
  po=actual_pad(p)
  for q in polys(po):ax.add_patch(PatchPoly(list(q.exterior.coords),facecolor='#b6a46c',edgecolor='none',zorder=4))
def vias(ax,native):
 for (k,i),p in native.items():
  if k!='VIA':continue
  ax.add_patch(Circle((p['centerX']*.0254,p['centerY']*.0254),p['viaDiameter']*.0254/2,facecolor='#929989',edgecolor='none',zorder=3));ax.add_patch(Circle((p['centerX']*.0254,p['centerY']*.0254),p['holeDiameter']*.0254/2,facecolor='#101f29',edgecolor='none',zorder=4))
def style(ax,title,bounds=(0,140,0,100)):
 ax.set_facecolor('#101f29');ax.set_xlim(bounds[:2]);ax.set_ylim(bounds[2:]);ax.set_aspect('equal');ax.set_title(title,color='white',fontsize=11);ax.tick_params(colors='#b3c4cc',labelsize=8);ax.set_xlabel('mm',color='#b3c4cc');ax.set_ylabel('mm',color='#b3c4cc')
 for s in ax.spines.values():s.set_edgecolor('#536874')
fig,axes=plt.subplots(2,2,figsize=(16,12),facecolor='#101f29')
for ax,l,title in zip(axes.flat,[1,2,16,15],['L1 top: source components unchanged','L4 bottom: I2S unchanged, reference review pending','Logical inner16: controls + GND; stackup pending','Logical inner15: GND only; stackup pending']):
 if l in [15,16]:drawplane(ax,planes[l])
 if l!=15:tracks(ax,new,[l])
 pads(ax,l in [15,16]);vias(ax,new);style(ax,title)
fig.suptitle('R4 INDEPENDENT FOUR-LAYER CANDIDATE | native DRC 0 clearance / 0 physics / 62 connection objects | NOT FOR FAB',color='white',fontsize=12);fig.tight_layout(rect=[0,0,1,.97]);fig.savefig(OUT/'four-layer-overview.png',dpi=180);plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(19,4.3),facecolor='#101f29')
for ax,n,l,t in [(axes[0],old,[1,2],'Preserved r3 two-layer core'),(axes[1],new,[1,2],'R4 outer core: replaced controls highlighted'),(axes[2],new,[16],'R4 inner controls: ground hidden for visibility')]:
 tracks(ax,n,l,True);pads(ax);vias(ax,n);style(ax,t,(45,105,35,66))
 for ref in ['U7','U8','U9','U15','U12','U14']:
  ps=[p for p in capture['pads'] if p['ref']==ref];x=sum(p['x'] for p in ps)*.0254/len(ps);y=sum(p['y'] for p in ps)*.0254/len(ps);ax.text(x,y,ref,color='white',ha='center',fontsize=9,zorder=7)
fig.suptitle('Same placement / same 230 components | connected control reroutes: -29 vias, -181.6 mm copper | total 533 -> 519 vias including 4 newly closed nets',color='white',fontsize=12);fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(OUT/'core-comparison.png',dpi=170);plt.close(fig)
# Geometry coverage is explicitly not a return-current or SI signoff.
metrics={}
for l,gnd in planes.items():
 po=list(polys(gnd));metrics[str(l)]=dict(area_mm2=gnd.area,polygon_count=len(po),largest_polygon_mm2=max((p.area for p in po),default=0))
i2s_vias=[p for (k,i),p in new.items() if k=='VIA' and p['netName'].startswith('I2S_')];excluded=unary_union([Point(p['centerX']*.0254,p['centerY']*.0254).buffer(1) for p in i2s_vias]+[actual_pad(p).buffer(.5) for p in capture['pads'] if p['layer']==12 and p['net'].startswith('I2S_')]);coverage=[]
for net in ['I2S_BCK','I2S_DIN','I2S_LRCK']:
 segs=[LineString([(p['startX']*.0254,p['startY']*.0254),(p['endX']*.0254,p['endY']*.0254)]) for (k,i),p in new.items() if k=='LINE' and p.get('layerId')==2 and p['netName']==net]
 length=sum(q.length for q in segs);away=[q.difference(excluded) for q in segs];awaylen=sum(q.length for q in away)
 coverage.append(dict(net=net,bottom_centerline_mm=length,centerline_over_native_L3_GND_fraction=sum(q.intersection(planes[16]).length for q in segs)/length if length else None,via_exclusion_radius_mm=1,pth_exclusion_pad_outline_buffer_mm=.5,away_from_signal_transitions_mm=awaylen,away_centerline_over_native_L3_GND_fraction=sum(q.intersection(planes[16]).length for q in away)/awaylen if awaylen else None,not_si_signoff=True))
contacts=[]
for (k,i),p in new.items():
 if k!='VIA' or p['netName']!='GND':continue
 center=Point(p['centerX']*.0254,p['centerY']*.0254);ann=center.buffer(p['viaDiameter']*.0254/2,resolution=64).difference(center.buffer(p['holeDiameter']*.0254/2,resolution=64));contacts.append(dict(id=i,layers={str(l):dict(intersection_mm2=ann.intersection(planes[l]).area,distance_mm=ann.distance(planes[l])) for l in [15,16]}))
(OUT/'plane-and-return-geometry.json').write_text(json.dumps(dict(pcb_sha256=cp['pcb_sha256'],planes=metrics,bottom_i2s_centerline_coverage=coverage,ground_via_inner_contacts=contacts,not_si_or_touch_capacitance_signoff=True),indent=2))
print(json.dumps(dict(planes=metrics,bottom_i2s_centerline_coverage=coverage,ground_vias=len(contacts),ground_vias_without_both_inner_contacts=[p['id'] for p in contacts if any(x['intersection_mm2']<=1e-6 or x['distance_mm']>.003 for x in p['layers'].values())]),indent=2))

# Locate gaps to guide later I2S rerouting; no electrical qualification implied.
import csv
rows=[]
for net in ['I2S_BCK','I2S_DIN','I2S_LRCK']:
 for (k,i),p in new.items():
  if k!='LINE' or p.get('layerId')!=2 or p['netName']!=net:continue
  line=LineString([(p['startX']*.0254,p['startY']*.0254),(p['endX']*.0254,p['endY']*.0254)])
  gaps=line.difference(excluded).difference(planes[16]);parts=list(gaps.geoms) if hasattr(gaps,'geoms') else [gaps]
  for gap in parts:
   if gap.is_empty or gap.length<.01:continue
   pt=gap.interpolate(.5,normalized=True)
   nearest=sorted((pt.distance(Point(q['centerX']*.0254,q['centerY']*.0254)),j,q['netName']) for (t,j),q in new.items() if t=='VIA' and q['netName']!='GND')[:3]
   rows.append(dict(net=net,source_line_id=i,gap_mm=gap.length,x_mm=pt.x,y_mm=pt.y,nearest_via=nearest[0][1],nearest_via_net=nearest[0][2],nearest_via_center_mm=nearest[0][0],pcb_sha256=cp['pcb_sha256']))
with (OUT/'i2s-reference-gaps.csv').open('w',encoding='utf-8-sig',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['net','gap_mm']);writer.writeheader();writer.writerows(rows)
print('Located reference gaps',len(rows),flush=True)

for layer in [15,16]:(OUT/('plane-'+str(layer)+'.wkb')).write_bytes(planes[layer].wkb)
