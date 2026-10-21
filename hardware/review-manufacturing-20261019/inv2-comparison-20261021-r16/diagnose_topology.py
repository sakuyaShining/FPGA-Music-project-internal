"""Read-only exact free-space screening after a bounded router made no progress."""
from pathlib import Path
import json
from exchange import read,OUT,sha
from four_layer_geometry import copper
from physical_geometry import actual_pad
from shapely.geometry import Point,box
from shapely.ops import unary_union
cp,pcb,s=read();foreign,_=copper(s,'INV2')
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
obs=unary_union(foreign[1]);margin=.0762+.165
free=box(.5,.5,139.5,99.5).difference(unary_union([obs,mount]).buffer(margin,quad_segs=32))
parts=sorted([free] if free.geom_type=='Polygon' else list(free.geoms),key=lambda p:p.area,reverse=True)
rows=[]
for pad in [p for p in s['pads'] if p['net']=='INV2']:
    q=Point(pad['x']*.0254,pad['y']*.0254)
    rows.append(dict(ref=pad['ref'],pin=pad['n'],xy_mm=list(q.coords)[0],center_free_regions=[i for i,p in enumerate(parts) if p.covers(q)],pad_reachable_regions=[i for i,p in enumerate(parts) if p.intersects(actual_pad(pad))],center_foreign_cu_gap_mm=q.distance(obs)))
common=set(rows[0]['pad_reachable_regions'])&set(rows[1]['pad_reachable_regions'])
out=dict(source_pcb_sha256=cp['pcb_sha256'],track_width_mm=.1524,clearance_screen_mm=.165,top_free_components=len(parts),pads=rows,common_top_free_regions=sorted(common),native_imported=False,manufacturing_release=False,interpretation='Continuous polygon model only; no successful route produced. Router failure is not physical impossibility. R13 is a 220ohm series element to SENSE_2, not a supply pullup; do not relocate it under the R30 pullup assumption.')
(OUT/'topology-diagnostic.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
assert sha(pcb)==cp['pcb_sha256'];print(json.dumps(out,indent=2),flush=True)
