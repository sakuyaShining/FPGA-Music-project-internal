"""Extend immutable explicit fanout candidate with a jointly planned right6 bus.
No native CAD calls, no old solver/apply replay. Right6 resistor INPUT nets are
reversed explicitly, with compensated external wiring; internal14MUX Cu kept.
"""
from pathlib import Path
import json,hashlib,sys,copy,datetime
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
from shapely.geometry import Point,LineString,box
from shapely.affinity import rotate
from shapely import union_all,from_wkb
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as PatchPolygon
E=Path(__file__).parent
def read(n):return json.loads((E/n).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=read('sensor-header-fanout-current.json');plan=read('sensor-electrode-channel-plan-current.json')
assert base['candidate_geometry_terminal'] and base['candidate_left8_four_pad_connectivity_pass']
assert sha(E/'sensor-front-14nets-current.epcb2')==base['source_sha256']
native=read('control-power-current-plan.json')['native_file_checks']
assert all(sha(Path(r['file']))==r['actual'] for r in native)
pads=read('sensor-front-exact-source-pads-14nets-current.json')['pads'];by={(p['ref'],p['pin']):p for p in pads}
changes=copy.deepcopy(plan['proposed_pad_net_changes'])
for c in changes:
 p=by[(c['ref'],c['pin'])];assert p['net']==c['old'];p['net']=c['proposed']
for ref in range(11,17):
 p=by[(f'R{ref}','1')];old=p['net'];p['net']=f'L0_E{24-ref:02}'
 changes.append(dict(ref=p['ref'],pin='1',old=old,proposed=p['net'],reason='Right6 input-side reversal for ordered north/perimeter bus; compensate physical harness. Internal M08..13 retained.'))
assert len(changes)==28
a=read('sensor-front-native-14nets-reopened-DRC-current.json')['value'];vias=copy.deepcopy(a['vias'])
for m in base['proposed_Ground_via_moves']:
 v=next(v for v in vias if v['primitiveId']==m['id']);v['x']=m['proposed_mm'][0]/.0254;v['y']=m['proposed_mm'][1]/.0254
def shape(p):
 s=p['shape'];w=s['width']*.0254;h=s['height']*.0254
 return Point(p['x_mm'],p['y_mm']).buffer(w/2,quad_segs=256) if s['padType']=='ELLIPSE' and abs(w-h)<1e-6 else rotate(box(p['x_mm']-w/2,p['y_mm']-h/2,p['x_mm']+w/2,p['y_mm']+h/2),p['angle'],origin=(p['x_mm'],p['y_mm']))
obs=[(p['ref']+'.'+p['pin'],p['net'],shape(p),.1651,'PAD') for p in pads]
for t in a['lines']:obs.append((t['primitiveId'],t['net'],LineString([(t['startX']*.0254,t['startY']*.0254),(t['endX']*.0254,t['endY']*.0254)]).buffer(t['lineWidth']*.0254/2,quad_segs=256),.1651,'LINE'))
for v in vias:obs.append((v['primitiveId'],v['net'],Point(v['x']*.0254,v['y']*.0254).buffer(v['diameter']*.0254/2,quad_segs=256),.2501,'VIA'))
routes=copy.deepcopy(base['checks']);width=.1651
for i in range(8,14):
 net=f'L0_E{i:02}';b=next(c for c in routes if c['net']==net and c['kind']=='EXTERNAL_NC_BRIDGE');sx,sy=b['points'][-1]
 pos=i%4
 if pos==0:escape=[[8.7,sy+.46],[10.2,sy+.46]]
 elif pos==1:escape=[[8.65,sy],[8.95,sy+.30],[10.2,sy+.30]]
 elif pos==2:escape=[[8.65,sy],[8.95,sy-.30],[10.2,sy-.30]]
 else:escape=[[8.7,sy-.46],[10.2,sy-.46]]
 lane_y=17.0-.5*(i-8);lane_x=40.0+.5*(i-8)
 p=next(p for p in pads if p['ref'].startswith('R') and p['pin']=='1' and p['net']==net)
 points=[[sx,sy]]+escape+[[17.0,lane_y],[lane_x,lane_y],[lane_x,p['y_mm']],[p['x_mm'],p['y_mm']]]
 routes.append(dict(net=net,kind='RIGHT6_ESD_TO_SERIES',points=points,width_mm=width))
for i,r in enumerate(routes):obs.append(('candidate:'+str(i),r['net'],LineString(r['points']).buffer(width/2,quad_segs=256),.1651,'NEW_LINE'))
violations=[];checks=[];gnd=from_wkb((E/'sensor-front-real-bottom-ground-14nets-current.wkb').read_bytes())
for i,r in enumerate(routes):
 cu=next(o[2] for o in obs if o[0]=='candidate:'+str(i));bad=[];margin=1e9
 for nm,n,o,c,kind in obs:
  if n!=r['net']:
   dd=cu.distance(o);margin=min(margin,dd-c)
   if dd<c-1e-8:bad.append(dict(other=nm,kind=kind,actual_mm=dd,required_mm=c))
 if bad:violations.append(dict(net=r['net'],kind=r['kind'],violations=bad))
 checks.append(dict(net=r['net'],kind=r['kind'],points=r['points'],width_mm=width,length_mm=LineString(r['points']).length,physical_pass=not bad,minimum_extra_clearance_mm=margin,actual_prior_Ground_reference_missing_mm2=cu.difference(gnd).area,reference_accepted=False))
islands={}
for i in range(14):
 net=f'L0_E{i:02}';cu=union_all([shape(p) for p in pads if p['net']==net]+[LineString(r['points']).buffer(width/2,quad_segs=256) for r in checks if r['net']==net]);islands[net]=len(cu.geoms) if hasattr(cu,'geoms') else 1
mapping=[]
for lane in range(6):
 for row in range(14):
  p=by[(f'R{row+3}','1')];header=int(p['net'][-2:])+1
  mapping.append(dict(lane=lane,MUX_channel=row,logical_raw_index=row*6+lane,J1_pin=header,electrode_net=p['net'],series_resistor=p['ref'],internal_net=f'L0_M{row:02}'))
assert sorted(x['logical_raw_index'] for x in mapping)==list(range(84)) and len({(x['lane'],x['J1_pin']) for x in mapping})==84
assert all(by[(f'R{r}','2')]['net']==f'L0_M{r-3:02}' for r in range(3,17))
assert all(sha(Path(r['file']))==r['actual'] for r in native)
r=dict(at=datetime.datetime.now().astimezone().isoformat(),state='OFFLINE_ALL14_ELECTRODE_CHANNEL_CANDIDATE',source_sha256=base['source_sha256'],input_fanout_sha256=sha(E/'sensor-header-fanout-current.json'),
 changes_from_prior='Explicitly reverse6 additional input-side R11..16 electrode nets and compensate header harness; order-preserving six-lane north/perimeter bus with actual clearances. No default remove, no old grid replay.',
 proposed_PAD_net_changes=changes,proposed_PAD_net_change_count=28,proposed_Ground_via_moves=base['proposed_Ground_via_moves'],existing91lines_retained=True,internal14MUX_nets_retained=True,new_signal_vias=0,
 routes=checks,new_signal_segments=sum(len(c['points'])-1 for c in checks),all_candidate_physical_pass=not violations,violations=violations,electrode_pad_islands=islands,all14_fourPAD_connectivity_pass=all(n==1 for n in islands.values()),full84_candidate_harness=mapping,full84_mapping_bijective=True,
 right6_full_width_prior_actual_Ground_reference_pass=all(c['actual_prior_Ground_reference_missing_mm2']<1e-8 for c in checks if c['kind']=='RIGHT6_ESD_TO_SERIES'),
 reference_scope='Right6 measured against prior actualGround only.14movedGrounddrills,TH-terminal transitions and allsource reference/oldcontacts/DC/minneck still need real native repour; no fullcandidate reference acceptance.',
 seven_control_nets_still_unrouted=True,native_applied=False,native40unchanged=True,manufacturing_release=False,physical_tests='UNMEASURED',candidate_geometry_terminal=True)
(E/'sensor-whole14-channel-current.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
fig,ax=plt.subplots(figsize=(13,10))
for nm,n,g,c,kind in obs:
 if kind=='NEW_LINE':continue
 ax.add_patch(PatchPolygon(list(g.exterior.coords),facecolor='#8296a5' if n=='GND' else '#c6ccd3',edgecolor='#6b7580',linewidth=.25))
for c in checks:
 ax.plot([p[0] for p in c['points']],[p[1] for p in c['points']],linewidth=1.0,color=plt.cm.tab20(int(c['net'][-2:])/20))
ax.set(xlim=(0,55),ylim=(0,45),aspect='equal',xlabel='x / mm',ylabel='y / mm',title='OFFLINE only: all14 electrode channels; original91 tracks retained\nRight6 resistor INPUT nets reversed;28PAD changes;14Ground via mirrors;7controls pending')
ax.grid(alpha=.15);fig.tight_layout();fig.savefig(E/'sensor-whole14-channel-current.png',dpi=170);plt.close(fig)
print(json.dumps({k:v for k,v in r.items() if k not in ['routes','full84_candidate_harness','proposed_PAD_net_changes','proposed_Ground_via_moves']},ensure_ascii=False))
