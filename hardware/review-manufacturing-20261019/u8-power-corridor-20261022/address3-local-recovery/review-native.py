"""Reconcile saved native copper and measure actual reference geometry."""
from pathlib import Path
import sys,json,hashlib,math,re,importlib.util
O=Path(__file__).resolve().parent;B=O.parent;R=B.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path[:0]=[str(R),str(B)]
from resume_offline import read_native
from native_plane_geometry import poured_planes
from four_layer_geometry import connected
from physical_geometry import actual_pad
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
import grid_route as g
spec=importlib.util.spec_from_file_location('addr3_native',O/'native_project.py');n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
rd=lambda p:json.loads(p.read_text(encoding='utf8'))
wr=lambda p,x:p.write_text(json.dumps(x,indent=2),encoding='utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
state=rd(O/'native-state.json');plan=rd(O/'grounded-plan.json');info=rd(O/'native-candidate-source.json');pcb=n.PROJECT/'pcb/PCB1.epcb2';assert sha(pcb)==state['pcb_sha256'];assert sha(O/'grounded-plan.json')==state['plan_sha256']
source=Path(info['source_project']);assert all(sha(source/p)==h for p,h in info['source_files'].items())
original=read_native(source/'pcb/PCB1.epcb2');raw=read_native(pcb)
doc=n.invoke('capture-identity','return await eda.dmt_SelectControl.getCurrentDocumentInfo();',timeout=35);assert doc['documentType']==3 and doc['parentProjectUuid']==info['parent_project_uuid']
g.invoke=n.invoke;cap=g.capture()
def lines(v):return [dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in v.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
def vias(v):return [dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in v.items() if k=='VIA']
cap['lines']=lines(raw);cap['vias']=vias(raw);wr(O/'native-stage-capture.json',cap)
for k,p in original.items():
 if k[0] not in ['DOCHEAD','LINE','VIA','POURED']:assert raw[k]==p,('Non-copper changed',k)
assert {k for k in original if k[0] not in ['DOCHEAD','LINE','VIA','POURED']}=={k for k in raw if k[0] not in ['DOCHEAD','LINE','VIA','POURED']}
def groups(ls):
 d={}
 for p in ls:d.setdefault((p['net'],p['layer']),[]).append(LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,quad_segs=32))
 return {k:unary_union(v) for k,v in d.items()}
removed={p['id'] for p in plan['remove_lines']}
patch_expected=rd(Path(state['latest_expected_capture'])) if state.get('latest_expected_capture') else None
expected=groups(patch_expected['lines'] if patch_expected else [p for p in lines(original) if p['id'] not in removed]+plan['lines']);actual=groups(cap['lines']);assert set(expected)==set(actual)
deviation=max(expected[k].hausdorff_distance(actual[k]) for k in actual);assert deviation<1e-5,deviation
removed={p['id'] for p in plan['remove_vias']};ev=patch_expected['vias'] if patch_expected else [p for p in vias(original) if p['id'] not in removed]+plan['vias'];assert len(ev)==len(cap['vias'])
for v in ev:
 matches=[p for p in cap['vias'] if p['net']==v['net'] and abs(p['diameter']-v['diameter'])<.001 and abs(p['hole']-v['hole'])<.001 and math.dist((p['x'],p['y']),(v['x'],v['y']))*.0254<1e-5];assert len(matches)==1,v
proof={net:connected(*[[p for p in cap[k] if p['net']==net] for k in ['pads','lines','vias']]) for net in plan['required_closed']};assert all(v['complete'] for v in proof.values())
planes=poured_planes(raw);oldplanes=poured_planes(original);reference=[]
for net in ['ADDR3','L2_M02','L2_M03']:
 ex=unary_union([Point(p['x']*.0254,p['y']*.0254).buffer(1) for p in cap['vias'] if p['net']==net])
 for layer,ref in [(1,15),(16,2),(2,16)]:
  qs=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).difference(ex) for p in cap['lines'] if p['net']==net and p['layer']==layer]
  if not qs:continue
  length=sum(q.length for q in qs);covered=sum(q.intersection(planes[ref]).length for q in qs);gaps=[q.difference(planes[ref]) for q in qs]
  reference.append(dict(net=net,layer=layer,reference=ref,length_mm=length,covered_mm=covered,gap_mm=length-covered,gap_wkt=[q.wkt for q in gaps if q.length>1e-5]))
