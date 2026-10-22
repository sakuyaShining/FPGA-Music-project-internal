"""Physical top/inner16 routing with isolated checkerboard through-via portals."""
import math,json
from pathlib import Path
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
from skimage.graph import MCP_Geometric
from four_layer_geometry import copper
def search(data,net,a,b,quiet,mount,g,raster,bounds):
 g.GRID=.075;grid=g.GRID;x0,y0,x1,y1=bounds;nx=round((x1-x0)/grid)+1;ny=round((y1-y0)/grid)+1;shape=(ny,nx);f,pads=copper(data,net);f[16].append(quiet);cu={l:unary_union(f[l]) for l in [1,16]};allcu=unary_union([q for gs in f.values() for q in gs]);padcu=unary_union(pads)
 blocked=[raster([cu[l],mount],bounds,.0762+.158+grid*math.sqrt(2),shape) for l in [1,16]]
 drills=unary_union([Point(v['x']*.0254,v['y']*.0254).buffer((12+v['hole'])*.0254/2+.35,resolution=24) for v in data['vias']])
 via_block=raster([allcu,quiet],bounds,.3048+.158+grid*math.sqrt(2),shape)|raster([padcu],bounds,.1524+.25+grid*math.sqrt(2),shape)|raster([mount],bounds,.3048+.15+grid*math.sqrt(2),shape)|raster([drills],bounds,grid*math.sqrt(2),shape)
 yy,xx=g.np.ogrid[:ny,:nx];portals=(~via_block)&(~blocked[0])&(~blocked[1])&((xx+yy)%2==0);reuse={}
 existing=[v for v in data['vias'] if v['net']==net]+[p for p in data['pads'] if p['net']==net and p['layer']==12]
 for v in existing:
  x,y=v['x']*.0254,v['y']*.0254;ix,iy=round((x-x0)/grid),round((y-y0)/grid)
  cells=sorted(((math.hypot(x0+j*grid-x,y0+i*grid-y),i,j) for i in range(iy-1,iy+2) for j in range(ix-1,ix+2) if 0<=i<ny and 0<=j<nx and (i+j)%2==0))
  for distance,i,j in cells:
   if distance>.18:continue
   if not blocked[0][i,j] and not blocked[1][i,j]:portals[i,j]=True;reuse[i,j]=(x,y);break
 costs=g.np.full((3,ny,nx),g.np.inf);costs[0][~blocked[0]]=1;costs[2][~blocked[1]]=1;costs[1][portals]=1
 sy,sx=round((a[1]-y0)/grid),round((a[0]-x0)/grid);ty,tx=round((b[1]-y0)/grid),round((b[0]-x0)/grid);starts=[(l,sy,sx) for l in [0,2] if g.np.isfinite(costs[l,sy,sx])];ends=[(l,ty,tx) for l in [0,2] if g.np.isfinite(costs[l,ty,tx])];assert starts and ends,'Mixed endpoint blocked'
 solver=MCP_Geometric(costs,fully_connected=False,sampling=(10.,grid,grid));dist,_=solver.find_costs(starts,ends,find_all_ends=False);goal=min(ends,key=lambda p:dist[p]);assert g.np.isfinite(dist[goal]),'Mixed graph disconnected';path=solver.traceback(goal);lines=[];vias=[];points=[a];layer=1 if path[0][0]==0 else 16
 def flush():
  reduced=[]
  for p in points:
   if reduced and math.dist(p,reduced[-1])<1e-9:continue
   while len(reduced)>1:
    u,v=reduced[-2:]
    if abs((v[0]-u[0])*(p[1]-v[1])-(v[1]-u[1])*(p[0]-v[0]))<1e-8:reduced.pop()
    else:break
   reduced.append(p)
  if not reduced:return
  smooth=[reduced[0]];i=0
  while i<len(reduced)-1:
   chosen=i+1
   for j in range(min(i+500,len(reduced)-1),i,-1):
    q=LineString([reduced[i],reduced[j]])
    if q.distance(cu[layer])>=.0762+.158 and q.distance(mount)>=.0762+.15:chosen=j;break
   smooth.append(reduced[chosen]);i=chosen
  for u,v in zip(smooth,smooth[1:]):
   if math.dist(u,v)<1e-9:continue
   assert LineString([u,v]).distance(cu[layer])>=.0762+.158-1e-8
   lines.append(dict(net=net,layer=layer,x1=u[0]/.0254,y1=u[1]/.0254,x2=v[0]/.0254,y2=v[1]/.0254,width=6))
 for index,(sheet,y,x) in enumerate(path):
  p=(x0+x*grid,y0+y*grid)
  if sheet==1:
   assert 0<index<len(path)-1 and path[index-1][0]!=path[index+1][0] and path[index-1][1:]==path[index+1][1:]==(y,x)
   p=reuse.get((y,x),p);points.append(p);flush()
   if (y,x) not in reuse:vias.append(dict(net=net,x=p[0]/.0254,y=p[1]/.0254,diameter=24,hole=12))
   points=[p]
  else:layer=1 if sheet==0 else 16;points.append(p)
 points.append(b);flush()
 if getattr(g,'DEBUG_ROUTE_PATH',None):Path(g.DEBUG_ROUTE_PATH).write_text(json.dumps(dict(net=net,lines=lines,vias=vias,a=a,b=b,bounds=bounds),indent=2),encoding='utf-8')
 # Reuse of existing barrels adds no hole; every new hole is checked in 4 layers.
 foreign,pads=copper(data,net);foreign[16].append(quiet);allcu=unary_union([q for gs in foreign.values() for q in gs]);padcu=unary_union(pads)
 for i,v in enumerate(vias):
  q=Point(v['x']*.0254,v['y']*.0254);assert q.distance(allcu)-.3048>=.158,(net,'new-via-copper',q.distance(allcu)-.3048);assert q.distance(padcu)-.1524>=.25,(net,'new-via-pad',q.distance(padcu)-.1524)
  near=[(q.distance(Point(o['x']*.0254,o['y']*.0254))-(12+o['hole'])*.0254/2,o['x']*.0254,o['y']*.0254) for o in data['vias']+vias[:i]];assert all(z[0]>=.35 for z in near),(net,'new-via-drill-spacing',v,min(near))
 return lines,vias
