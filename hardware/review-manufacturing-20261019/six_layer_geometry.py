"""Explicit six-layer copper/connectivity; no projected layer joins."""
from shapely.geometry import Point,LineString
from physical_geometry import actual_pad
LAYERS=(1,15,16,17,18,2)
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
 masks={l:1<<i for i,l in enumerate(LAYERS)};masks[12]=63;obs=[(masks[p['layer']],actual_pad(p)) for p in pads];n=len(obs)
 obs +=[(masks[p['layer']],LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,resolution=32)) for p in lines]
 obs +=[(63,Point(p['x']*.0254,p['y']*.0254).buffer(p['diameter']*.0254/2,resolution=32)) for p in vias];parent=list(range(len(obs)))
 def root(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 for i,(m,q) in enumerate(obs):
  for j in range(i):
   if m&obs[j][0] and root(i)!=root(j) and q.distance(obs[j][1])<=.003:parent[root(i)]=root(j)
 return dict(complete=n>=2 and len({root(i) for i in range(n)})==1,pad_islands=len({root(i) for i in range(n)}))
