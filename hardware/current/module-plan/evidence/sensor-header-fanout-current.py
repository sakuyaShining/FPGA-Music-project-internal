"""Explicit all14 fanout candidate, not a replay of the stopped grid router.

Change: reflect14 per-header Ground-return vias to the left of J1. This opens
the right-side fanout and preserves each signal-TH-to-return distance. Offline
only; native source, existing91lines and all component positions are untouched.
"""
from pathlib import Path
import json,hashlib,sys,copy,datetime,math
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
from shapely.geometry import Point,LineString,box
from shapely.affinity import rotate
from shapely import from_wkb,union_all
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as PatchPolygon

E=Path(__file__).parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
plan=json.loads((E/'sensor-electrode-channel-plan-current.json').read_text())
source=E/'sensor-front-14nets-current.epcb2';assert sha(source)==plan['source_sha256']
native=json.loads((E/'control-power-current-plan.json').read_text())['native_file_checks']
assert all(sha(Path(r['file']))==r['actual'] for r in native)
pads=json.loads((E/'sensor-front-exact-source-pads-14nets-current.json').read_text())['pads']
by={(p['ref'],p['pin']):p for p in pads}
for ch in plan['proposed_pad_net_changes']:
 p=by[(ch['ref'],ch['pin'])];assert p['net']==ch['old'];p['net']=ch['proposed']
a=json.loads((E/'sensor-front-native-14nets-reopened-DRC-current.json').read_text())['value']
vias=copy.deepcopy(a['vias']);old_vias=copy.deepcopy(vias);moves=[]
for i in range(1,15):
 p=by[('J1',str(i))]
 matches=[v for v in vias if abs(v['x']*.0254-6.4513)<.001 and abs(v['y']*.0254-p['y_mm'])<.001]
 assert len(matches)==1,(i,matches)
 v=matches[0];old=[v['x']*.0254,v['y']*.0254];new=[2*p['x_mm']-old[0],old[1]]
 v['x']=new[0]/.0254
 assert abs(math.dist(old,[p['x_mm'],p['y_mm']])-math.dist(new,[p['x_mm'],p['y_mm']]))<1e-10
 moves.append(dict(id=v['primitiveId'],net=v['net'],old_mm=old,proposed_mm=new,header_pin=i,return_distance_mm=math.dist(new,[p['x_mm'],p['y_mm']]),diameter_mm=v['diameter']*.0254,drill_mm=v['holeDiameter']*.0254))
 assert moves[-1]['return_distance_mm']<=1.5

def shape(p):
 s=p['shape'];w=s['width']*.0254;h=s['height']*.0254
 return Point(p['x_mm'],p['y_mm']).buffer(w/2,quad_segs=256) if s['padType']=='ELLIPSE' and abs(w-h)<1e-6 else rotate(box(p['x_mm']-w/2,p['y_mm']-h/2,p['x_mm']+w/2,p['y_mm']+h/2),p['angle'],origin=(p['x_mm'],p['y_mm']))
obs=[(p['ref']+'.'+p['pin'],p['net'],shape(p),.1651,'PAD') for p in pads]
for t in a['lines']:obs.append((t['primitiveId'],t['net'],LineString([(t['startX']*.0254,t['startY']*.0254),(t['endX']*.0254,t['endY']*.0254)]).buffer(t['lineWidth']*.0254/2,quad_segs=256),.1651,'LINE'))
for v in vias:obs.append((v['primitiveId'],v['net'],Point(v['x']*.0254,v['y']*.0254).buffer(v['diameter']*.0254/2,quad_segs=256),.2501,'VIA'))
width=.1651;routes=[]
for r in json.loads((E/'sensor-front-electrode-whole-channel-order-current.json').read_text())['nets']:
 h=by[('J1',r['header']['pin'])];d=by[(r['ESD']['ref'],r['ESD']['pin'])]
 points=[[h['x_mm'],h['y_mm']],[d['x_mm'],d['y_mm']]]
 if r['net']=='L0_E13':points=[points[0],[5.55,9.7],[5.9,10.45],[6.3,10.5],[6.8,10.5],points[1]]
 routes.append(dict(net=r['net'],kind='HEADER_TO_ESD',points=points))
