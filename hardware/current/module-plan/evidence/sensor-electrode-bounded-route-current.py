"""One finite offline all14 group probe; no CAD API, no source writes or retries."""
from pathlib import Path
import json,sys,time,heapq,math,datetime,hashlib
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import numpy as np
from shapely import intersects_xy,union_all,from_wkb
from shapely.geometry import Point,LineString,box
from shapely.affinity import rotate

E=Path(__file__).parent
out=E/'sensor-electrode-bounded-route-current.json'
assert not out.exists(), 'Terminal offline probe already exists. Read it; do not replay.'
plan=json.loads((E/'sensor-electrode-channel-plan-current.json').read_text())
assert plan['candidate_bridge_physical_and_full_width_reference_pass']
source=E/'sensor-front-14nets-current.epcb2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(source)==plan['source_sha256']
pads=json.loads((E/'sensor-front-exact-source-pads-14nets-current.json').read_text())['pads']
by={(p['ref'],p['pin']):p for p in pads}
for ch in plan['proposed_pad_net_changes']:
 p=by[(ch['ref'],ch['pin'])];assert p['net']==ch['old'];p['net']=ch['proposed']
actual=json.loads((E/'sensor-front-native-14nets-reopened-DRC-current.json').read_text())['value']
def shape(p):
 s=p['shape'];w=s['width']*.0254;h=s['height']*.0254
 return Point(p['x_mm'],p['y_mm']).buffer(w/2,quad_segs=32) if s['padType']=='ELLIPSE' and abs(w-h)<1e-6 else rotate(box(p['x_mm']-w/2,p['y_mm']-h/2,p['x_mm']+w/2,p['y_mm']+h/2),p['angle'],origin=(p['x_mm'],p['y_mm']))
obs=[(p['ref']+'.'+p['pin'],p['net'],shape(p),.1651) for p in pads]
for t in actual['lines']:obs.append((t['primitiveId'],t['net'],LineString([(t['startX']*.0254,t['startY']*.0254),(t['endX']*.0254,t['endY']*.0254)]).buffer(t['lineWidth']*.0254/2,quad_segs=32),.1651))
for v in actual['vias']:obs.append((v['primitiveId'],v['net'],Point(v['x']*.0254,v['y']*.0254).buffer(v['diameter']*.0254/2,quad_segs=32),.2501))
width=.1651;step=.1
for b in plan['candidate14_ESD_external_bridge_checks']:obs.append(('bridge:'+b['net'],b['net'],LineString([b['start'],b['end']]).buffer(width/2,quad_segs=32),.1651))
nx,ny=551,451
xx,yy=np.meshgrid(np.arange(nx)*step,np.arange(ny)*step)
dirs=[(1,0,1),(-1,0,1),(0,1,1),(0,-1,1),(1,1,2**.5),(1,-1,2**.5),(-1,1,2**.5),(-1,-1,2**.5)]
def metric(x,y,gx,gy):
 dx=abs(x-gx);dy=abs(y-gy);return max(dx,dy)+(2**.5-1)*min(dx,dy)
