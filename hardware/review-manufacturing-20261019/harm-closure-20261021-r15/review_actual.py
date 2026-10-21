"""Review actual saved/reopened copper, metadata, references and source preservation."""
from pathlib import Path
import sys,json,hashlib,math,collections
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
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text(encoding='utf-8'))
pcb=PROJECT/'pcb/PCB1.epcb2';beforepcb=Path(info['source_project'])/'pcb/PCB1.epcb2'
meta=read(BASE/'native-drc-meta.json');assert meta['source_stable'] and sha(pcb)==meta['pcb_sha256_after']
old=read_native(beforepcb);new=read_native(pcb);cap=read(BASE/'native-verified-capture.json');plan=read(BASE/'plan.json');audit=read(BASE/'native-apply-audit.json')
counts={p['name']:p.get('count',0) for p in read(BASE/'native-drc.json')};assert counts=={'Connection Error':58},counts
cid=audit['result']['actual_component']['id']
for key in set(old)|set(new):
    kind,i=key;a,b=old.get(key),new.get(key)
    if kind in ['DOCHEAD','LINE','VIA','POURED']:continue
    if (kind=='COMPONENT' and i==cid) or (kind=='ATTR' and a and a.get('parentId')==cid):
        assert {k:v for k,v in a.items() if k not in ['x','y','angle']}=={k:v for k,v in b.items() if k not in ['x','y','angle']},key
    else:assert a==b,key
created=set(audit['result']['createdV'])
groundaudit=read(BASE/'ground-stitch-apply-audit.json')
groundids=set(groundaudit['result']['createdV'])
assert len(groundids)==5 and not (groundids & created)
assert {i:v for (k,i),v in old.items() if k=='VIA'}=={i:v for (k,i),v in new.items() if k=='VIA' and i not in created|groundids}
def lines(native):
    return [dict(net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in native.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
def cu(ls):return unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,quad_segs=32) for p in ls])
actual=lines(new);prior=lines(old)
# Native cleanup coalesced the planned old-pad junction into the pre-existing
# 363532d01f230c2c diagonal. Require exact preservation of that entire power net.
assert {i:p for (k,i),p in old.items() if k=='LINE' and p.get('netName')=='3V3_IO'}=={i:p for (k,i),p in new.items() if k=='LINE' and p.get('netName')=='3V3_IO'}
expected=prior+[p for p in plan['lines'] if p['net']=='HARM_CS_N'];nets=sorted({(p['net'],p['layer']) for p in actual+expected})
assert {i:p for (k,i),p in old.items() if k=='LINE' and p.get('netName')!='HARM_CS_N'}=={i:p for (k,i),p in new.items() if k=='LINE' and p.get('netName')!='HARM_CS_N'}
copper_deviation=[]
for net,layer in nets:
    a=cu([p for p in expected if p['net']==net and p['layer']==layer]);b=cu([p for p in actual if p['net']==net and p['layer']==layer])
    if net=='HARM_CS_N':
        # Native cleanup absorbed a 0.001mil (0.0000254mm) FR fragment.
        # Bound the actual discrepancy explicitly; no unselected copper changes.
        delta=a.hausdorff_distance(b);assert delta<=.00005,(net,layer,delta)
        assert a.difference(b.buffer(.00005)).is_empty and b.difference(a.buffer(.00005)).is_empty,(net,layer)
        copper_deviation.append(dict(net=net,layer=layer,hausdorff_mm=delta,tolerance_mm=.00005))
    else:assert a.equals(b),(net,layer)
for net in ['HARM_CS_N','3V3_IO']:
    result=connected([p for p in cap['pads'] if p['net']==net],[p for p in actual if p['net']==net],[p for p in cap['vias'] if p['net']==net]);assert result['complete'],(net,result)
planes=poured_planes(new);oldplanes=poured_planes(old)
audio={'I2S_BCK','I2S_DIN','I2S_LRCK'};av=[p for p in cap['vias'] if p['net'] in audio]
excluded=unary_union([Point(p['x']*.0254,p['y']*.0254).buffer(1,quad_segs=64) for p in av]+[actual_pad(p).buffer(.5) for p in cap['pads'] if p['layer']==12 and p['net'] in audio])
coverage=[]
for net in sorted(audio):
    ls=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).difference(excluded) for p in actual if p['layer']==2 and p['net']==net]
    total=sum(q.length for q in ls);a=sum(q.intersection(oldplanes[16]).length for q in ls)/total;b=sum(q.intersection(planes[16]).length for q in ls)/total
    assert b>=a-1e-6,(net,a,b);coverage.append(dict(net=net,before_fraction=a,after_fraction=b,not_si_signoff=True))
