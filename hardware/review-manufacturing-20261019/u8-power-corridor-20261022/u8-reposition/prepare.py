"""Source-bound U8/C8/R63 layout candidate. Preparation only; no native edit."""
from pathlib import Path
import sys,json,copy,ast,math,heapq
O=Path(__file__).resolve().parent;B=O.parent;R=B.parent
P=B/'u2-layout-coopt/full-bundle/critical-first/address0-backbone'
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path[:0]=[str(R),str(B)]
from physical_geometry import actual_pad
from four_layer_geometry import copper,connected
from reserve_escape import reserve
from shapely.geometry import Point,LineString,box
from shapely.affinity import translate
from shapely.ops import unary_union
rd=lambda p:json.loads(p.read_text(encoding='utf8'))
wr=lambda p,v:p.write_text(json.dumps(v,indent=2),encoding='utf8')
assert not (O/'layout-plan.json').exists(),'Inspect existing candidate; do not overwrite'
s=rd(P/'routed-capture.json');w=copy.deepcopy(s);cp=rd(R/'REGIONAL-WORK-IN-PROGRESS.json')
prefix=(B/'mosi_prepare.py').read_text(encoding='utf8').split("cid=cid_by_ref['R64']")[0]
t=ast.parse(prefix);t.body=[n for n in t.body if not isinstance(n,ast.Assert)];d={'__file__':str(B/'mosi_prepare.py')};exec(compile(t,'footprint-boxes-only','exec'),d)
oldc8=[p for p in s['pads'] if p['ref']=='C8'];cx=sum(p['x'] for p in oldc8)/2*.0254;cy=sum(p['y'] for p in oldc8)/2*.0254
delta={'U8':(3,-.25),'C8':(63-cx,49.56-cy),'R63':(1,0)}
boxes=d['boxes'];boxes['U2']=translate(boxes['U2'],yoff=-2);boxes['C2']=translate(boxes['C2'],yoff=-2)
for ref,(dx,dy) in delta.items():boxes[ref]=translate(boxes[ref],xoff=dx,yoff=dy)
body=[]
for ref in delta:
 near=sorted((boxes[ref].distance(q),other) for other,q in boxes.items() if other!=ref);body.append(dict(ref=ref,nearest=near[:5]));print('BODY',ref,near[:3],flush=True);assert near[0][0]>=.25
w['pads']=[{**p,'x':p['x']+delta[p['ref']][0]/.0254,'y':p['y']+delta[p['ref']][1]/.0254} if p['ref'] in delta else p for p in s['pads']]
key=lambda x,y:(round(x,1),round(y,1));remove={};vremove={};anchors={};paths={}
def walk(pad):
 net=pad['net'];ls=[p for p in s['lines'] if p['net']==net and p['layer']==1];adj={}
 for p in ls:
  a,b=key(p['x1'],p['y1']),key(p['x2'],p['y2']);length=math.dist(a,b)*.0254;adj.setdefault(a,[]).append((b,length,p));adj.setdefault(b,[]).append((a,length,p))
 start=min(adj,key=lambda q:math.dist(q,(pad['x'],pad['y'])));assert math.dist(start,(pad['x'],pad['y']))*.0254<.003
 vkeys={key(v['x'],v['y']):v for v in s['vias'] if v['net']==net};queue=[(0,start,[])];seen=set()
 while queue:
  dist,node,path=heapq.heappop(queue)
  if dist>25:break
  if node in seen:continue
  seen.add(node)
  if node in vkeys:return vkeys[node],path
  for other,length,line in adj.get(node,[]):
   if other not in seen:heapq.heappush(queue,(dist+length,other,path+[line]))
 raise RuntimeError('No bounded source escape '+pad['ref']+'.'+pad['n'])
for pad in [p for p in s['pads'] if p['ref']=='U8' and p['net'] in ['RC_DRIVE','LCD_RESET_N','TP_RESET_N','SCAN_LATCH','BUS_MOSI']]:
 via,path=walk(pad);anchors[pad['net']]=via;paths[pad['net']]=path
 for p in path:remove[p['id']]=p
 vremove[via['id']]=via
