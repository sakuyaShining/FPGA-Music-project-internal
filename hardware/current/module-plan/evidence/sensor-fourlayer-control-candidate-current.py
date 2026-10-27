"""Explicit four-layer alternative, offline only; no hidden layer/cost acceptance.
Top electrodes and7 short source escapes; Bottom7 controls; two real Ground
planes are REQUIRED in a future native candidate. No hypothetical fill accepted.
"""
from pathlib import Path
import json,hashlib,sys,copy,datetime,math
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
from shapely.geometry import Point,LineString,box
from shapely.affinity import rotate
from shapely import union_all
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as PatchPolygon
E=Path(__file__).parent
def read(n):return json.loads((E/n).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
prior=read('sensor-fourlayer-control-candidate-current.json') if (E/'sensor-fourlayer-control-candidate-current.json').exists() else {}
prior_rejection=prior.get('rejected_prior_geometry',dict(route_violations=prior.get('route_violations',[]),new_via_violations=prior.get('new_via_violations',[]),reason='Explicit revision:move MUX inner escape to29.3mm;routeSENSE below actual Ground vias;routeADDR2 aroundC4Ground andADDR3via. No rule relaxation.'))
base=read('sensor-whole14-channel-current.json');assert base['all_candidate_physical_pass'] and base['all14_fourPAD_connectivity_pass']
assert sha(E/'sensor-front-14nets-current.epcb2')==base['source_sha256']
native=read('control-power-current-plan.json')['native_file_checks'];assert all(sha(Path(r['file']))==r['actual'] for r in native)
pads=read('sensor-front-exact-source-pads-14nets-current.json')['pads'];by={(p['ref'],p['pin']):p for p in pads};changes=copy.deepcopy(base['proposed_PAD_net_changes'])
for c in changes:
 p=by[(c['ref'],c['pin'])];assert p['net']==c['old'];p['net']=c['proposed']
pin_nets={'3':'RC_DRIVE','5':'SENSE_OUT','7':'ADDR0','9':'MUX_DISABLE','11':'ADDR1','13':'ADDR2','15':'ADDR3'}
for pin,net in pin_nets.items():
 p=by[('J2',pin)];changes.append(dict(ref='J2',pin=pin,old=p['net'],proposed=net,reason='Explicit odd-pin control order for fourlayer candidate; all evenGround/pin1power unchanged. Harness must be revised.'));p['net']=net
a=read('sensor-front-native-14nets-reopened-DRC-current.json')['value'];vias=copy.deepcopy(a['vias']);moves=copy.deepcopy(base['proposed_Ground_via_moves'])
for m in moves:
 v=next(v for v in vias if v['primitiveId']==m['id']);v['x']=m['proposed_mm'][0]/.0254;v['y']=m['proposed_mm'][1]/.0254
for pin in pin_nets:
 p=by[('J2',pin)];matches=[v for v in vias if abs(v['x']*.0254-48.54990036)<1e-5 and abs(v['y']*.0254-p['y_mm'])<.001];assert len(matches)==1,pin
 v=matches[0];old=[v['x']*.0254,v['y']*.0254];new=[2*p['x_mm']-old[0],old[1]];v['x']=new[0]/.0254
 moves.append(dict(id=v['primitiveId'],net='GND',old_mm=old,proposed_mm=new,header='J2',header_pin=int(pin),return_distance_mm=math.dist(new,[p['x_mm'],p['y_mm']]),diameter_mm=v['diameter']*.0254,drill_mm=v['holeDiameter']*.0254))
assert len(changes)==35 and len(moves)==21 and all(m['return_distance_mm']<=1.5 for m in moves)
def shape(p):
 s=p['shape'];w=s['width']*.0254;h=s['height']*.0254
 return Point(p['x_mm'],p['y_mm']).buffer(w/2,quad_segs=256) if s['padType']=='ELLIPSE' and abs(w-h)<1e-6 else rotate(box(p['x_mm']-w/2,p['y_mm']-h/2,p['x_mm']+w/2,p['y_mm']+h/2),p['angle'],origin=(p['x_mm'],p['y_mm']))
obs=[]
for p in pads:obs.append((p['ref']+'.'+p['pin'],p['net'],shape(p),.1651,{1,2} if p['layer']==12 else {p['layer']},'PAD'))
for t in a['lines']:obs.append((t['primitiveId'],t['net'],LineString([(t['startX']*.0254,t['startY']*.0254),(t['endX']*.0254,t['endY']*.0254)]).buffer(t['lineWidth']*.0254/2,quad_segs=256),.1651,{t['layer']},'SOURCE_LINE'))
for v in vias:obs.append((v['primitiveId'],v['net'],Point(v['x']*.0254,v['y']*.0254).buffer(v['diameter']*.0254/2,quad_segs=256),.2501011,{1,2},'SOURCE_VIA'))
routes=[dict(net=c['net'],kind=c['kind'],layer=1,points=c['points'],width_mm=c['width_mm']) for c in base['routes']]
S={'RC_DRIVE':[21.6,28.1],'SENSE_OUT':[28.2,27.9],'ADDR0':[26.0,22.4],'ADDR1':[27.0,21.2],'ADDR2':[28.0,20.0],'ADDR3':[29.2,18.8],'MUX_DISABLE':[29.0,22.0]}
G={'RC_DRIVE':[21.6,29.2],'SENSE_OUT':[29.1,28.8],'ADDR0':[26.0,23.5],'ADDR1':[28.0,22.0],'MUX_DISABLE':[28.0,22.0],'ADDR2':[28.2,18.8],'ADDR3':[28.2,18.8]}
sources={'RC_DRIVE':('R1','1'),'SENSE_OUT':('R2','2'),'ADDR0':('U1','10'),'ADDR1':('U1','11'),'ADDR2':('U1','14'),'ADDR3':('U1','13'),'MUX_DISABLE':('U1','15')}
new_vias=[]
for net,xy in S.items():new_vias.append(dict(id='signal:'+net,net=net,xy_mm=xy,diameter_mm=.7112,drill_mm=.36068))
for k,xy in enumerate(sorted({tuple(v) for v in G.values()})):new_vias.append(dict(id='return:'+str(k),net='GND',xy_mm=list(xy),diameter_mm=.7112,drill_mm=.36068))
for v in new_vias:obs.append((v['id'],v['net'],Point(v['xy_mm']).buffer(v['diameter_mm']/2,quad_segs=256),.2501011,{1,2},'NEW_VIA'))
for net,key in sources.items():
 p=by[key];start=[p['x_mm'],p['y_mm']]
 if net=='ADDR0':pts=[start,[25.5,start[1]],[26.0,start[1]+.5],S[net]]
 elif net=='ADDR1':pts=[start,[26.5,start[1]],[27.0,start[1]+.5],S[net]]
 elif net=='ADDR2':pts=[start,[28.8,start[1]],S[net]]
 elif net=='MUX_DISABLE':pts=[start,[29.3,start[1]],[29.3,22.0],S[net]]
 else:pts=[start,S[net]]
 routes.append(dict(net=net,kind='TOP_SOURCE_ESCAPE',layer=1,points=pts,width_mm=.1651))
 p=next(by[('J2',pin)] for pin,n in pin_nets.items() if n==net)
 bottom=[S[net],[p['x_mm'],p['y_mm']]]
 if net=='SENSE_OUT':bottom=[S[net],[31.0,27.6],[34.0,27.6],[p['x_mm'],p['y_mm']]]
 elif net=='ADDR2':bottom=[S[net],[30.3,19.55],[32.5,17.4],[35.0,17.4],[p['x_mm'],p['y_mm']]]
 routes.append(dict(net=net,kind='BOTTOM_CONTROL',layer=2,points=bottom,width_mm=.1651))
for i,c in enumerate(routes):obs.append(('route:'+str(i),c['net'],LineString(c['points']).buffer(c['width_mm']/2,quad_segs=256),.1651,{c['layer']},'NEW_LINE'))
bad=[];checks=[]
for i,c in enumerate(routes):
 own=next(o for o in obs if o[0]=='route:'+str(i));local=[];margin=1e9
 for nm,n,g,clear,layers,kind in obs:
  if n!=c['net'] and c['layer'] in layers:
   dd=own[2].distance(g);margin=min(margin,dd-clear)
   if dd<clear-1e-8:local.append(dict(other=nm,kind=kind,actual_mm=dd,required_mm=clear))
 if local:bad.append(dict(net=c['net'],kind=c['kind'],violations=local))
 checks.append(dict(**c,physical_pass=not local,minimum_extra_clearance_mm=margin))
via_bad=[]
for v in new_vias:
 own=next(o for o in obs if o[0]==v['id'])
 for nm,n,g,clear,layers,kind in obs:
  if n!=v['net'] and own[2].distance(g)<max(.2501011,clear)-1e-8:via_bad.append(dict(via=v['id'],other=nm,kind=kind,actual_mm=own[2].distance(g),required_mm=max(.2501011,clear)))
# Drill spacing separately, including same-net holes.
holes=[dict(id=v['primitiveId'],xy=[v['x']*.0254,v['y']*.0254],drill=v['holeDiameter']*.0254) for v in vias]+[dict(id=v['id'],xy=v['xy_mm'],drill=v['drill_mm']) for v in new_vias]
for p in pads:
 if p['hole']:holes.append(dict(id=p['ref']+'.'+p['pin'],xy=[p['hole_x_mm'],p['hole_y_mm']],drill=p['hole']['width']*.0254))
hole_bad=[]
for i,h in enumerate(holes):
 for k in holes[i+1:]:
  gap=math.dist(h['xy'],k['xy'])-(h['drill']+k['drill'])/2
  if gap<.2999994-1e-8:hole_bad.append(dict(a=h['id'],b=k['id'],edge_gap_mm=gap,required_mm=.2999994))
returns=[dict(net=n,signal_via_mm=S[n],Ground_via_mm=G[n],distance_mm=math.dist(S[n],G[n])) for n in S]
assert all(x['distance_mm']<=1.5 for x in returns)
assert all(sha(Path(r['file']))==r['actual'] for r in native)
r=dict(at=datetime.datetime.now().astimezone().isoformat(),state='OFFLINE_FOURLAYER_ALTERNATIVE_NOT_COSTED_OR_NATIVE',source_sha256=base['source_sha256'],input14_channel_sha256=sha(E/'sensor-whole14-channel-current.json'),explicit_layer_change='2layer current ->4layer alternative:Top signal/Inner1 Ground/Inner2 Ground/Bottom controls. Requires actual manufacturer stack and native layer identities/real pours; not silently accepted.',board_mm=[55,45],
 rejected_prior_geometry=prior_rejection,
 saved_source_rules=dict(track_PAD_clearance_mm=.1651,via_clearance_mm=.2501011,hole_to_hole_clearance_mm=.2999994,source='sensor-front-native-pcb-verified-rule-readback.json'),offline_rule_erratum='Initial drill-only helper used0.25mm; native saved rule is0.2999994mm and is rechecked here without any native rule change. Via comparisons now also use exact saved0.2501011mm.',
 proposed_PAD_net_changes=changes,proposed_PAD_change_count=len(changes),proposed_Ground_via_moves=moves,new_vias=new_vias,new_signal_vias=7,new_Ground_return_vias=5,total_vias=len(vias)+len(new_vias),
 routes=checks,all_routes_physical_pass=not bad,route_violations=bad,new_vias_physical_pass=not via_bad,new_via_violations=via_bad,all_drill_spacing_pass=not hole_bad,drill_violations=hole_bad,
 signal_to_return_pairs=returns,all_new_signal_vias_have_Ground_return_within1_5mm=True,J2_candidate_pin_nets=pin_nets,J2_scope_warning='OldJ2.15SENSE_OUT is obsolete ONLY FOR THIS UNAPPLIED fourlayer candidate. CandidateJ2.5=SENSE_OUT;6bank outputs remain six independent GPIOs. All7odd signalpins explicitly reassigned, evenGround/pin1power unchanged. NativeJ2 unchanged.',
 all_new_reference_planes_actual=False,whole_reference_DC_oldcontacts_and_real_repour_pending=True,manufacturer_stack_quote_delivery_pending=True,whole700budget_accepted=False,existing91Top_lines_retained=True,native_applied=False,native40unchanged=True,physical_tests='UNMEASURED',manufacturing_release=False)
(E/'sensor-fourlayer-control-candidate-current.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
fig,axs=plt.subplots(1,2,figsize=(16,7))
for ax,L in zip(axs,[1,2]):
 for nm,n,g,cl,ls,k in obs:
  if L not in ls or k=='NEW_LINE':continue
  ax.add_patch(PatchPolygon(list(g.exterior.coords),facecolor='#8296a5' if n=='GND' else '#c6ccd3',edgecolor='#6b7580',linewidth=.25))
 for c in checks:
  if c['layer']==L:ax.plot([p[0] for p in c['points']],[p[1] for p in c['points']],linewidth=.9)
 ax.set(xlim=(0,55),ylim=(0,45),aspect='equal',xlabel='x/mm',ylabel='y/mm',title=('Top: electrodes + control escapes' if L==1 else 'Bottom:7controls; INNER Ground REQUIRED'))
 ax.grid(alpha=.15)
fig.suptitle('UNAPPLIED4layer alternative;35PAD net changes;21Ground-via moves;new7signal+5Ground vias\nNo actual inner planes / no stack quote / no manufacturing release')
fig.tight_layout();fig.savefig(E/'sensor-fourlayer-control-candidate-current.png',dpi=150);plt.close(fig)
print(json.dumps({k:v for k,v in r.items() if k not in ['routes','proposed_PAD_net_changes','proposed_Ground_via_moves','new_vias','signal_to_return_pairs']},ensure_ascii=False))
