"""Independent continuous geometry check before a recoverable native trial."""
from pathlib import Path
import json,math,re,sys
from exchange import read,OUT,sha
from four_layer_geometry import copper,connected
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
cp,pcb,work=read();plan=json.loads((OUT/'plan.json').read_text());fan=json.loads((OUT/'bus-escapes.json').read_text())
route={k:plan[k]+fan[k] for k in ['lines','vias']}
trunks=None
if '--trunks' in sys.argv:
 trunks=json.loads((OUT/'grid-trunks.json').read_text())
 assert trunks['plan_sha256']==sha(OUT/'plan.json') and trunks['fanout_sha256']==sha(OUT/'bus-escapes.json')
 assert any(n['net']=='INPUT_LOAD_N' and n['continuity']['complete'] for n in trunks['nets'])
 for k in ['lines','vias']:
  work[k]+=trunks[k];route[k]+=trunks[k]
quiet=unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+(.6 if p['net'].startswith('I2S_') else .5),quad_segs=32) for p in work['lines'] if p['layer']==2 and (p['net'].startswith('I2S_') or re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net']))])
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
edge=box(0,0,140,100).boundary;checks={};fail=[];nets=[]
for net in sorted({p['net'] for k in route for p in route[k]}):
 f,pads=copper(work,net);foreign={l:unary_union(q) for l,q in f.items()};allforeign=unary_union(list(foreign.values()));allpads=unary_union(pads)
 def check(kind,gap,minimum):
  checks[kind]=min(checks.get(kind,math.inf),gap)
  if gap<minimum-1e-7:fail.append(dict(net=net,criterion=kind,gap_mm=gap,minimum_mm=minimum))
 for p in [p for p in route['lines'] if p['net']==net]:
  assert p['width']>=6 and p['layer'] in [1,2,16]
  q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]);radius=p['width']*.0254/2
  check('track_copper',q.distance(foreign[p['layer']])-radius,.158);check('track_mount',q.distance(mount)-radius,.15);check('track_edge',q.distance(edge)-radius,.3)
  if p['layer'] in [2,16]:check('track_quiet',q.distance(quiet)-radius,.158)
 for v in [p for p in route['vias'] if p['net']==net]:
  q=Point(v['x']*.0254,v['y']*.0254);check('via_copper',q.distance(allforeign)-.3048,.158);check('hole_pad',q.distance(allpads)-.1524,.25);check('via_quiet',q.distance(quiet)-.3048,.158);check('via_edge',q.distance(edge)-.3048,.3);check('via_mount',q.distance(mount)-.3048,.15)
  for other in work['vias']:
   if other['net']==v['net'] and math.dist((v['x'],v['y']),(other['x'],other['y']))<1e-6:continue
   check('drill_drill',math.dist((v['x'],v['y']),(other['x'],other['y']))*.0254-(v['hole']+other['hole'])*.0254/2,.35)
 proof=connected([p for p in work['pads'] if p['net']==net],[p for p in work['lines'] if p['net']==net],[p for p in work['vias'] if p['net']==net])
 required={'5V_PERIPH','3V3_IO','PRESET1'}|({n['net'] for n in trunks['nets']} if trunks else set())
 if net in required and not proof['complete']:fail.append(dict(net=net,continuity=proof))
 nets.append(dict(net=net,continuity=proof))
audit=dict(source_pcb_sha256=cp['pcb_sha256'],minimum_clearances_mm=checks,failures=fail,nets=nets,geometric_pass=not fail,required_recovery_nets=plan['required_recovery_nets'],manufacturing_release=False)
if trunks:
 (OUT/'complete-trunk-preflight.json').write_text(json.dumps(audit,indent=2))
else:
 (OUT/'native-trial-preflight.json').write_text(json.dumps(audit,indent=2));(OUT/'native-trial-copper.json').write_text(json.dumps({**route,'remove_lines':plan['remove_lines'],'remove_vias':plan['remove_vias']},indent=2))
assert sha(pcb)==cp['pcb_sha256'];print(json.dumps(audit,indent=2),flush=True)
