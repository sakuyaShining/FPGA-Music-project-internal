"""Locate remaining reference-plane gaps without presenting projection as SI signoff."""
from pathlib import Path
import sys,json,hashlib
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BASE))
from native_project import PROJECT
from resume_offline import read_native
from native_plane_geometry import poured_planes
from physical_geometry import actual_pad
from shapely.geometry import Point,LineString
from shapely.ops import unary_union,linemerge
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
pcb=PROJECT/'pcb/PCB1.epcb2';native=read_native(pcb);planes=poured_planes(native)
cap=read(BASE/'native-verified-capture.json');ids=set(read(BASE/'native-apply-audit.json')['result']['createdV'])
excluded=unary_union([Point(p['x']*.0254,p['y']*.0254).buffer(1,quad_segs=64) for p in cap['vias'] if p['id'] in ids]+[actual_pad(p).buffer(.5) for p in cap['pads'] if p['net']=='HARM_CS_N' and p['layer']==12])
def segments(g):
    if g.is_empty:return []
    if g.geom_type=='LineString':return [g]
    return [p for v in g.geoms for p in segments(v)]
data=[]
for layer,ref in [(1,15),(16,2)]:
    ls=[LineString([(p['startX']*.0254,p['startY']*.0254),(p['endX']*.0254,p['endY']*.0254)]).difference(excluded) for (kind,i),p in native.items() if kind=='LINE' and p.get('netName')=='HARM_CS_N' and p.get('layerId')==layer]
    gap=unary_union([p.difference(planes[ref]) for p in ls])
    if gap.geom_type=='MultiLineString':gap=linemerge(gap)
    pieces=sorted(segments(gap),key=lambda p:p.length,reverse=True)
    data.append(dict(signal_layer=layer,reference_layer=ref,total_gap_mm=sum(p.length for p in pieces),longest_gap_mm=max([p.length for p in pieces],default=0),gaps=[dict(length_mm=p.length,bounds_mm=list(p.bounds),xy_mm=list(p.coords),alternate_ground15_fraction=p.intersection(planes[15]).length/p.length) for p in pieces if p.length>1e-6]))
out=dict(pcb_sha256=hashlib.sha256(pcb.read_bytes()).hexdigest(),method='Actual rebuilt native GND polygons with holes; centerline projection excluding 1mm signal-via and 0.5mm HARM PTH-pad regions.',layers=data,not_si_signoff=True,limitations=['Projection gaps are a screening result, not a modeled return-current path or predicted waveform.','Alternate inner-1 GND is separated by thick core; its projection cannot replace nearest-reference evaluation.','Actual GPIO edge rates, cable loading and qualified stackup remain unknown.'],next_step='Evaluate return detours and IO edge/cable timing against the final stackup, then bench-test; retain as a routing candidate only.',manufacturing_release=False)
(BASE/'remaining-reference-gaps.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(json.dumps([{k:v for k,v in p.items() if k!='gaps'} for p in data],indent=2))
