"""Screen a joint top fanout change without cutting either reference plane."""
from pathlib import Path
import sys,json,copy,math
B=Path(__file__).resolve().parent;R=B.parent;O=B/'mosi'
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(R))
from four_layer_geometry import copper
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
s=json.loads((B/'checkpoint-capture.json').read_text(encoding='utf8'))
rl=[p for p in s['lines'] if p['id'] in ['3046abffee283114','fffcd717d6e4eb35','e5e71fbe3d180937','afe6a618ca2230a3']]
rv=[p for p in s['vias'] if p['id'] in ['d2cb5aee0e210038','14251fb9fdd18053'] or (p['net']=='GND' and math.dist([p['x']*.0254,p['y']*.0254],[64.023099,49.133125])<.001)]
assert len(rl)==4 and len(rv)==3
w=copy.deepcopy(s);w['lines']=[p for p in w['lines'] if p not in rl];w['vias']=[p for p in w['vias'] if p not in rv]
fs={};ps={}
for net in ['BUS_SCK','BUS_MOSI']:
 f,p=copper(w,net);fs[net]={l:unary_union(gs) for l,gs in f.items()};ps[net]=unary_union(p)
def line(net,layer,a,b):return dict(net=net,layer=layer,x1=a[0]/.0254,y1=a[1]/.0254,x2=b[0]/.0254,y2=b[1]/.0254,width=6)
def path(net,layer,pts):return [line(net,layer,a,b) for a,b in zip(pts,pts[1:])]
def valid(ls,vs):
 for p in ls:
  q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)])
  if q.distance(fs[p['net']][p['layer']])-.0762<.158: return False
 for p in vs:
  q=Point(p['x']*.0254,p['y']*.0254)
  if min(q.distance(g) for g in fs[p['net']].values())-.3048<.158 or q.distance(ps[p['net']])-.1524<.25:return False
  if any(math.dist((p['x'],p['y']),(v['x'],v['y']))*.0254-(12+v['hole'])*.0254/2<.35 for v in w['vias']):return False
 for a in ls+vs:
  ag=LineString([(a['x1']*.0254,a['y1']*.0254),(a['x2']*.0254,a['y2']*.0254)]).buffer(.0762) if 'layer' in a else Point(a['x']*.0254,a['y']*.0254).buffer(.3048)
  for b in ls+vs:
   if a['net']==b['net'] or ('layer' in a and 'layer' in b and a['layer']!=b['layer']):continue
   bg=LineString([(b['x1']*.0254,b['y1']*.0254),(b['x2']*.0254,b['y2']*.0254)]).buffer(.0762) if 'layer' in b else Point(b['x']*.0254,b['y']*.0254).buffer(.3048)
   if ag.distance(bg)<.158:return False
 return True
found=[]
for x in [65.05+i*.025 for i in range(45)]:
 for y in [48.25+i*.025 for i in range(16)]:
  cv=dict(net='BUS_SCK',x=x/.0254,y=y/.0254,diameter=24,hole=12,id='new-u8-clock')
  clock=path('BUS_SCK',1,[(65.90538,47.73422),(x,y)])+path('BUS_SCK',16,[(63.4,51.75),(x,y),(69.25,47.4)])
  # Existing clock endpoints in native coordinates, no grid rounded substitution.
  clock[1]['x1']=next(p for p in rl if p['id']=='e5e71fbe3d180937')['x1'];clock[1]['y1']=next(p for p in rl if p['id']=='e5e71fbe3d180937')['y1']
  clock[2]['x2']=next(p for p in rl if p['id']=='afe6a618ca2230a3')['x2'];clock[2]['y2']=next(p for p in rl if p['id']=='afe6a618ca2230a3')['y2']
  if not valid(clock,[cv]):continue
  for mx in [66.3+i*.025 for i in range(11)]:
   mv=dict(net='BUS_MOSI',x=mx/.0254,y=49.15/.0254,diameter=24,hole=12,id='new-u8-mosi')
   ls=clock+path('BUS_MOSI',1,[(62.09538,47.73422),(62.65,48.86),(62.8,49.15),(mx,49.15)])
   if valid(ls,[cv,mv]):found.append(dict(lines=ls,vias=[cv,mv],score=math.dist((x,y),(65.325,48.85))))