for b in plan['candidate14_ESD_external_bridge_checks']:routes.append(dict(net=b['net'],kind='EXTERNAL_NC_BRIDGE',points=[b['start'],b['end']]))
# Joint left8 corridors, including explicit escapes around the unchanged
# right-side ESD Ground vias. All8 are validated against each other at once.
for i in range(8):
 net=f'L0_E{i:02}';b=next(b for b in plan['candidate14_ESD_external_bridge_checks'] if b['net']==net)
 sx,sy=b['end'];p=next(p for p in pads if p['ref'].startswith('R') and p['pin']=='1' and p['net']==net)
 pos=i%4
 if pos==0:escape=[[8.7,sy+.46],[10.2,sy+.46]]
 elif pos==1:escape=[[8.65,sy],[8.95,sy+.30],[10.2,sy+.30]]
 elif pos==2:escape=[[8.65,sy],[8.95,sy-.30],[10.2,sy-.30]]
 else:escape=[[8.7,sy-.46],[10.2,sy-.46]]
 routes.append(dict(net=net,kind='LEFT8_ESD_TO_SERIES',points=[[sx,sy]]+escape+[[17.5,p['y_mm']],[p['x_mm'],p['y_mm']]]))
for i,r in enumerate(routes):obs.append(('candidate:'+str(i),r['net'],LineString(r['points']).buffer(width/2,quad_segs=256),.1651,'NEW_LINE'))
bad=[];checks=[]
for i,r in enumerate(routes):
 cu=next(o[2] for o in obs if o[0]=='candidate:'+str(i));margin=1e9;local=[]
 for nm,n,o,c,kind in obs:
  if n!=r['net']:
   dd=cu.distance(o);margin=min(margin,dd-c)
   if dd<c-1e-8:local.append(dict(other=nm,kind=kind,actual_mm=dd,required_mm=c))
 if local:bad.append(dict(net=r['net'],kind=r['kind'],violations=local))
 checks.append(dict(**r,width_mm=width,length_mm=LineString(r['points']).length,minimum_extra_clearance_mm=margin,physical_pass=not local))
move_bad=[]
for mv in moves:
 own=next(o for o in obs if o[0]==mv['id'])
 for nm,n,o,c,kind in obs:
  if n!='GND':
   dd=own[2].distance(o)
   if dd<max(.2501,c)-1e-8:move_bad.append(dict(id=mv['id'],other=nm,actual_mm=dd,required_mm=max(.2501,c)))
 if own[2].distance(box(0,0,55,45).boundary)<.3-1e-8:move_bad.append(dict(id=mv['id'],error='board-edge clearance'))

# Provisional DC geometry ONLY. A future candidate must be actually repoured;
# this is not actual post-move native Ground copper.
actual_gnd=from_wkb((E/'sensor-front-real-bottom-ground-14nets-current.wkb').read_bytes())
model=actual_gnd
for mv in moves:model=model.union(Point(mv['old_mm']).buffer(mv['drill_mm']/2,quad_segs=256))
for mv in moves:model=model.difference(Point(mv['proposed_mm']).buffer(mv['drill_mm']/2,quad_segs=256))
for c in checks:
 cu=LineString(c['points']).buffer(width/2,quad_segs=256)
 c['actual_old_Ground_reference_missing_mm2']=cu.difference(actual_gnd).area
 c['provisional_post_drill_model_reference_missing_mm2']=cu.difference(model).area
 if c['kind']=='HEADER_TO_ESD':
  p=next(p for p in pads if p['ref']=='J1' and p['net']==c['net'])
  terminal_region=shape(p).buffer(.1651+1e-5,quad_segs=256)
  c['provisional_missing_outside_TH_terminal_clearance_mm2']=cu.difference(model).difference(terminal_region).area
 c['reference_accepted']=False

