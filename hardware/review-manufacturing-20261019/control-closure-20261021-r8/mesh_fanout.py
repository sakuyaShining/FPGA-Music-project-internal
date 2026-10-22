"""Local constrained-triangle navigation inside exact buffered free copper."""
import shapely,heapq,math
from shapely.geometry import Point,LineString,box
def polygons(g):
 if g.geom_type=='Polygon':yield g
 elif hasattr(g,'geoms'):
  for q in g.geoms:yield from polygons(q)
def route(a,b,obstacle,bounds):
 free=box(*bounds).difference(obstacle.buffer(.0762+.1605,resolution=32));start,end=Point(a),Point(b);poly=next((p for p in polygons(free) if p.covers(start) and p.covers(end)),None)
 assert poly is not None,'Exact fanout component disconnected'
 triangles=[q for q in shapely.constrained_delaunay_triangles(poly).geoms if poly.covers(q.representative_point())];starts=[i for i,q in enumerate(triangles) if q.covers(start)];ends={i for i,q in enumerate(triangles) if q.covers(end)};assert starts and ends
 edges={};adj={i:[] for i in range(len(triangles))}
 for i,q in enumerate(triangles):
  pts=list(q.exterior.coords)[:3]
  for u,v in zip(pts,pts[1:]+pts[:1]):
   key=tuple(sorted((tuple(round(z,9) for z in u),tuple(round(z,9) for z in v))))
   if key in edges:
    j=edges[key];mid=((u[0]+v[0])/2,(u[1]+v[1])/2);adj[i].append((j,mid));adj[j].append((i,mid))
   else:edges[key]=i
 centers=[(q.centroid.x,q.centroid.y) for q in triangles];dist={i:0 for i in starts};previous={};heap=[(0,i) for i in starts];heapq.heapify(heap);goal=None
 while heap:
  cost,i=heapq.heappop(heap)
  if cost!=dist[i]:continue
  if i in ends:goal=i;break
  for j,mid in adj[i]:
   nc=cost+math.dist(centers[i],centers[j])
   if nc<dist.get(j,math.inf):dist[j]=nc;previous[j]=(i,mid);heapq.heappush(heap,(nc,j))
 assert goal is not None,'Triangle graph disconnected'
 mids=[]
 while goal in previous:goal,mid=previous[goal];mids.append(mid)
 pts=[a]+mids[::-1]+[b];smooth=[a];i=0
 while i<len(pts)-1:
  j=next((j for j in range(len(pts)-1,i,-1) if poly.covers(LineString([pts[i],pts[j]]))),None);assert j is not None;smooth.append(pts[j]);i=j
 assert all(LineString([u,v]).distance(obstacle)>=.0762+.158 for u,v in zip(smooth,smooth[1:]));return smooth