found.sort(key=lambda p:p['score'])
result=dict(source_pcb_sha256='8b9b68a5f42a446b2c716e41d6693f480fb9c8048e6c1c7080b151244978aa19',remove_lines=rl,remove_vias=rv,options=found)
(O/'joint-escape-options.json').write_text(json.dumps(result,indent=2),encoding='utf8');print('JOINT OPTIONS',len(found));print(json.dumps(found[:1],indent=2),flush=True)

# Alternate local co-optimization at U15: its old inward data via sits in a
# sealed region. Move the neighbouring backlight via and clock approach to
# permit an outward data escape; no rule/layer/component/BOM changes.
rl=[p for p in s['lines'] if p['id'] in ['1d8c6af9bf673d26','8f52d8eaf27bb5be','8de81cfdb1b577da','fafc8ecf022f3fdb','c12ef6a21505564a']]
rv=[p for p in s['vias'] if p['id'] in ['4c8de6ab447ab4b8','f55f8ab4f2bf21ba'] or (p['net']=='GND' and math.dist([p['x']*.0254,p['y']*.0254],[79.2,45.7])<.25)]
w=copy.deepcopy(s);w['lines']=[p for p in w['lines'] if p not in rl];w['vias']=[p for p in w['vias'] if p not in rv]
fs={};ps={}
for net in ['BUS_SCK','BUS_MOSI','VIS_BL_EN']:
 f,p=copper(w,net);fs[net]={l:unary_union(gs) for l,gs in f.items()};ps[net]=unary_union(p)
oldclock=next(p for p in rl if p['id']=='c12ef6a21505564a');oldbl=next(p for p in rl if p['id']=='fafc8ecf022f3fdb');oldfan=next(p for p in rl if p['id']=='8f52d8eaf27bb5be')
found=[]
for mx in [79.7+i*.05 for i in range(9)]:
 for by in [44.65+i*.05 for i in range(8)]:
  mv=dict(net='BUS_MOSI',x=mx/.0254,y=43.975/.0254,diameter=24,hole=12,id='new-u15-mosi')
  bv=dict(net='VIS_BL_EN',x=mx/.0254,y=by/.0254,diameter=24,hole=12,id='new-u15-bl')
  for cy in [45.25+i*.05 for i in range(7)]:
   ls=path('BUS_MOSI',1,[(81.1276,43.97502),(mx,43.975)])+path('VIS_BL_EN',1,[(oldfan['x1']*.0254,oldfan['y1']*.0254),(mx,by)])+path('VIS_BL_EN',16,[(oldbl['x1']*.0254,oldbl['y1']*.0254),(mx,by)])+path('BUS_SCK',1,[(oldclock['x1']*.0254,oldclock['y1']*.0254),(79.7,cy),(80.5,cy),(81.1276,45.2755)])
   if valid(ls,[mv,bv]):found.append(dict(lines=ls,vias=[mv,bv],score=abs(cy-45.1)+abs(by-44.775)))
found.sort(key=lambda p:p['score'])
(O/'u15-escape-options.json').write_text(json.dumps(dict(remove_lines=rl,remove_vias=rv,options=found),indent=2),encoding='utf8');print('U15 OPTIONS',len(found));print(json.dumps(found[:1],indent=2),flush=True)
if not found:
 for p in ls:
  q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)])
  print('TRACK GAP',p['net'],p['layer'],q.distance(fs[p['net']][p['layer']])-.0762)
 for p in [mv,bv]:
  q=Point(p['x']*.0254,p['y']*.0254)
  print('VIA GAP',p['net'],{l:q.distance(g)-.3048 for l,g in fs[p['net']].items()},'PAD',q.distance(ps[p['net']])-.1524)
