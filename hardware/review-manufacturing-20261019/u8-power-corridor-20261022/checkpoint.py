"""Reopen and reconcile this actual native clock/corridor checkpoint."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import sys,json,hashlib,zipfile,csv
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(OUT))
import native_project as n
from native_review import call
from resume_offline import read_native
from native_plane_geometry import poured_planes
from physical_geometry import actual_pad
from four_layer_geometry import connected
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
import grid_route as g
read=lambda p:json.loads(p.read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
PROJECT=n.PROJECT;pcb=PROJECT/'pcb/PCB1.epcb2'
assert sha(pcb)==read(OUT/'after-ground-meta.json')['pcb_sha256']
call('u8-clock-close-owned',['session','close','--session',n.SESSION],60)
session=call('u8-clock-reopen',['open','--path',str(PROJECT/(PROJECT.name+'.eprj3')),'--headless','true'],120)
(OUT/'native-session.json').write_text(json.dumps(session,indent=2));n.SESSION=session['sessionId'];doc=None
for attempt in range(6):
 docs=n.invoke('clock-reopen-pcbs-'+str(attempt),'await new Promise(r=>setTimeout(r,2500));return await eda.dmt_Pcb.getAllPcbsInfo();',timeout=35)
 if not docs:continue
 try:n.invoke('clock-reopen-tab-'+str(attempt),"return await eda.dmt_EditorControl.openDocument('c3fd8656cf425e9f');",timeout=45)
 except RuntimeError:continue
 doc=n.invoke('clock-reopen-identity-'+str(attempt),'return await eda.dmt_SelectControl.getCurrentDocumentInfo();',timeout=35)
 if doc and doc.get('documentType')==3:break
assert doc and doc['parentProjectUuid']==n.info['parent_project_uuid']
source_sha=sha(pcb);drc=n.invoke('clock-checkpoint-drc','await eda.pcb_Drc.stopRealTimeDrc();return await eda.pcb_Drc.check(true,false,true);',timeout=180);assert sha(pcb)==source_sha
(OUT/'checkpoint-drc.json').write_text(json.dumps(drc,indent=2));counts={c['name']:sum(len(v.get('list',[])) for v in c.get('list',[])) for c in drc};assert counts=={'Connection Error':59},counts
assert not any(v['name'] in ['BUS_SCK','INPUT_LOAD_N','GND','PRESET1','3V3_IO','5V_PERIPH'] for c in drc for v in c.get('list',[]))
g.invoke=n.invoke;cap=g.capture();(OUT/'checkpoint-capture.json').write_text(json.dumps(cap))
original=read_native(Path(n.info['source_project'])/'pcb/PCB1.epcb2');final=read_native(pcb)
assert all(sha(Path(n.info['source_project'])/p)==h for p,h in n.info['source_files'].items())
stable=read(ROOT/'ACTIVE-ROUTING-CANDIDATE.json');assert all(sha(Path(stable['project'])/p)==h for p,h in stable['files'].items())
for k,p in original.items():
 if k[0] not in ['DOCHEAD','LINE','VIA','POURED']:assert final[k]==p,('Non-copper changed',k)
plan=read(OUT/'plan.json');fan=read(OUT/'bus-escapes.json');trunk=read(OUT/'grid-trunks.json');ground=read(OUT/'reconnections-ground-plan.json')
def lines(raw):return [dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
cap['lines']=lines(final)
cap['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in final.items() if k=='VIA']
(OUT/'checkpoint-capture.json').write_text(json.dumps(cap))
def groups(ls):
 d={}
 for p in ls:d.setdefault((p['net'],p['layer']),[]).append(LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,quad_segs=32))
 return {k:unary_union(v) for k,v in d.items()}
removed={p['id'] for p in plan['remove_lines']};expected=groups([p for p in lines(original) if p['id'] not in removed]+plan['lines']+fan['lines']+trunk['lines']);actual=groups(lines(final));assert set(expected)==set(actual)
deviation=max(expected[k].hausdorff_distance(actual[k]) for k in actual);assert deviation<.00001,deviation
vremoved={p['id'] for p in plan['remove_vias']}
expected_vias=[dict(net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in original.items() if k=='VIA' and i not in vremoved]+plan['vias']+fan['vias']+trunk['vias']+ground['vias']
assert len(expected_vias)==len(cap['vias'])==555
for v in expected_vias:
 match=[p for p in cap['vias'] if p['net']==v['net'] and abs(p['diameter']-v['diameter'])<.001 and abs(p['hole']-v['hole'])<.001 and ((p['x']-v['x'])**2+(p['y']-v['y'])**2)**.5*.0254<.00001];assert len(match)==1,v
proof={net:connected([p for p in cap['pads'] if p['net']==net],[p for p in lines(final) if p['net']==net],[p for p in cap['vias'] if p['net']==net]) for net in ['BUS_SCK','INPUT_LOAD_N','PRESET1','3V3_IO','5V_PERIPH']};assert all(p['complete'] for p in proof.values())
planes=poured_planes(final);oldplanes=poured_planes(original);ground_ids=set(read(OUT/'native-ground-apply.json')['createdV']);contacts=[]
for v in cap['vias']:
 if v['id'] not in ground_ids:continue
 q=Point(v['x']*.0254,v['y']*.0254);ring=q.buffer(.3048,quad_segs=64).difference(q.buffer(.1524,quad_segs=64));areas={str(l):ring.intersection(planes[l]).area for l in [15,2]};assert min(areas.values())>=.15;contacts.append(dict(id=v['id'],contact_mm2=areas))
audio=[]
for net in ['I2S_BCK','I2S_DIN','I2S_LRCK']:
 excluded=unary_union([Point(v['x']*.0254,v['y']*.0254).buffer(1,quad_segs=64) for v in cap['vias'] if v['net'] in ['I2S_BCK','I2S_DIN','I2S_LRCK']]+[actual_pad(p).buffer(.5) for p in cap['pads'] if p['layer']==12 and p['net'] in ['I2S_BCK','I2S_DIN','I2S_LRCK']])
 traces=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).difference(excluded) for p in lines(final) if p['net']==net and p['layer']==2];length=sum(q.length for q in traces);before=sum(q.intersection(oldplanes[16]).length for q in traces)/length;after=sum(q.intersection(planes[16]).length for q in traces)/length;assert after>=before-1e-6,(net,before,after);audio.append(dict(net=net,before_fraction=before,after_fraction=after,si_signoff=False))
archive=OUT/'native-clock-corridor-WORK-IN-PROGRESS.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in PROJECT.rglob('*'):
  if p.is_file():z.write(p,p.relative_to(PROJECT))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None;assert hashlib.sha256(z.read('pcb/PCB1.epcb2')).hexdigest()==sha(pcb)
remaining=[dict(net=v['name'],open_objects=len(v['list'])) for c in drc for v in c.get('list',[])]
with (OUT/'remaining-networks.csv').open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=['net','open_objects']);w.writeheader();w.writerows(remaining)
result=dict(updated_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),project=str(PROJECT),session=n.SESSION,pcb_sha256=sha(pcb),native_drc=dict(clearance=0,physical=0,connection=59),remaining_nets=len(remaining),components=230,pads=len(cap['pads']),vias=len(cap['vias']),native_lines=len(lines(final)),source_checkpoint_and_stable_R15_unchanged=True,components_rules_stackup_outline_nets_unchanged=True,declared_actual_copper_max_deviation_mm=deviation,continuity=proof,new_ground_stitches=len(contacts),actual_ground_contacts=contacts,audio_reference_projection=audio,reference_distance_goal_uncovered_ids=ground['uncovered_signal_ids'],reference_distance_goal_not_si_signoff=True,archive=str(archive),archive_sha256=sha(archive),manufacturing_release=False)
(OUT/'checkpoint-review.json').write_text(json.dumps(result,indent=2))
p=ROOT/'REGIONAL-WORK-IN-PROGRESS.json';pointer=read(p);pointer.pop('pending_trial',None);pointer.update(updated_at=result['updated_at'],project=str(PROJECT),session=n.SESSION,pcb_sha256=result['pcb_sha256'],native_wrapper=str(OUT/'native_project.py'),source_capture=str(OUT/'checkpoint-capture.json'),drc=str(OUT/'checkpoint-drc.json'),review=str(OUT/'checkpoint-review.json'),readme=str(OUT/'README.md'),native_drc=result['native_drc'],status='saved_reopened_verified_construction_checkpoint_not_promoted',router_status='Native trial explicitly cancelled after API timeout; Freerouting terminal without complete nets. Only independently checked local clock and INPUT_LOAD_N recovery trunks applied.',next_action='Do not repeat MOSI fixed-layout search: the U8-to-R64 MOSI edge failed even with 22mm search margin. Jointly move R64/fanout or blocking local copper; R64 is BUS_MOSI-to-GND pulldown, so recover its affected GND connection. Address0-3/MUX_DISABLE still35 objects; BUS_MOSI7; five regional controls11; PRESET3 four; INV2 two. Preserve references and source identity.')
pointer['closed_nets_this_recovery']=list(dict.fromkeys(pointer['closed_nets_this_recovery']+['BUS_SCK']))
p.write_text(json.dumps(pointer,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['actual_ground_contacts','audio_reference_projection']},indent=2),flush=True)
