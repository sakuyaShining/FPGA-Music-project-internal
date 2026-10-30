from pathlib import Path
import sys,json,re,math,hashlib,collections,copy
from native_documents import documents
from shapely.geometry import Point,LineString,Polygon
from shapely.affinity import translate
from shapely.strtree import STRtree
O=Path(__file__).parent
P=O/'FPGA-Music-Control88-ROUTING-CANDIDATE/pcb/PCB1.epcb2'
LAYERS={'TopLayer':1,'Inner1':15,'Inner2':16,'BottomLayer':2}
def parse(s):
 stack=[];root=None
 for t in re.findall(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()]+',s):
  if t=='(':
   n=[]
   if stack:stack[-1].append(n)
   else:assert root is None;root=n
   stack.append(n)
  elif t==')':stack.pop()
  else:stack[-1].append(json.loads(t) if t.startswith('"') else t)
 assert not stack;return root
child=lambda n,k:next(v for v in n if isinstance(v,list) and v[0]==k)
def load(p=P):
 ds=documents(p);b=next(d for d in ds if d['head']['docType']=='PCB');return ds,b

def objects(b):
 dsn=parse((O/'native-fourlayer.dsn').read_text());lib=child(dsn,'library');stacks={}
 for v in lib[1:]:
  if v[0]!='padstack':continue
  ss=[]
  for sh in v[2:]:
   if sh[0]!='shape':continue
   s=sh[1];layer=LAYERS[s[1]]
   if s[0]=='circle':g=Point(float(s[3]) if len(s)>3 else 0,float(s[4]) if len(s)>4 else 0).buffer(float(s[2])/2,quad_segs=64)
   elif s[0]=='polygon':g=Polygon(list(zip(map(float,s[3::2]),map(float,s[4::2])))).buffer(float(s[2])/2,quad_segs=16)
   else:raise ValueError(s[0])
   ss.append((layer,g))
  stacks[v[1]]=ss
 pins={v[2]:v for v in child(lib,'image')[2:] if v[0]=='pin'}
 nets={};refs={}
 at=collections.defaultdict(dict)
 for h,v in b['records']:
  if h['type']=='ATTR':at[v['parentId']][v['key']]=v['value']
 for h,v in b['records']:
  if h['type']=='PAD_NET':
   _,cid,pad,pid=json.loads(h['id']);key=(cid+pid).replace('e','',1);assert key not in nets
   nets[key]=v['padNet'];refs[key]=at[cid]['Designator']+'.'+pad
 assert set(nets)==set(pins),(list(set(nets)-set(pins))[:5],list(set(pins)-set(nets))[:5])
 obs=[]
 for pid,p in pins.items():
  for layer,g in stacks[p[1]]:obs.append(dict(id=pid,ref=refs[pid],kind='PAD',net=nets[pid],layer=layer,g=translate(g,float(p[3]),float(p[4]))))
 for h,v in b['records']:
  if h['type']=='LINE':obs.append(dict(id=h['id'],kind='LINE',net=v['netName'],layer=v['layerId'],g=LineString([(v['startX'],v['startY']),(v['endX'],v['endY'])]).buffer(v['width']/2,quad_segs=32)))
  elif h['type']=='VIA':
   for layer in LAYERS.values():obs.append(dict(id=h['id'],kind='VIA',net=v['netName'],layer=layer,g=Point(v['centerX'],v['centerY']).buffer(v['viaDiameter']/2,quad_segs=64)))
 return obs

def audit(b):
 obs=objects(b);errors=[];parent=list(range(len(obs)))
 def root(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 for layer in LAYERS.values():
  ids=[i for i,x in enumerate(obs) if x['layer']==layer];gs=[obs[i]['g'] for i in ids];tree=STRtree(gs)
  for pos,i in enumerate(ids):
   a=obs[i]
   for jj in tree.query(a['g'].buffer(6.3)):
    j=ids[int(jj)]
    if j<=i:continue
    bb=obs[j];dist=a['g'].distance(bb['g'])
    if a['net'] and a['net']==bb['net']:
     if dist<.02:parent[root(i)]=root(j)
    elif dist<5.98 and not(a['kind']==bb['kind']=='PAD'):
     errors.append({'a':{k:v for k,v in a.items() if k!='g'},'b':{k:v for k,v in bb.items() if k!='g'},'gap_mil':dist})
 # Join plated pads and through vias between layers.
 groups=collections.defaultdict(list)
 for i,x in enumerate(obs):
  if x['kind']in['PAD','VIA']:groups[(x['kind'],x['id'])].append(i)
 for ids in groups.values():
  for i in ids[1:]:parent[root(i)]=root(ids[0])
 netpads=collections.defaultdict(set)
 for i,x in enumerate(obs):
  if x['kind']=='PAD' and x['net']:netpads[x['net']].add(root(i))
 return {'clearance_errors':errors,'unconnected_nets':{n:len(cs) for n,cs in netpads.items() if len(cs)>1},'net_count':len(netpads)}
if __name__=='__main__':
 _,b=load();r=audit(b);(O/'independent-before-repair.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r,indent=2))



