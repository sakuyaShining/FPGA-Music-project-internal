"""Reconcile all actual copper against the declared regional edits and imported routes."""
from pathlib import Path
import sys,json,hashlib,math
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BASE))
from native_project import PROJECT,info
from resume_offline import read_native
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
read=lambda p:json.loads(p.read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
meta=read(BASE/'native-stage2-drc-meta.json');assert sha(PROJECT/'pcb/PCB1.epcb2')==meta['pcb_sha256']
old=read_native(Path(info['source_project'])/'pcb/PCB1.epcb2');new=read_native(PROJECT/'pcb/PCB1.epcb2')
plan=read(BASE/'regional-edit-plan.json');correction=read(BASE/'testpoint-clearance-correction.json')['result']
removedL={p['id'] for p in plan['remove_lines']}|set(correction['removed_lines']);removedV={p['id'] for p in plan['remove_vias']}|set(correction['removed_vias'])
def norm(p):return dict(net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width'])
layers=[1,15,16,2]
expected=[norm(p) for (k,i),p in old.items() if k=='LINE' and p.get('layerId') in layers and i not in removedL]
expected+=[norm(p) for p in read(BASE/'power-preservation-correction.json')['restored_lines'] if p['netName']=='5V_PERIPH']
expected+=read(BASE/'selected-copper.json')['lines']+read(ROOT/'regional-signals-20261021-r20/accepted-complete-copper.json')['lines']
actual=[norm(p) for (k,i),p in new.items() if k=='LINE' and p.get('layerId') in layers]
def cu(ls):return unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,quad_segs=32) for p in ls])
keys=sorted({(p['net'],p['layer']) for p in expected+actual});deviations=[]
for net,layer in keys:
    a=cu([p for p in expected if p['net']==net and p['layer']==layer]);b=cu([p for p in actual if p['net']==net and p['layer']==layer])
    if a.is_empty or b.is_empty:assert a.is_empty and b.is_empty,(net,layer);continue
    d=a.hausdorff_distance(b)
    assert d<=.00005 and a.difference(b.buffer(.00005)).is_empty and b.difference(a.buffer(.00005)).is_empty,(net,layer,d)
    if d>1e-9:deviations.append(dict(net=net,layer=layer,hausdorff_mm=d))
oldvias={i:p for (k,i),p in old.items() if k=='VIA' and i not in removedV};newvias={i:p for (k,i),p in new.items() if k=='VIA'}
assert all(newvias.get(i)==p for i,p in oldvias.items())
added=set(read(BASE/'native-clock-route-apply.json')['result']['createdV'])|set(read(BASE/'native-clock-ground-apply.json')['createdV'])|set(read(ROOT/'regional-signals-20261021-r20/native-complete-routes-apply.json')['result']['createdV'])|set(read(BASE/'native-reconnections-ground-apply.json')['createdV'])
assert set(newvias)==set(oldvias)|added,(len(newvias),len(oldvias),len(added))
cap=read(BASE/'native-stage2-capture.json');planes=__import__('native_plane_geometry').poured_planes(new)
signalids=set(read(BASE/'native-clock-route-apply.json')['result']['createdV'])|set(read(ROOT/'regional-signals-20261021-r20/native-complete-routes-apply.json')['result']['createdV']);groundids=added-signalids
signals=[p for p in cap['vias'] if p['id'] in signalids];grounds=[p for p in cap['vias'] if p['id'] in groundids]
returns=[dict(signal_net=p['net'],signal_id=p['id'],nearest_new_reference_ground_mm=min(math.dist((p['x'],p['y']),(g['x'],g['y']))*.0254 for g in grounds)) for p in signals];assert max(p['nearest_new_reference_ground_mm'] for p in returns)<1.5
stage=read(BASE/'stage2-actual-review.json')
profile=[]
for net in ['DISP_SCK','DISP_HARM_CS_N','DISP_VIS_CS_N','LCD_RESET_N']:
    excluded=unary_union([Point(p['x']*.0254,p['y']*.0254).buffer(1,quad_segs=64) for p in signals if p['net']==net]+[__import__('physical_geometry').actual_pad(p).buffer(.5) for p in cap['pads'] if p['net']==net and p['layer']==12])
    for layer,ref in [(1,15),(16,2)]:
        traces=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).difference(excluded) for p in actual if p['net']==net and p['layer']==layer];total=sum(p.length for p in traces)
        if not total:continue
        missing=unary_union([p.difference(planes[ref]) for p in traces]);profile.append(dict(net=net,signal_layer=layer,reference_layer=ref,evaluated_mm=total,reference_projection_fraction=1-missing.length/total,gap_bounds_mm=list(missing.bounds) if not missing.is_empty else None,si_signoff=False))
result=dict(pcb_sha256=meta['pcb_sha256'],all_actual_copper_matches_declared_regional_edits=True,copper_comparison_tolerance_mm=.00005,small_native_cleanup_differences=deviations,all_retained_source_vias_exactly_preserved=True,native_copper_lines=len(actual),api_lines=len(cap['lines']),native_microtracks=len(actual)-len(cap['lines']),vias=len(cap['vias']),pads=len(cap['pads']),new_signal_vias=len(signals),new_ground_stitches=len(grounds),all_new_reference_distances=returns,actual_reference_projection=profile,manufacturing_release=False)
(BASE/'declared-copper-reconciliation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
print(json.dumps(result,indent=2),flush=True)