# C8 power is a leaf joined to the existing rail mid-segment, rather than a
# standalone pad-to-via fanout. Remove its actual pad-connected top segment.
cap_power=next(p for p in oldc8 if p['net']=='3V3_IO')
for p in s['lines']:
 if p['net']=='3V3_IO' and p['layer']==1 and min(math.dist((p['x1'],p['y1']),(cap_power['x'],cap_power['y'])),math.dist((p['x2'],p['y2']),(cap_power['x'],cap_power['y'])))*.0254<.003:remove[p['id']]=p
ls=[p for p in s['lines'] if p['net']=='GND' and p['layer']==1];adj={};vkeys={key(v['x'],v['y']) for v in s['vias'] if v['net']=='GND'}
for p in ls:
 a,b=key(p['x1'],p['y1']),key(p['x2'],p['y2']);adj.setdefault(a,[]).append((b,p));adj.setdefault(b,[]).append((a,p))
for pad in [p for p in s['pads'] if p['ref'] in delta and p['net']=='GND']:
 start=min(adj,key=lambda q:math.dist(q,(pad['x'],pad['y'])));queue=[(start,0.)];seen=set()
 if math.dist(start,(pad['x'],pad['y']))*.0254>=.003:
  # A ground pour or pad-edge contact need not terminate at the pad center.
  touches=[p for p in ls if LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).distance(actual_pad(pad))<=p['width']*.0254/2+.003]
  if not touches:continue
  queue=[]
  for p in touches:
   remove[p['id']]=p;queue.extend([(key(p['x1'],p['y1']),0.),(key(p['x2'],p['y2']),0.)])
 while queue:
  node,dist=queue.pop()
  if node in seen or dist>12:continue
  seen.add(node)
  if node!=start and (node in vkeys or len(adj.get(node,[]))>2):continue
  for other,line in adj.get(node,[]):remove[line['id']]=line;queue.append((other,dist+math.dist(node,other)*.0254))
old10=next(p for p in s['pads'] if p['ref']=='U8' and p['n']=='10')
for p in s['lines']:
 if p['net']=='3V3_IO' and p['layer']==1 and min(math.dist((p['x1'],p['y1']),(old10['x'],old10['y'])),math.dist((p['x2'],p['y2']),(old10['x'],old10['y'])))*.0254<.003:remove[p['id']]=p
rail=next(p for p in s['lines'] if p.get('id')=='6e6945216e6a98a0');remove[rail['id']]=rail
oldav=next(p for p in s['vias'] if p['net']=='ADDR0' and math.dist((p['x']*.0254,p['y']*.0254),(61.4,48.825))<.01)
oldal=[p for p in s['lines'] if p['net']=='ADDR0' and p['layer']==1 and LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).intersects(box(59,46,63,50))]
w['lines']=[p for p in w['lines'] if p.get('id') not in remove and p not in oldal and p['net']!='BUS_SCK'];w['vias']=[p for p in w['vias'] if p.get('id') not in vremove and p!=oldav and p['net']!='BUS_SCK']
ss={**s,'pads':[p for p in s['pads'] if p['ref'] not in ['U8','R63']]};esc=reserve(ss,w,'BUS_SCK');w['pads']=[{k:v for k,v in p.items() if k!='routing_pad_exclude'} for p in w['pads'] if not p['id'].startswith('anchor-')]
added=[];vias=[]
def ln(net,a,b,width):return dict(net=net,layer=1,x1=a[0]/.0254,y1=a[1]/.0254,x2=b[0]/.0254,y2=b[1]/.0254,width=width)
p16=next(p for p in w['pads'] if p['ref']=='U8' and p['n']=='16');p10=next(p for p in w['pads'] if p['ref']=='U8' and p['n']=='10');x16=p16['x']*.0254;x10=p10['x']*.0254
added+=[ln('3V3_IO',(59.55538,49.84999936),(x16,49.84999936),15.74),ln('3V3_IO',(x16,49.84999936),(x16,46),15.74),ln('3V3_IO',(x16,46),(x10,46),15.74),ln('3V3_IO',(x10,46),(p10['x']*.0254,p10['y']*.0254),15.74)]
for ref,n,xy,wire in [('C8','2',(64.65,49.56),True),('U8','13',(66.55,48.9),True),('U8','8',(71.44538,43.55),True),('U8','13',(69.35,48.9),False),('R63','2',(75.7,44.20108),True)]:
 p=next(p for p in w['pads'] if p['ref']==ref and p['n']==n);vias.append(dict(net='GND',x=xy[0]/.0254,y=xy[1]/.0254,diameter=24,hole=12))
 if wire:added.append(ln('GND',(p['x']*.0254,p['y']*.0254),xy,8))
