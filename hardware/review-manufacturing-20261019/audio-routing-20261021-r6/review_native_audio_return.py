"""Audit actual saved copper/planes; descriptive geometry, never SI signoff."""
import sys,json,hashlib,math,csv
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BASE))
from native_project import PROJECT,info
from native_plane_geometry import poured_planes
from resume_offline import read_native
from physical_geometry import actual_pad
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
OUT=BASE/'actual-return';OUT.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
PCB=PROJECT/'pcb/PCB1.epcb2';raw=read_native(PCB);planes=poured_planes(raw)
meta=json.loads((BASE/'native-drc-meta.json').read_text(encoding='utf-8'));assert meta['source_stable'] and sha(PCB)==meta['pcb_sha256_after']
capture=json.loads((BASE/'native-verified-capture.json').read_text(encoding='utf-8'))
audio={n for n in ['I2S_BCK','I2S_DIN','I2S_LRCK']}
vs=[(i,p) for (k,i),p in raw.items() if k=='VIA'];av=[p for i,p in vs if p['netName'] in audio]
excluded=unary_union([Point(p['centerX']*.0254,p['centerY']*.0254).buffer(1,resolution=64) for p in av]+[actual_pad(p).buffer(.5) for p in capture['pads'] if p['layer']==12 and p['net'] in audio])
coverage=[];gaps=[]
for net in sorted(audio):
 for layer,reference,separation in [(1,15,.2104),(16,2,.2104),(2,16,.2104)]:
  ls=[(i,LineString([(p['startX']*.0254,p['startY']*.0254),(p['endX']*.0254,p['endY']*.0254)])) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId')==layer and p['netName']==net]
  length=sum(q.length for i,q in ls);away=[(i,q.difference(excluded)) for i,q in ls];awaylen=sum(q.length for i,q in away)
  coverage.append(dict(net=net,signal_layer=layer,closest_reference_layer=reference,nominal_dielectric_mm=separation,length_mm=length,away_length_mm=awaylen,raw_reference_coverage=sum(q.intersection(planes[reference]).length for i,q in ls)/length if length else None,away_reference_coverage=sum(q.intersection(planes[reference]).length for i,q in away)/awaylen if awaylen else None,farther_inner15_coverage=sum(q.intersection(planes[15]).length for i,q in away)/awaylen if layer==16 and awaylen else None))
  for ident,q in away:
   missing=q.difference(planes[reference]);parts=list(missing.geoms) if hasattr(missing,'geoms') else [missing]
   for gap in parts:
    if gap.is_empty or gap.length<.01:continue
    pt=gap.interpolate(.5,normalized=True);gaps.append(dict(net=net,signal_layer=layer,reference_layer=reference,source_line_id=ident,gap_mm=gap.length,x_mm=pt.x,y_mm=pt.y))
ground=[(i,p) for i,p in vs if p['netName']=='GND'];nearest=[]
for i,p in vs:
 if p['netName'] not in audio:continue
 q=Point(p['centerX']*.0254,p['centerY']*.0254);ds=sorted((q.distance(Point(v['centerX']*.0254,v['centerY']*.0254)),j) for j,v in ground)
 nearest.append(dict(id=i,net=p['netName'],x_mm=q.x,y_mm=q.y,nearest_ground_via_id=ds[0][1],distance_mm=ds[0][0],within_engineering_1p5mm_target=ds[0][0]<=1.5))
v=dict(pcb_sha256=sha(PCB),plane_areas_mm2={str(k):q.area for k,q in planes.items()},via_exclusion_radius_mm=1,pth_outline_exclusion_mm=.5,closest_reference=coverage,reference_gaps=gaps,audio_via_nearest_ground=nearest,not_electromagnetic_simulation=True,si_release=False,manufacturing_release=False)
(OUT/'return-geometry.json').write_text(json.dumps(v,indent=2),encoding='utf-8')
for l,q in planes.items():(OUT/('plane-'+str(l)+'.wkb')).write_bytes(q.wkb)
with (OUT/'reference-gaps.csv').open('w',encoding='utf-8-sig',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(gaps[0]) if gaps else ['net','gap_mm']);writer.writeheader();writer.writerows(gaps)
print(json.dumps(dict(pcb_sha256=v['pcb_sha256'],coverage=coverage,gaps=len(gaps),audio_vias=nearest),indent=2),flush=True)
