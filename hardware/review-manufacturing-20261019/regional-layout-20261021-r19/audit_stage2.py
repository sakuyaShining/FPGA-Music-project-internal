"""Audit actual stage-1 geometry without treating a dismantled region as a finished candidate."""
from pathlib import Path
import sys,json,hashlib,math,zipfile
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BASE))
from native_project import PROJECT,info
from resume_offline import read_native
from native_plane_geometry import poured_planes
from physical_geometry import actual_pad
from four_layer_geometry import connected
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
read=lambda p:json.loads(p.read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
meta=read(BASE/'native-stage2-drc-meta.json');assert sha(PROJECT/'pcb/PCB1.epcb2')==meta['pcb_sha256']
native=read_native(PROJECT/'pcb/PCB1.epcb2');source=read_native(Path(info['source_project'])/'pcb/PCB1.epcb2');cap=read(BASE/'native-stage2-capture.json')
layout=read(BASE/'selected-layout.json');moved={m['ref'] for m in layout['selected_variant']['changes']};ids={m['id'] for m in layout['selected_variant']['changes']}
oldcap=read(ROOT/info['source_capture']);canon=lambda ps:sorted(ps,key=lambda p:p['id'])
assert canon([p for p in oldcap['pads'] if p['ref'] not in moved])==canon([p for p in cap['pads'] if p['ref'] not in moved])
placement_deltas=[]
for m in layout['selected_variant']['changes']:
    for p in m['expected_pads']:
        actual=next(q for q in cap['pads'] if q['id']==p['id'])
        delta=math.dist((actual['x'],actual['y']),(p['x'],p['y']))*.0254
        # API captures round to0.1mil; bound their vector error, retain native DRC.
        assert actual['net']==p['net'] and delta<.004,(m['ref'],p['n'],delta)
        placement_deltas.append(dict(ref=m['ref'],pin=p['n'],expected_to_capture_mm=delta))
for key,p in source.items():
    k,i=key
    if k in ['DOCHEAD','LINE','VIA','POURED']:continue
    q=native.get(key);assert q is not None,key
    if (k=='COMPONENT' and i in ids) or (k=='ATTR' and p.get('parentId') in ids):
        assert {a:b for a,b in p.items() if a not in ['x','y','angle']}=={a:b for a,b in q.items() if a not in ['x','y','angle']},key
    elif k=='PAD' and i in ids:
        assert {a:b for a,b in p.items() if a not in ['centerX','centerY','padAngle']}=={a:b for a,b in q.items() if a not in ['centerX','centerY','padAngle']},key
    else:assert p==q,key
def lines(doc):return [dict(net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in doc.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
ls=lines(native);ols=lines(source)
def cu(net,layer,data):return unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,quad_segs=32) for p in data if p['net']==net and p['layer']==layer])
assert all(cu('5V_PERIPH',l,ls).equals(cu('5V_PERIPH',l,ols)) for l in [1,15,16,2]),'5V original width/geometry changed'
audio=['I2S_BCK','I2S_DIN','I2S_LRCK'];assert {k:p for k,p in source.items() if k[0]=='LINE' and p.get('netName') in audio}=={k:p for k,p in native.items() if k[0]=='LINE' and p.get('netName') in audio}
assert connected([p for p in cap['pads'] if p['net']=='DISP_SCK'],[p for p in ls if p['net']=='DISP_SCK'],[p for p in cap['vias'] if p['net']=='DISP_SCK'])['complete']
planes=poured_planes(native);oldplanes=poured_planes(source)
av=[p for p in cap['vias'] if p['net'] in audio];excluded=unary_union([Point(p['x']*.0254,p['y']*.0254).buffer(1,quad_segs=64) for p in av]+[actual_pad(p).buffer(.5) for p in cap['pads'] if p['layer']==12 and p['net'] in audio])
coverage=[]
for net in audio:
    traces=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).difference(excluded) for p in ls if p['net']==net and p['layer']==2];total=sum(p.length for p in traces)
    before=sum(p.intersection(oldplanes[16]).length for p in traces)/total;after=sum(p.intersection(planes[16]).length for p in traces)/total
    assert after>=before-1e-6,(net,before,after);coverage.append(dict(net=net,before_fraction=before,after_fraction=after,si_signoff=False))
