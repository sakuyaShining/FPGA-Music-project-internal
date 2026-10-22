"""Source-bound plane-aware ADDR3 tree; save every branch before continuing."""
from pathlib import Path
import sys,json,re,math
O=Path(__file__).resolve().parent;D=O.parent;B=D.parent.parent;R=B.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
from shapely.geometry import Polygon,Point,LineString,box
from shapely.ops import unary_union,triangulate
sys.path[:0]=[str(R),str(B)]
import grid_route as g
from four_layer_geometry import copper,connected
rd=lambda p:json.loads(p.read_text(encoding='utf8'))
wr=lambda p,x:p.write_text(json.dumps(x,indent=2),encoding='utf8')
previous=rd(O/'tree-state.json') if (O/'tree-state.json').exists() else None
assert not previous or previous['state']=='terminal_branch_blocked','Inspect existing task; no duplicate run'
w=rd(D/'working-capture.json');nodes=[v for v in w['vias'] if v['net']=='ADDR3'];host=min(range(len(nodes)),key=lambda i:math.dist((nodes[i]['x']*.0254,nodes[i]['y']*.0254),(62.65,41.125)))
fg,ps=copper(w,'ADDR3');ex=unary_union([Point(v['x']*.0254,v['y']*.0254).buffer(1,quad_segs=32) for v in nodes]);guards=[]
for c in rd(B/'interface-closure/reference-voids.json'):
 q=Polygon(c).difference(ex)
 for z in list(q.geoms) if hasattr(q,'geoms') else [q]:
  if z.geom_type!='Polygon' or z.is_empty:continue
  if not z.interiors:guards.append(z)
  else:
   for t in triangulate(z):
    j=t.intersection(z)
    for h in list(j.geoms) if hasattr(j,'geoms') else [j]:
     if h.geom_type=='Polygon' and h.area>1e-8:assert not h.interiors;guards.append(h)
quiet=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+(.6 if p['net'].startswith('I2S_') else .5),quad_segs=16) for p in w['lines'] if p['layer']==2 and (p['net'].startswith('I2S_') or re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net']))]
g.geometries=lambda data,net:({1:fg[1],2:fg[16]+quiet+guards},ps,[box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
g.GRID=.1;g.GAP=.18;g.VIA_COST_MM=5
state=previous or dict(state='running',source_pcb_sha256=rd(D/'classification.json')['source_pcb_sha256'],connected_node_indices=[host],branches=[],native_imported=False,raw_nets_pending_recovery=['L2_M02','L2_M03','L2_M04','L2_M14'])
if previous:
 w=rd(O/'routed-capture.json');state['failed_pairs']=[state.pop('failed_pair')];state['consecutive_failed_branches']=1
state['state']='running';state.setdefault('failed_pairs',[]);state.setdefault('consecutive_failed_branches',0)
wr(O/'tree-state.json',state)
while len(state['connected_node_indices'])<len(nodes):
 step=len(state['branches']);done=state['connected_node_indices'];pairs=sorted((math.dist((nodes[i]['x'],nodes[i]['y']),(nodes[j]['x'],nodes[j]['y'])),i,j) for i in done for j in range(len(nodes)) if j not in done and [i,j] not in state['failed_pairs'])
 _,i,j=pairs[0];w['routing_extra_via_obstacles']=fg[15]+fg[2]+quiet
 try:r=g.search(w,'ADDR3',dict(nodes[i],layer=12),dict(nodes[j],layer=12),20)
 except g.SealedEscape as error:r=None;state['error']=str(error)
 w.pop('routing_extra_via_obstacles',None)
 if not r:
  state['failed_pairs'].append([i,j]);state['consecutive_failed_branches']+=1
  if state['consecutive_failed_branches']>=2:
   state.update(state='terminal_two_branches_blocked');wr(O/'tree-state.json',state);break
  wr(O/'tree-state.json',state);continue
 for k in ['lines','vias']:
  for n,p in enumerate(r[k]):
   p['id']='addr3-tree-%s-%s-%s'%(step,k,n)
   if k=='lines':p['layer']=16 if p['layer']==2 else 1
  w[k]+=r[k]
 wr(O/('branch-%s.json'%step),r);wr(O/'routed-capture.json',w)
 state['connected_node_indices'].append(j);state['branches'].append(dict(index=step,pair=[i,j],lines=len(r['lines']),vias=len(r['vias'])));state['consecutive_failed_branches']=0
 state['continuity']=connected(*[[p for p in w[k] if p['net']=='ADDR3'] for k in ['pads','lines','vias']]);wr(O/'tree-state.json',state)
 print('SAVED BRANCH',step,state['continuity'],flush=True)
else:
 state['state']='terminal_tree_connected_raw4_recovery_pending';wr(O/'tree-state.json',state)
print(json.dumps(state,indent=2),flush=True)
