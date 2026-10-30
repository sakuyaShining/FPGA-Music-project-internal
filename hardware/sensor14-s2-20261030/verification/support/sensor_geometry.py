from pathlib import Path
import sys,json,math,collections,hashlib
import cad_audit as base
from cad_audit import documents,Point,LineString,Polygon,STRtree
from shapely.geometry import box
from shapely.affinity import translate,rotate,scale
O=Path(__file__).resolve().parent.parent.parent;Q=O/'Sensor14Bank-S2-CANDIDATE/pcb/PCB2.epcb2'
def load(p=Q):return base.load(p)
def objects(b):
 ds=documents(Q);libs={d['head']['uuid']:d for d in ds};at=collections.defaultdict(dict);nets={}
 for h,v in b['records']:
  if h['type']=='ATTR':at[v['parentId']][v['key']]=v['value']
  elif h['type']=='PAD_NET':_,cid,num,pid=json.loads(h['id']);nets[cid,pid]=v['padNet']
 obs=[]
 for h,c in b['records']:
  if h['type']!='COMPONENT':continue
  cid=h['id'];ref=at[cid]['Designator'];theta=math.radians(c['angle']);co,si=math.cos(theta),math.sin(theta)
  assert c['layerId']==1
  for hh,p in libs[at[cid]['Footprint']]['records']:
   if hh['type']!='PAD':continue
   shape=p['defaultPad'];w,ht=shape['width'],shape['height'];typ=shape['padType'];x=c['x']+p['centerX']*co-p['centerY']*si;y=c['y']+p['centerX']*si+p['centerY']*co
   if typ=='RECT':g=box(-w/2,-ht/2,w/2,ht/2)
   elif typ=='ELLIPSE':g=scale(Point(0,0).buffer(1,quad_segs=128),w/2,ht/2)
   elif typ=='OVAL':g=LineString([(-max(0,w-ht)/2,-max(0,ht-w)/2),(max(0,w-ht)/2,max(0,ht-w)/2)]).buffer(min(w,ht)/2,quad_segs=128)
   else:raise ValueError(typ)
   g=translate(rotate(g,c['angle']+p['padAngle'],origin=(0,0)),x,y)
   for layer in ([1,15,16,2] if p['layerId']==12 else [p['layerId']]):obs.append(dict(id=cid+hh['id'],ref=ref+'.'+p['num'],kind='PAD',net=nets[cid,hh['id']],layer=layer,g=g))
 for h,v in b['records']:
  if h['type']=='LINE':obs.append(dict(id=h['id'],kind='LINE',net=v['netName'],layer=v['layerId'],g=LineString([(v['startX'],v['startY']),(v['endX'],v['endY'])]).buffer(v['width']/2,quad_segs=64)))
  elif h['type']=='VIA':
   for layer in [1,15,16,2]:obs.append(dict(id=h['id'],kind='VIA',net=v['netName'],layer=layer,g=Point(v['centerX'],v['centerY']).buffer(v['viaDiameter']/2,quad_segs=128)))
 assert len(set(o['id'] for o in obs if o['kind']=='PAD'))==150
 return obs
def audit(b):
 original=base.objects
 try:base.objects=objects;return base.audit(b)
 finally:base.objects=original
if __name__=='__main__':
 _,b=load();r={'pcb_sha256':hashlib.sha256(Q.read_bytes()).hexdigest(),'counts':dict(collections.Counter(h['type'] for h,v in b['records'])),'copper':audit(b)}
 (O/'sensor-independent-geometry.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r,indent=2))