results=[];total_expanded=0;started=time.monotonic()
def route(net,a,b,tag):
 global total_expanded
 blocked_geom=union_all([o.buffer(c+width/2+1e-5,quad_segs=8) for nm,n,o,c in obs if n!=net])
 block=intersects_xy(blocked_geom,xx,yy)
 block[:3,:]=True;block[-3:,:]=True;block[:,:3]=True;block[:,-3:]=True
 sx,sy=[round(v/step) for v in a];gx,gy=[round(v/step) for v in b]
 if block[sy,sx] or block[gy,gx]:return dict(net=net,tag=tag,state='ENDPOINT_GRID_BLOCKED',expanded=0,start=a,end=b)
 start=sy*nx+sx;goal=gy*nx+gx
 dist={start:0.};prev={};q=[(metric(sx,sy,gx,gy),0.,start)];expanded=0;found=False
 while q and expanded<160000 and time.monotonic()-started<105:
  _,g,k=heapq.heappop(q)
  if g!=dist.get(k):continue
  if k==goal:found=True;break
  expanded+=1;x=k%nx;y=k//nx
  for dx,dy,cost in dirs:
   tx=x+dx;ty=y+dy
   if tx<0 or tx>=nx or ty<0 or ty>=ny or block[ty,tx]:continue
   if dx and dy and (block[y,tx] or block[ty,x]):continue
   k2=ty*nx+tx;ng=g+cost
   if ng+1e-10<dist.get(k2,1e20):
    dist[k2]=ng;prev[k2]=k;heapq.heappush(q,(ng+metric(tx,ty,gx,gy),ng,k2))
 total_expanded+=expanded
 if not found:return dict(net=net,tag=tag,state='BOUNDED_NO_PATH',expanded=expanded,start=a,end=b,global_time_limit_seconds=105,per_branch_expansion_limit=160000)
 keys=[goal]
 while keys[-1]!=start:keys.append(prev[keys[-1]])
 points=[tuple(a)]+[(k%nx*step,k//nx*step) for k in reversed(keys)]+[tuple(b)]
 simple=[]
 for p in points:
  if simple and math.dist(simple[-1],p)<1e-8:continue
  while len(simple)>=2 and abs((simple[-1][0]-simple[-2][0])*(p[1]-simple[-1][1])-(simple[-1][1]-simple[-2][1])*(p[0]-simple[-1][0]))<1e-10:simple.pop()
  simple.append(p)
 cu=LineString(simple).buffer(width/2,quad_segs=64)
 bad=[dict(other=nm,actual=cu.distance(o),required=c) for nm,n,o,c in obs if n!=net and cu.distance(o)<c-1e-8]
 if not bad:obs.append(('route:'+net+':'+tag,net,cu,.1651))
 return dict(net=net,tag=tag,state='PHYSICAL_PASS' if not bad else 'POSTCHECK_REJECTED',expanded=expanded,points=simple,length_mm=LineString(simple).length,violations=bad)

order=json.loads((E/'sensor-front-electrode-whole-channel-order-current.json').read_text())['nets']
for row in order:
 h=by[('J1',row['header']['pin'])];d=by[(row['ESD']['ref'],row['ESD']['pin'])]
 r=route(row['net'],[h['x_mm'],h['y_mm']],[d['x_mm'],d['y_mm']],'header_to_ESD');results.append(r)
 print(row['net'],r['tag'],r['state'],flush=True)
 if r['state']!='PHYSICAL_PASS':break
if len(results)==14 and all(r['state']=='PHYSICAL_PASS' for r in results):
 for row in order:
  net=row['net'];bridge=next(b for b in plan['candidate14_ESD_external_bridge_checks'] if b['net']==net)
  p=next(p for p in pads if p['ref'].startswith('R') and p['pin']=='1' and p['net']==net)
  r=route(net,bridge['end'],[p['x_mm'],p['y_mm']],'ESD_to_seriesR');results.append(r)
  print(net,r['tag'],r['state'],flush=True)
  if r['state']!='PHYSICAL_PASS':break

gnd=from_wkb((E/'sensor-front-real-bottom-ground-14nets-current.wkb').read_bytes())
for r in results:
 if r['state']=='PHYSICAL_PASS':
  cu=LineString(r['points']).buffer(width/2,quad_segs=64)
  r['full_width_reference_missing_mm2']=cu.difference(gnd).area
  r['reference_accepted']=False  # TH antipad/terminal transition and all-source DC audit still pending.
full=len(results)==28 and all(r['state']=='PHYSICAL_PASS' for r in results)
result=dict(at=datetime.datetime.now().astimezone().isoformat(),source_sha256=plan['source_sha256'],state='TERMINAL_OFFLINE_BOUNDED_GROUP_PROBE',elapsed_seconds=time.monotonic()-started,total_expanded=total_expanded,step_mm=step,width_mm=width,branches=results,all28branches_physical_pass=full,full_group_routing_accepted=False,reference_and_DC_audit_pending=True,native_applied=False,native_route_rerun=False,physical_tests='UNMEASURED',manufacturing_release=False,stop_reason='First failed branch or complete group; no ripup/no permutations/no parallel geometry/no retry. Failure does not prove global impossibility.')
assert sha(source)==plan['source_sha256']
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='branches'},ensure_ascii=False))
