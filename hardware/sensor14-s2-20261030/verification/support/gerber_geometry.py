from sensor_geometry import *
from shapely.ops import unary_union
import re
def gerber_regions(file):
 text=file.read_text();assert '%LP' not in text
 aps={int(a):(shape,list(map(float,d.split('X')))) for a,shape,d in re.findall(r'%ADD(\d+)([CRO]),([0-9.X]+)',text)}
 regions=[];paths=[];path=[];active=False;x=y=0.;ap=None;mode=1
 for token in text.split('*'):
  t=token.strip()
  if t=='G36':active=True;paths=[];path=[];continue
  if t=='G37':
   if path:paths.append(path)
   g=None
   for pp in paths:
    if len(pp)<3:continue
    pg=Polygon(pp).buffer(0);g=pg if g is None else g.symmetric_difference(pg)
   if g is not None:regions.append(g)
   active=False;continue
  dm=re.fullmatch(r'(?:G54)?D(\d+)',t)
  if dm:ap=int(dm[1]);continue
  m=re.fullmatch(r'(?:G0([123]))?(?:X(-?\d+))?(?:Y(-?\d+))?(?:I(-?\d+))?(?:J(-?\d+))?D0([123])',t)
  if not m:continue
  if m[1]:mode=int(m[1])
  nx=float(m[2])/1e5 if m[2] else x;ny=float(m[3])/1e5 if m[3] else y;code=m[6]
  vertices=[(nx,ny)]
  if code=='1' and mode in [2,3]:
   cx=x+(float(m[4])/1e5 if m[4] else 0);cy=y+(float(m[5])/1e5 if m[5] else 0);start=math.atan2(y-cy,x-cx);end=math.atan2(ny-cy,nx-cx);sweep=(end-start)%(2*math.pi)
   if mode==2:sweep=-((start-end)%(2*math.pi))
   if abs(sweep)<1e-12:sweep=2*math.pi*(1 if mode==3 else -1)
   rad=math.hypot(x-cx,y-cy);n=max(4,math.ceil(abs(sweep)/(2*math.pi)*2048));vertices=[(cx+rad*math.cos(start+sweep*i/n),cy+rad*math.sin(start+sweep*i/n)) for i in range(1,n+1)];vertices[-1]=(nx,ny)
  if active:
   if code=='2':
    if path:paths.append(path)
    path=[(nx,ny)]
   elif code=='1':path.extend(vertices)
   else:raise ValueError('Flash within region')
  elif code=='1':
   shape,d=aps[ap];assert shape=='C'
   regions.append(LineString([(x,y)]+vertices).buffer(d[0]/2,quad_segs=128))
  elif code=='3':
   shape,d=aps[ap]
   if shape=='C':g=Point(nx,ny).buffer(d[0]/2,quad_segs=128)
   elif shape=='R':g=box(nx-d[0]/2,ny-d[1]/2,nx+d[0]/2,ny+d[1]/2)
   else:
    w,h=d[:2];g=LineString([(nx-max(0,w-h)/2,ny-max(0,h-w)/2),(nx+max(0,w-h)/2,ny+max(0,h-w)/2)]).buffer(min(w,h)/2,quad_segs=128)
   regions.append(g)
  x,y=nx,ny
 return unary_union(regions)
