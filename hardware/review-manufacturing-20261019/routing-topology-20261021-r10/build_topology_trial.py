"""Derive an isolated trial from retained v2; preserve the historical script."""
from pathlib import Path
import hashlib
ROOT=Path(__file__).resolve().parent.parent
source=ROOT/'control-closure-20261021-r8/plan_closure_v2.py'
s=source.read_text(encoding='utf-8')
s=s.replace("OUT=BASE/'raster-hole-fix-v2'", "OUT=BASE/'harm-trial'")
s=s.replace("selected=['PRESET3','HARM_CS_N','ADDR1','ADDR3','DISP_SCK']", "selected=['HARM_CS_N']")
s=s.replace("from skimage.graph import route_through_array", "from skimage.graph import route_through_array\nsys.path.insert(0,str(ROOT/'control-closure-20261021-r8'))\nfrom mesh_fanout import route as mesh_route")
s=s.replace("eligible=eligible.difference(drills)", "eligible=eligible.difference(drills).intersection(target_region)")
s=s.replace("for tx,ty in candidates:\n  v=", "for tx,ty in candidates:\n  if not target_region.covers(Point(tx,ty)):continue\n  v=")
s=s.replace("except Exception as e:errors.append(str(e));continue", "except Exception as e:\n    try:points=mesh_route(a,b,cu,(x-4,y-4,x+4,y+4))\n    except Exception as e2:errors.append(str(e2));continue")
needle="  pads=[p for p in s['pads'] if p['net']==net]"
s=s.replace(needle,needle+"\n  source_foreign,_=copper(trial,net);inner_obstacle=unary_union(source_foreign[16]+[quiet,mount])\n  parts=sorted(polygons(box(.5,.5,139.5,99.5).difference(inner_obstacle.buffer(.0762+.1605,resolution=32))),key=lambda q:q.area,reverse=True)\n  th=[Point(p['x']*.0254,p['y']*.0254) for p in pads if p['layer']==12]\n  target_region=next((q for q in parts if all(q.covers(p) for p in th)),None)\n  assert target_region is not None,'No shared through-hole component'\n  print('TARGET REGION',target_region.area,flush=True)")
s=s.replace("   assert pts,'No inner16 route in checked windows'", "   if pts is None:\n    pts=mesh_route(anchors[a],anchors[b],obstacle,(.5,.5,139.5,99.5))\n   assert pts,'No inner16 route in checked windows'")
s=s.replace("raster_polygon_holes_preserved=True", "raster_polygon_holes_preserved=True,topology_aware_fanout=True,previous_script_sha256='"+hashlib.sha256(source.read_bytes()).hexdigest()+"'")
target=ROOT/'topology-aware-routing-20261021-r11'
target.mkdir(exist_ok=False)
(target/'plan_harm.py').write_text(s,encoding='utf-8')
compile(s,str(target/'plan_harm.py'),'exec')
print(target/'plan_harm.py')
