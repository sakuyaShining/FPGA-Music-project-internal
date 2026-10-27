from pathlib import Path
import json,sys,hashlib,datetime,math
sys.path.insert(0,r'D:\FPGA-Project\codex-tools\shapely')
from shapely.geometry import Point,LineString,box
from shapely.affinity import rotate
E=Path(__file__).parent;J=lambda f:json.loads((E/f).read_text(encoding='utf-8-sig'));a=J('sensor-fourlayer-signal-repair-reopened-DRC-current.json')['value'];pads=J('sensor-fourlayer-exact-source-pads-current.json')['pads']
def root(p):
 d={};on=False
 for l in p.read_text(encoding='utf-8').splitlines():
  l=l.rstrip('|')
  if '||' not in l:continue
  h,b=map(json.loads,l.split('||',1))
  if h['type']=='DOCHEAD':on=b['uuid']=='f52674d6627fca6f'
  if on:d[h.get('id',h['type'])]=(h,b)
 return d
original=root(E/'sensor-front-14nets-current.epcb2');prior=root(E/'sensor-fourlayer-before-signal-reference-repair-current.epcb2');cur=root(E/'sensor-fourlayer-native-current.epcb2');removed={x['primitiveId'] for x in J('sensor-fourlayer-signal-reference-repair-plan-current.json')['delete_own_candidate_lines']};unexpected=[]
for k,(h,b) in prior.items():
 if h['type'] in ['DOCHEAD','POURED']:continue
 if k in removed:assert h['type']=='LINE' and k not in original;continue
 if k not in cur or cur[k][1]!=b:unexpected.append({'id':k,'type':h['type']})
protected=[k for k,(h,b) in original.items() if h['type']=='LINE'];assert len(protected)==91;origdiff=[k for k in protected if cur.get(k,(None,None))[1]!=original[k][1]];rulediff=[k for k,(h,b) in original.items() if h['type'] in ['RULE','RULE_SELECTOR','RULE_TEMPLATE'] and cur.get(k,(None,None))[1]!=b];oldids=set(protected)
def shape(p):
 q=p['shape'];w=q['width']*.0254;hh=q['height']*.0254
 return Point(p['x_mm'],p['y_mm']).buffer(w/2,quad_segs=256) if q['padType']=='ELLIPSE' and abs(w-hh)<1e-6 else rotate(box(p['x_mm']-w/2,p['y_mm']-hh/2,p['x_mm']+w/2,p['y_mm']+hh/2),p['angle'],origin=(p['x_mm'],p['y_mm']))
obs=[]
for p in pads:obs.append((p['id'],p['net'],shape(p),.1651,{1,2,15,16} if p['layer']==12 else {p['layer']},'PAD'))
for t in a['lines']:obs.append((t['primitiveId'],t['net'],LineString([(t['startX']*.0254,t['startY']*.0254),(t['endX']*.0254,t['endY']*.0254)]).buffer(t['lineWidth']*.0254/2,quad_segs=256),.1651,{t['layer']},'LINE'))
for v in a['vias']:obs.append((v['primitiveId'],v['net'],Point(v['x']*.0254,v['y']*.0254).buffer(v['diameter']*.0254/2,quad_segs=256),.2501011,{1,2,15,16},'VIA'))
oldviaids={h['id'] for h,b in original.values() if h['type']=='VIA'};changedvia={x['id'] for x in J('sensor-fourlayer-control-candidate-current.json')['proposed_Ground_via_moves']};checkids={x['primitiveId'] for x in a['lines'] if x['primitiveId'] not in oldids}|{x['primitiveId'] for x in a['vias'] if x['primitiveId'] not in oldviaids}|changedvia;bboxes={q[0]:q[2].bounds for q in obs};bad=[];margins=[]
for oid,n,g,cl,layers,kind in obs:
 if oid not in checkids:continue
 b=bboxes[oid];margin=1e9
 for tid,net,q,clear,ls,tk in obs:
  if n==net or not layers&ls:continue
  z=bboxes[tid];req=max(cl,clear);dx=max(b[0]-z[2],z[0]-b[2],0);dy=max(b[1]-z[3],z[1]-b[3],0)
  if max(dx,dy)>=req:continue
  dist=g.distance(q);margin=min(margin,dist-req)
  if dist<req-1e-8:bad.append({'own':oid,'other':tid,'kind':tk,'gap_mm':dist,'required_mm':req})
 if kind in ['LINE','VIA'] and g.distance(box(0,0,55,45).boundary)<.2999994-1e-8:bad.append({'own':oid,'kind':'boardedge'})
 margins.append({'id':oid,'local_minimum_extra_clearance_mm':None if margin==1e9 else margin})
holes=[{'id':v['primitiveId'],'xy':[v['x']*.0254,v['y']*.0254],'drill':v['holeDiameter']*.0254} for v in a['vias']]+[{'id':p['id'],'xy':[p['hole_x_mm'],p['hole_y_mm']],'drill':p['hole']['width']*.0254} for p in pads if p['hole']];hb=[]
for i,h in enumerate(holes):
 for t in holes[i+1:]:
  gap=math.dist(h['xy'],t['xy'])-(h['drill']+t['drill'])/2
  if gap<.2999994-1e-8:hb.append({'a':h['id'],'b':t['id'],'gap_mm':gap})
local=[]
for key in [('U1','12'),('U2','7')]:
 p=next(p for p in pads if (p['ref'],p['pin'])==key);v=min((v for v in a['vias'] if v['net']=='GND'),key=lambda v:math.dist([p['x_mm'],p['y_mm']],[v['x']*.0254,v['y']*.0254]));local.append({'Ground_pin':'.'.join(key),'Ground_via':v['primitiveId'],'actual_distance_mm':math.dist([p['x_mm'],p['y_mm']],[v['x']*.0254,v['y']*.0254])})
r={'at':datetime.datetime.now().astimezone().isoformat(),'source_sha256':hashlib.sha256((E/'sensor-fourlayer-native-current.epcb2').read_bytes()).hexdigest(),'original91Cu_source_exact_preserved':not origdiff,'original_RULE_source_exact_preserved':not rulediff,'prior_all_source_preserved_except6explicit_own_candidate_lines':not unexpected,'unexpected_source_changes':unexpected,'original_Cu_differences':origdiff,'rule_differences':rulediff,'actual_line_count':len(a['lines']),'actual_via_count':len(a['vias']),'actual_new_or_moved_primitives_checked':len(checkids),'actual_physical_pass':not bad,'physical_violations':bad,'all_drill_spacing_pass':not hb,'drill_violations':hb,'actual_MUX_Schmitt_Ground_references':local,'native_saved_closed_reopened_DRC':a['drc'],'all150PAD_map_verified':J('sensor-fourlayer-exact-source-pads-current.json')['all150netlist_PADs_match'],'accepted':False,'reference_criteria_decision_pending':True,'physical_tests':'UNMEASURED'};(E/'sensor-fourlayer-final-candidate-audit-current.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(r,ensure_ascii=True));assert not unexpected and not origdiff and not rulediff and not bad and not hb
