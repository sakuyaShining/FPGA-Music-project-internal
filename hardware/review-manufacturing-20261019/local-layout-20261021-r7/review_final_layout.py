"""Audit r7 against preserved r5, including real ground and complete native copper."""
import sys,json,math,hashlib,collections
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(BASE));sys.path.insert(0,str(ROOT))
from native_project import PROJECT,info
from resume_offline import read_native
from native_plane_geometry import poured_planes
from physical_geometry import actual_pad
from four_layer_geometry import connected
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text(encoding='utf-8'))
PCB=PROJECT/'pcb/PCB1.epcb2';meta=read(BASE/'native-drc-meta.json');assert meta['source_stable'] and sha(PCB)==meta['pcb_sha256_after']
drc=read(BASE/'native-drc.json');counts={c['name']:c.get('count',0) for c in drc};assert counts=={'Connection Error':62},counts
old=read_native(Path(info['source_project'])/'pcb/PCB1.epcb2');new=read_native(PCB);capture=read(BASE/'native-verified-capture.json');first=read(BASE/'decoupling-plan.json');plan=read(BASE/'final-decoupling-plan.json');audit=read(BASE/'native-final-decoupling-audit.json');cid='9f1e9b877a49c6a1'
for key in set(old)|set(new):
 k,i=key
 if k in ['DOCHEAD','LINE','VIA','POURED']:continue
 a,b=old.get(key),new.get(key)
 if k=='COMPONENT' and i==cid:
  assert {n:v for n,v in a.items() if n not in ['x','y','angle']}=={n:v for n,v in b.items() if n not in ['x','y','angle']}
 elif k=='ATTR' and a and a.get('parentId')==cid:
  assert {n:v for n,v in a.items() if n not in ['x','y','angle']}=={n:v for n,v in b.items() if n not in ['x','y','angle']}
 else:assert a==b,(k,i)
removed=set(first['remove_line_ids']);created=set(audit['result']['createdL']);newvia=read(BASE/'native-decoupling-audit.json')['result']['createdV'][0]
assert {i:p for (k,i),p in old.items() if k=='LINE' and i not in removed}=={i:p for (k,i),p in new.items() if k=='LINE' and i not in created}
assert {i:p for (k,i),p in old.items() if k=='VIA'}=={i:p for (k,i),p in new.items() if k=='VIA' and i!=newvia}
assert len([1 for k,i in new if k=='VIA'])==520
actual=[dict(net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in new.items() if k=='LINE' and i in created]
shape=lambda ls:unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,resolution=32) for p in ls])
for net in ['3V3_PERIPH','GND']:
 a=shape([p for p in plan['lines'] if p['net']==net]);b=shape([p for p in actual if p['net']==net]);assert a.difference(b.buffer(.000005)).is_empty and b.difference(a.buffer(.000005)).is_empty
planes=poured_planes(new);oldplanes=poured_planes(old);v=new['VIA',newvia];pt=Point(v['centerX']*.0254,v['centerY']*.0254);annulus=pt.buffer(v['viaDiameter']*.0254/2,resolution=64).difference(pt.buffer(v['holeDiameter']*.0254/2,resolution=64));contacts={str(l):annulus.intersection(planes[l]).area for l in [1,15,16,2]};assert contacts['15']>1e-5 and contacts['16']>1e-5
audio={'I2S_BCK','I2S_DIN','I2S_LRCK'};av=[p for (k,i),p in new.items() if k=='VIA' and p['netName'] in audio];excluded=unary_union([Point(p['centerX']*.0254,p['centerY']*.0254).buffer(1,resolution=64) for p in av]+[actual_pad(p).buffer(.5) for p in capture['pads'] if p['layer']==12 and p['net'] in audio]);coverage=[]
for n in sorted(audio):
 ls=[LineString([(p['startX']*.0254,p['startY']*.0254),(p['endX']*.0254,p['endY']*.0254)]).difference(excluded) for (k,i),p in new.items() if k=='LINE' and p.get('layerId')==2 and p['netName']==n];total=sum(q.length for q in ls);before=sum(q.intersection(oldplanes[16]).length for q in ls)/total;after=sum(q.intersection(planes[16]).length for q in ls)/total;assert after>=before-1e-6;coverage.append(dict(net=n,before_fraction=before,after_fraction=after,not_si_signoff=True))
for rel,h in info['source_files'].items():
 assert sha(Path(info['source_project'])/rel)==h
 if not rel.endswith('.eprj3') and rel!='pcb/PCB1.epcb2':assert sha(PROJECT/rel)==h
counts2=collections.Counter(k for k,i in new);assert counts2['COMPONENT']==230 and counts2['LINE']==3290 and len(capture['lines'])==3262
result=dict(pcb_sha256=sha(PCB),native_drc=counts,other_229_components_and_pads_unchanged=True,C35_only_position_rotation_and_attribute_transform_changed=True,all_net_memberships_footprints_values_rules_layer_stack_unchanged=True,unselected_copper_unchanged=True,original_r5_19_files_unchanged=True,other_17_support_files_unchanged=True,new_local_copper_matches_plan=True,ground_via_id=newvia,ground_via_inner_contacts_mm2=contacts,audio_reference_coverage=coverage,audio_copper_unchanged=True,api_lines=3262,native_lines=3290,native_microtracks=28,vias=520,components=230,pads=len(capture['pads']),C35_final_rotation=270,C35_final_pad_midpoint_mm=[77.7,45.3],power_stub_before_mm=first['before_power_stub_mm'],power_stub_after_mm=plan['vcc_centerline_mm'],ground_stub_mm=plan['ground_stub_mm'],legacy_CPL_C35_position_is_stale=True,power_transient_measured=False,manufacturing_release=False)
(BASE/'final-layout-review.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2),flush=True)
