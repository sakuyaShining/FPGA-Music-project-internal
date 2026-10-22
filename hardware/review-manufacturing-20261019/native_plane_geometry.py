"""Native POURED parser: 0.254 mm coordinates, actual holes, chord error <=1um."""
import math,json,shapely
from shapely.geometry import Polygon,LineString
from shapely.ops import unary_union
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

def poured_planes(native):
 planes={}
 for (kind,i),p in native.items():
  if kind!='POURED':continue
  ident=json.loads(i)[1];layer=native['POUR',ident]['layerId'];shapes=[]
  for fill in p['pourFill']:
   ps=fill['path']
   if not fill['fill']:shapes.extend(LineString(ring(q)).buffer(fill['strokeWidth']*.254/2) for q in ps);continue
   a=shapely.make_valid(Polygon(ring(ps[0])));b=unary_union([shapely.make_valid(Polygon(ring(q))) for q in ps[1:]]);shapes.append(a.difference(b))
  planes[layer]=unary_union(shapes)
 return planes
