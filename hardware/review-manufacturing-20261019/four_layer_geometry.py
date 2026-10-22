"""Physical copper and connectivity for four native layers; no projected joins."""
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
from physical_geometry import actual_pad
LAYERS=(1,15,16,2)
def copper(data,net):
 f={l:[] for l in LAYERS};pads=[]
 for p in data['pads']:
  if p['id'].startswith('anchor-'):continue
  q=actual_pad(p);pads.append(q)
  if p['net']!=net:
   for l in LAYERS if p['layer']==12 else [p['layer']]:
    if l in f:f[l].append(q)
 for p in data['lines']:
  if p['net']!=net and p['layer'] in f:f[p['layer']].append(LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,resolution=32))
 for p in data['vias']:
  if p['net']==net:continue
  q=Point(p['x']*.0254,p['y']*.0254).buffer(p['diameter']*.0254/2,resolution=32)
  for l in LAYERS:f[l].append(q)
 return f,pads

def connected(pads,lines,vias):
 mask={1:1,15:2,16:4,2:8,12:15};obs=[]
 for p in pads:obs.append((mask[p['layer']],actual_pad(p),'pad',p))
 n=len(obs)
 for p in lines:obs.append((mask[p['layer']],LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,resolution=32),'line',p))
 for p in vias:obs.append((15,Point(p['x']*.0254,p['y']*.0254).buffer(p['diameter']*.0254/2,resolution=32),'via',p))
 parent=list(range(len(obs)))
 def root(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 for i,(m,q,k,p) in enumerate(obs):
  for j in range(i):
   if m&obs[j][0] and root(i)!=root(j) and q.distance(obs[j][1])<=.003:parent[root(i)]=root(j)
 islands={root(i) for i in range(n)}
 return dict(complete=n>=2 and len(islands)==1,pad_islands=len(islands))