sid=set(read(BASE/'native-clock-route-apply.json')['result']['createdV']);gid=set(read(BASE/'native-clock-ground-apply.json')['createdV'])|set(read(BASE/'native-reconnections-ground-apply.json')['createdV']);sv=[p for p in cap['vias'] if p['id'] in sid];gv=[p for p in cap['vias'] if p['id'] in gid];contacts=[]
for v in gv:
    q=Point(v['x']*.0254,v['y']*.0254);ring=q.buffer(v['diameter']*.0254/2,quad_segs=48).difference(q.buffer(v['hole']*.0254/2,quad_segs=48));areas={str(l):ring.intersection(planes[l]).area for l in [15,2]};assert min(areas.values())>=.15
    contacts.append(dict(id=v['id'],reference_contacts_mm2=areas))
returns=[dict(signal_id=v['id'],distance_mm=min(math.dist((v['x'],v['y']),(g['x'],g['y']))*.0254 for g in gv)) for v in sv];assert max(p['distance_mm'] for p in returns)<1.5
ex=unary_union([Point(p['x']*.0254,p['y']*.0254).buffer(1,quad_segs=64) for p in sv]+[actual_pad(p).buffer(.5) for p in cap['pads'] if p['net']=='DISP_SCK' and p['layer']==12]);ref=[]
for layer,ground in [(1,15),(16,2)]:
    traces=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).difference(ex) for p in ls if p['net']=='DISP_SCK' and p['layer']==layer];total=sum(p.length for p in traces)
    ref.append(dict(signal_layer=layer,ground_layer=ground,evaluated_mm=total,projection_fraction=sum(p.intersection(planes[ground]).length for p in traces)/total,si_signoff=False))
counts={g['name']:g['count'] for g in read(BASE/'native-stage2-drc.json')};assert counts=={'Connection Error':84}
assert all(sha(Path(info['source_project'])/rel)==h for rel,h in info['source_files'].items())
result=dict(pcb_sha256=meta['pcb_sha256'],native_drc=counts,stage='regional_layout_reconnections_work_in_progress_not_promoted',moved_components=['U15','C35','R30','R31','R63','R64'],moved_testpads=['TP13','TP14'],other224_components_and_other_pads_unchanged=True,MPNs_values_pin_net_membership_stackup_rules_outline_and_connectors_preserved=True,original_5V_copper_geometry_and_width_restored=True,audio_copper_unchanged=True,audio_reference_projection=coverage,display_clock_complete=True,display_clock_length_mm=sum(math.dist((p['x1'],p['y1']),(p['x2'],p['y2']))*.0254 for p in ls if p['net']=='DISP_SCK'),display_clock_signal_vias=len(sv),display_clock_ground_stitches=len(gv),actual_ground_contacts=contacts,reference_change_distances=returns,display_clock_reference_projection=ref,source_R15_19_files_unchanged=True,unqualified=['Other disturbed signal/power nets not restored yet','U8 address/disable fanout corridors not yet arranged','Final mechanical fit, actual edge rates and qualified factory stackup unknown'],manufacturing_release=False)

extra=read(ROOT/'regional-signals-20261021-r20/native-complete-routes-apply.json')
result['restored_connected_signal_nets']=extra['selected_nets']
for net in extra['selected_nets']:
    assert connected([p for p in cap['pads'] if p['net']==net],[p for p in ls if p['net']==net],[p for p in cap['vias'] if p['net']==net])['complete'],net
result['all_five_new_signal_vias']=list(sid|set(extra['result']['createdV']))
result['new_ground_stitches_total']=len(gv)
result['display_clock_ground_stitches']=2
result['placement_capture_deltas_mm']=placement_deltas
result['placement_capture_comparison_tolerance_mm']=.004
(BASE/'stage2-actual-review.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
archive=BASE/'native-stage2-WORK-IN-PROGRESS.zip'
if not archive.exists():
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for p in PROJECT.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(PROJECT))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
print(json.dumps({k:v for k,v in result.items() if k not in ['audio_reference_projection']},indent=2),flush=True)