protected=lambda net:bool(net.startswith('I2S_') or re.fullmatch(r'RC[0-5]',net) or re.match(r'L[0-5]_',net))
sensitive=[]
for layer,ref in [(1,15),(2,16)]:
 for net in sorted({p['net'] for p in cap['lines'] if p['layer']==layer and protected(p['net']) and p['net'] not in ['L2_M02','L2_M03']}):
  mask=unary_union([Point(v['x']*.0254,v['y']*.0254).buffer(1,quad_segs=64) for v in cap['vias'] if v['net']==net]+[actual_pad(p).buffer(.5) for p in cap['pads'] if p['net']==net and p['layer']==12]);qs=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).difference(mask) for p in cap['lines'] if p['net']==net and p['layer']==layer]
  old=sum(q.intersection(oldplanes[ref]).length for q in qs);new=sum(q.intersection(planes[ref]).length for q in qs);sensitive.append(dict(net=net,layer=layer,reference=ref,before_covered_mm=old,after_covered_mm=new,delta_mm=new-old))
ground=[];refs=[];new_via_ids=set(state.get('new_via_ids',rd(O/'native-apply.json')['createdV']))
for v in cap['vias']:
 if v['net']!='GND':continue
 q=Point(v['x']*.0254,v['y']*.0254);ring=q.buffer(v['diameter']*.0254/2,quad_segs=64).difference(q.buffer(v['hole']*.0254/2,quad_segs=64));areas={str(l):ring.intersection(planes[l]).area for l in [15,2]}
 if min(areas.values())>=.15:refs.append(dict(v,contact_mm2=areas))
 if v['id'] in new_via_ids:ground.append(dict(v,contact_mm2=areas))
returns=[]
for v in [v for v in cap['vias'] if v['net']=='ADDR3' and v['id'] in new_via_ids]:
 r=min(refs,key=lambda p:math.dist((v['x'],v['y']),(p['x'],p['y'])));distance=math.dist((v['x'],v['y']),(r['x'],r['y']))*.0254;returns.append(dict(signal_xy_mm=[v['x']*.0254,v['y']*.0254],ground_xy_mm=[r['x']*.0254,r['y']*.0254],distance_mm=distance,within_preference_1p5mm=distance<=1.500001))
lengths=[]
for net in ['ADDR3','L2_M02','L2_M03']:
 length=lambda ls:sum(math.dist((p['x1'],p['y1']),(p['x2'],p['y2']))*.0254 for p in ls if p['net']==net)
 lengths.append(dict(net=net,before_trace_length_mm=length(lines(original)),after_trace_length_mm=length(cap['lines']),before_vias=sum(p['net']==net for p in vias(original)),after_vias=sum(p['net']==net for p in cap['vias'])))
audit=dict(pcb_sha256=sha(pcb),source_pcb_sha256=plan['source_pcb_sha256'],native_drc=state['drc'],native_copper_max_hausdorff_mm=deviation,actual_vias=len(cap['vias']),actual_pads=len(cap['pads']),continuity=proof,actual_reference_projection=reference,new_ground_contacts=ground,actual_returns=returns,unchanged_sensor_audio_reference=sensitive,reference_degradation=[p for p in sensitive if p['delta_mm']<-1e-5],changed_net_lengths_and_vias=lengths,components_bom_stack_outline_unchanged=True,manufacturing_release=False,physical_tests='UNMEASURED')
wr(O/'native-stage-review.json',audit)
print(json.dumps(dict(sha=audit['pcb_sha256'],drc=state['drc'],copper_deviation=deviation,reference=[{k:v for k,v in p.items() if k!='gap_wkt'} for p in reference],ground_contacts=len(ground),bad_ground_contacts=[v for v in ground if min(v['contact_mm2'].values())<.15],protected_reference_degradation=audit['reference_degradation'],lengths=lengths),indent=2),flush=True)