result=dict(at=datetime.datetime.now().astimezone().isoformat(),state='OFFLINE_EXPLICIT14_FANOUT_WITH14_RETURN_VIA_MIRRORS',source_sha256=plan['source_sha256'],method_change='No graph search. Explicit all14 fanout geometry; reflect14 header Ground-return vias left of J1. This changes actual obstacle placement, instead of extending/repeating the stopped router.',
 rejected_initial_left8_diagonal_entry=dict(reason='Direct steep entries clipped adjacent resistor pads. Explicit x17.5 horizontal terminal entries replace them; source remains unchanged.',violations=[dict(net='L0_E01',other='R10.1',actual_mm=.039761057506920675,required_mm=.1651),dict(net='L0_E02',other='R9.1',actual_mm=.05301922278732169,required_mm=.1651),dict(net='L0_E03',other='R8.1',actual_mm=.03523942231745381,required_mm=.1651)]),
 proposed_Ground_via_moves=moves,existing91lines_unchanged=True,other22vias_unchanged=True,proposed22PAD_map_inherited=True,components_moved=0,signal_vias_added=0,
 all14_header_fanouts_physical_pass=all(c['physical_pass'] for c in checks if c['kind']=='HEADER_TO_ESD'),all14_NC_bridges_physical_pass=all(c['physical_pass'] for c in checks if c['kind']=='EXTERNAL_NC_BRIDGE'),all_left8_ESD_to_series_physical_pass=all(c['physical_pass'] for c in checks if c['kind']=='LEFT8_ESD_TO_SERIES'),moved14vias_physical_pass=not move_bad,
 checks=checks,violations=bad,moved_via_violations=move_bad,max_signal_TH_return_distance_mm=max(m['return_distance_mm'] for m in moves),
 Ground_model_scope='Hypothesis only: fill old14 Ground drill holes, cut new14 drills from actual prior Bottom polygon. Not a real native repour, not acceptance of all old contacts/sourceCu/reference/DC/minimum neck.',
 Ground_model_components=len(model.geoms) if hasattr(model,'geoms') else 1,
 missing_reference_outside_TH_terminal_provisional_max_mm2=max(c.get('provisional_missing_outside_TH_terminal_clearance_mm2',0) for c in checks),
 native_files_checked=len(native),native40_unchanged=True,native_applied=False,all14_electrode_complete_routes=False,remaining='Right6 ESD-to-seriesR full paths;7control nets; real native schematic/22PAD+14via candidate and realGround repour/fullacceptance; quote/whole700budget/delivery',physical_tests='UNMEASURED',manufacturing_release=False)
assert all(sha(Path(r['file']))==r['actual'] for r in native)
(E/'sensor-header-fanout-current.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

fig,ax=plt.subplots(figsize=(9,12))
for nm,n,g,c,kind in obs:
 if kind=='NEW_LINE':continue
 if g.bounds[0]>11:continue
 color='#8a9ba8' if n=='GND' else '#d8dce0'
 ax.add_patch(PatchPolygon(list(g.exterior.coords),facecolor=color,edgecolor='#657380',linewidth=.4))
for v in old_vias:
 if v['primitiveId'] in {m['id'] for m in moves}:ax.add_patch(plt.Circle((v['x']*.0254,v['y']*.0254),v['diameter']*.0254/2,color='#d44545',fill=False,linestyle='--',linewidth=.8))
for c in checks:
 if c['kind']!='HEADER_TO_ESD':continue
 points=c['points'];ax.plot([p[0] for p in points],[p[1] for p in points],linewidth=1.7,label=c['net'],color=plt.cm.tab20(int(c['net'][-2:])/20))
 h=points[0];ax.text(4.8,h[1],c['net'][-2:],ha='right',va='center',fontsize=8)
for p in pads:
 if p['ref'] in ['D1','D2','D3','D4'] and p['pin']=='3':ax.text(9.8,p['y_mm'],p['ref'],fontsize=9)
ax.set(xlim=(2.7,10.5),ylim=(7.1,43),aspect='equal',xlabel='x / mm',ylabel='y / mm',title='OFFLINE candidate: all14 J1-to-ESD fanouts\n14 return vias mirrored LEFT; old positions red dashed')
ax.grid(alpha=.18);fig.tight_layout();fig.savefig(E/'sensor-header-fanout-current.png',dpi=170);plt.close(fig)
fig,ax=plt.subplots(figsize=(13,10))
for nm,n,g,c,kind in obs:
 if kind=='NEW_LINE':continue
 color='#8296a5' if n=='GND' else '#c6ccd3'
 ax.add_patch(PatchPolygon(list(g.exterior.coords),facecolor=color,edgecolor='#6b7580',linewidth=.25))
for c in checks:
 points=c['points'];ax.plot([p[0] for p in points],[p[1] for p in points],linewidth=1.15,color=plt.cm.tab20(int(c['net'][-2:])/20))
for p in pads:
 if p['ref'].startswith('R') and p['pin']=='1':ax.text(p['x_mm'],p['y_mm'],p['ref'],fontsize=5)
ax.set(xlim=(0,55),ylim=(0,45),aspect='equal',xlabel='x / mm',ylabel='y / mm',title='OFFLINE only: all14 header fanouts + left8 complete electrode paths\nOriginal91 tracks shown; native source remains unchanged')
ax.grid(alpha=.15);fig.tight_layout();fig.savefig(E/'sensor-left8-whole-candidate-current.png',dpi=170);plt.close(fig)
print(json.dumps({k:v for k,v in result.items() if k not in ['checks','proposed_Ground_via_moves']},ensure_ascii=False))