newvias=[p for p in cap['vias'] if p['id'] in created]
harm_excluded=unary_union([Point(p['x']*.0254,p['y']*.0254).buffer(1,quad_segs=64) for p in newvias]+[actual_pad(p).buffer(.5) for p in cap['pads'] if p['net']=='HARM_CS_N' and p['layer']==12])
references=[]
for layer,ref in [(1,15),(16,2)]:
    ls=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).difference(harm_excluded) for p in actual if p['net']=='HARM_CS_N' and p['layer']==layer]
    total=sum(p.length for p in ls);good=sum(p.intersection(planes[ref]).length for p in ls)
    references.append(dict(signal_layer=layer,nearest_ground_layer=ref,evaluated_centerline_mm=total,ground_projection_fraction=good/total,not_si_signoff=True))
groundvias=[];groundcontacts=[]
for v in cap['vias']:
    if v['net']!='GND':continue
    q=Point(v['x']*.0254,v['y']*.0254);annulus=q.buffer(v['diameter']*.0254/2,quad_segs=48).difference(q.buffer(v['hole']*.0254/2,quad_segs=48))
    contacts={str(l):annulus.intersection(planes[l]).area for l in [15,2]}
    if all(area>1e-5 for area in contacts.values()):groundvias.append(v)
    if v['id'] in groundids:
        assert all(area>=.15 for area in contacts.values()),(v['id'],contacts)
        groundcontacts.append(dict(id=v['id'],xy_mm=[v['x']*.0254,v['y']*.0254],actual_reference_contact_mm2=contacts))
assert len(groundcontacts)==5
returns=[]
for v in newvias:
    nearest=min(groundvias,key=lambda g:math.dist((g['x'],g['y']),(v['x'],v['y'])))
    returns.append(dict(signal_via=v['id'],x_mm=v['x']*.0254,y_mm=v['y']*.0254,nearest_ground_via_connected_to_both_references=nearest['id'],distance_mm=math.dist((nearest['x'],nearest['y']),(v['x'],v['y']))*.0254,not_si_signoff=True))
    assert returns[-1]['distance_mm']<=1.5
harm_length=sum(math.dist((p['x1'],p['y1']),(p['x2'],p['y2']))*.0254 for p in actual if p['net']=='HARM_CS_N')
rp=[p for p in cap['pads'] if p['ref']=='R30'];mid=[sum(p[k] for p in rp)/2*.0254 for k in ['x','y']]
assert math.dist(mid,[plan['component_x_mm'],plan['component_y_mm']])<.003
assert len(cap['vias'])==530 and len(cap['pads'])==1079
for rel,h in info['source_files'].items():
    assert sha(Path(info['source_project'])/rel)==h
    if not rel.endswith('.eprj3') and rel!='pcb/PCB1.epcb2':assert sha(PROJECT/rel)==h
result=dict(pcb_sha256=sha(pcb),native_drc=counts,all_changed_copper_matches_declared_plan=True,other229_components_pads_rules_stack_values_and_net_memberships_unchanged=True,
            source_r7_19_files_unchanged=True,other17_native_support_files_unchanged=True,components=230,pads=len(cap['pads']),api_lines=len(cap['lines']),native_copper_lines=len(actual),native_microtracks=len(actual)-len(cap['lines']),vias=len(cap['vias']),pours=len(planes),
            completed_net='HARM_CS_N',harm_length_mm=harm_length,new_signal_vias=len(newvias),new_ground_stitches=len(groundcontacts),actual_ground_stitch_contacts=groundcontacts,new_power_vias=0,R30_actual_pad_midpoint_mm=mid,R30_actual_rotation=audit['result']['actual_component']['rotation'],R30_old_power_junction_preserved=True,
            all_original_3V3_IO_copper_records_exactly_unchanged=True,planned_junction_coalesced_into_existing_diagonal='363532d01f230c2c',native_harm_cleanup_deviation=copper_deviation,
            legacy_CPL_stale_designators=['C35','R30'],i2s_audio_copper_unchanged=True,i2s_reference_projection=coverage,harm_reference_projection=references,signal_reference_change_ground_vias=returns,
            edge_rates_and_si_unqualified=True,power_drop_transients_and_actual_measurements_unqualified=True,manufacturing_release=False)
(BASE/'actual-layout-review.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2),flush=True)