for n,net,xy in [('15','ADDR0',(64.4,48.575)),('14','BUS_MOSI',(65.65,48.6099988)),('12','SCAN_LATCH',(67.45,48.9)),('11','BUS_SCK',(68.32500016,48.59999882))]:
 p=next(p for p in w['pads'] if p['ref']=='U8' and p['n']==n);vias.append(dict(net=net,x=xy[0]/.0254,y=xy[1]/.0254,diameter=24,hole=12));added.append(ln(net,(p['x']*.0254,p['y']*.0254),xy,6))
w['lines']+=added;w['vias']+=vias;moved=[p for p in w['pads'] if p['ref'] in delta]
for v in list(w['vias']):
 if v.get('id') and v['net'] in ['GND','3V3_IO'] and any(p['net']!=v['net'] and actual_pad(p).distance(Point(v['x']*.0254,v['y']*.0254))-v['diameter']*.0254/2<.1524 for p in moved):vremove[v['id']]=v;w['vias'].remove(v)
fail=[];mins={}
for net in {p['net'] for p in moved}|{p['net'] for p in added}:
 f,ps=copper(w,net);un={l:unary_union(v) for l,v in f.items()};fu=unary_union(list(un.values()));pu=unary_union(ps)
 for p in [p for p in moved if p['net']==net]:
  gap=actual_pad(p).distance(un[1]);mins['moved_pad']=min(mins.get('moved_pad',999),gap)
  if gap<.1524-1e-6:fail.append(dict(kind='moved_pad',ref=p['ref'],pin=p['n'],net=net,gap_mm=gap))
 for p in [p for p in added if p['net']==net]:
  gap=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).distance(un[1])-p['width']*.0254/2;mins['new_track']=min(mins.get('new_track',999),gap)
  if gap<.158-1e-6:fail.append(dict(kind='new_track',net=net,gap_mm=gap,line=p))
 for v in [v for v in vias if v['net']==net]:
  q=Point(v['x']*.0254,v['y']*.0254);gap=q.distance(fu)-.3048;hole=q.distance(pu)-.1524
  if gap<.165-1e-6 or hole<.25-1e-6:fail.append(dict(kind='new_via',net=net,xy_mm=[q.x,q.y],copper_gap_mm=gap,hole_pad_gap_mm=hole))
proof={n:connected([p for p in w['pads'] if p['net']==n],[p for p in w['lines'] if p['net']==n],[p for p in w['vias'] if p['net']==n]) for n in ['3V3_IO','BUS_MOSI']}
report=dict(source_pcb_sha256=cp['pcb_sha256'],changes=[dict(ref=ref,id=d['cid_by_ref'][ref],delta_mm=list(v)) for ref,v in delta.items()],body_checks=body,remove_source_lines=list(remove.values()),remove_source_vias=list(vremove.values()),removed_trial_address_lines=oldal,removed_trial_address_via=oldav,old_control_anchors=anchors,old_control_paths=paths,retained_clock_escapes=esc,lines=added,vias=vias,minimum_clearances_mm=mins,preflight_failures=fail,continuity=proof,native_imported=False,manufacturing_release=False)
wr(O/'layout-plan.json',report);wr(O/'working-capture.json',w)
print(json.dumps(dict(continuity=proof,failures=fail),indent=2),flush=True)
