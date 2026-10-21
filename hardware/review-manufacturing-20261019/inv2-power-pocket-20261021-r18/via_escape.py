"""Continuous terminal escape capacity, separating line topology from via/drill limits."""
from pathlib import Path
import sys,json,hashlib
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,str(ROOT/'inv2-comparison-20261021-r16'))
from exchange import read
from four_layer_geometry import copper
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
from physical_geometry import actual_pad
cp,pcb,s=read();power=json.loads((OUT/'plan.json').read_text(encoding='utf8'))['power_rework'];s['lines']=[p for p in s['lines'] if p['id']!=power['remove_line_id']]+power['replacement_lines'];f,pads=copper(s,'INV2');foreign={l:unary_union(q) for l,q in f.items()};allcu=unary_union(list(foreign.values()))
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
import re
quiet=unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+(.6 if p['net'].startswith('I2S_') else .5),quad_segs=32) for p in s['lines'] if p['layer']==2 and (p['net'].startswith('I2S_') or re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net']))])
free=box(.5,.5,139.5,99.5).difference(unary_union([foreign[1],mount]).buffer(.0762+.165,quad_segs=32))
def polys(q):
    if q.is_empty:return []
    if q.geom_type=='Polygon':return [q]
    if hasattr(q,'geoms'):return [p for g in q.geoms for p in polys(g)]
    return []
regions=polys(free)
blocks=[('foreign_copper_annulus',allcu.buffer(.3048+.165,quad_segs=64)),('all_pads_hole',unary_union(pads).buffer(.1524+.25,quad_segs=64)),('quiet_annulus',quiet.buffer(.3048+.165,quad_segs=64)),('mount_annulus',mount.buffer(.3048+.15,quad_segs=64)),('existing_drills',unary_union([Point(v['x']*.0254,v['y']*.0254).buffer(.1524+.35+v['hole']*.0254/2,quad_segs=64) for v in s['vias']]))]
rows=[]
for t in [p for p in s['pads'] if p['net']=='INV2']:
    q=Point(t['x']*.0254,t['y']*.0254);region=next(p for p in regions if p.covers(q));safe=region;steps=[]
    for name,b in blocks:
        safe=safe.difference(b);steps.append(dict(criterion=name,remaining_area_mm2=safe.area))
    areas=sorted(polys(safe),key=lambda p:p.area,reverse=True)
    rows.append(dict(ref=t['ref'],pin=t['n'],top_region_area_mm2=region.area,top_region_bounds_mm=list(region.bounds),via_safe_area_mm2=safe.area,steps=steps,legal_area_representatives_mm=[list(p.representative_point().coords)[0] for p in areas[:8]],safe_polygons_wkb_hex=[p.wkb_hex for p in areas]))
out=dict(source_pcb_sha256=cp['pcb_sha256'],method='Continuous free-space intersection for24mil/12mil via and6mil line; explicit native-copper/own-pad/drill/quiet guards. No ray/grid-only impossibility claim.',terminals=rows,native_imported=False,manufacturing_release=False)
(OUT/'via-escape-capacity.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
assert hashlib.sha256(pcb.read_bytes()).hexdigest()==cp['pcb_sha256']
print(json.dumps({**out,'terminals':[{k:v for k,v in p.items() if k!='safe_polygons_wkb_hex'} for p in rows]},indent=2),flush=True)
