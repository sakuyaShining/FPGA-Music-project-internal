"""Reopen, verify real native changes, archive, and update the single resume pointer."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import sys,json,hashlib,zipfile,shutil,csv
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent;BASE=ROOT/'regional-recovery-20261021-r21'
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BASE))
import native_project as native
from native_review import call
from resume_offline import read_native
from native_plane_geometry import poured_planes
from shapely.geometry import Point
import grid_route as g
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf8'))
plan=read(OUT/'plan.json');result=read(OUT/'native-apply.json')['result'];PROJECT=native.PROJECT;pcb=PROJECT/'pcb/PCB1.epcb2'
assert (OUT/'after-save-drc.json').exists(),'Wait for apply.py to complete'
call('bus-return-close-owned',['session','close','--session',native.SESSION],60)
descriptor=PROJECT/(PROJECT.name+'.eprj3')
session=call('bus-return-reopen',['open','--path',str(descriptor),'--headless','true'],120)
(BASE/'native-session.json').write_text(json.dumps(session,indent=2));native.SESSION=session['sessionId']
for attempt in range(3):
 native.invoke('bus-return-open-'+str(attempt),"await new Promise(r=>setTimeout(r,2500));return await eda.dmt_EditorControl.openDocument('c3fd8656cf425e9f');")
 doc=native.invoke('bus-return-ready-'+str(attempt),'await new Promise(r=>setTimeout(r,1500));return await eda.dmt_SelectControl.getCurrentDocumentInfo();')
 if doc and doc.get('documentType')==3:break
assert doc['documentType']==3 and doc['parentProjectUuid']==native.info['parent_project_uuid']
before_sha=sha(pcb)
drc=native.invoke('bus-return-reopened-drc','await eda.pcb_Drc.stopRealTimeDrc();return await eda.pcb_Drc.check(true,false,true);',timeout=180)
assert sha(pcb)==before_sha
(OUT/'checkpoint-drc.json').write_text(json.dumps(drc,indent=2))
counts={c['name']:sum(len(n.get('list',[])) for n in c.get('list',[])) for c in drc}
assert counts.get('Clearance Error',0)==0 and counts.get('Physical Error',0)==0
assert counts.get('Connection Error',0)==63,counts
assert not any(n['name'] in ['BUS_RETURN','GND'] for c in drc for n in c.get('list',[]))
g.invoke=native.invoke;capture=g.capture();(OUT/'checkpoint-capture.json').write_text(json.dumps(capture))
final=read_native(pcb)
class Source:
 def __init__(self,s):self.s=s
 def read_text(self,encoding):return self.s
with zipfile.ZipFile(OUT/'before-repair.zip') as z:original=read_native(Source(z.read('pcb/PCB1.epcb2').decode('utf8')))
for key,p in original.items():
 if key[0] not in ['DOCHEAD','POURED']:assert final[key]==p,('Unexpected source object changed',key)
added={k:p for k,p in final.items() if k not in original and k[0] not in ['DOCHEAD','POURED']}
assert set(added)=={('VIA',i) for i in result['createdV']},list(added)
planes=poured_planes(final);contacts=[]
for v in plan['vias']:
 actual=next(p for (k,i),p in added.items() if p['netName']==v['net'])
 assert abs(actual['centerX']-v['x'])*.0254<.00001 and abs(actual['centerY']-v['y'])*.0254<.00001
 if v['net']=='GND':
  q=Point(actual['centerX']*.0254,actual['centerY']*.0254);ring=q.buffer(.3048,quad_segs=64).difference(q.buffer(.1524,quad_segs=64));areas={str(l):ring.intersection(planes[l]).area for l in [15,2]};assert min(areas.values())>=.15;contacts.append(areas)
assert len(capture['pads'])==1079 and len(capture['vias'])==530
meta=dict(updated_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),project=str(PROJECT),pcb_sha256=sha(pcb),source_stable_during_reopened_drc=True,reopened_identity=doc,session_id=native.SESSION,native_drc=dict(clearance=0,physical=0,connection=63),added_vias=result['createdV'],original_nonpour_objects_unchanged=True,actual_ground_reference_contact_mm2=contacts,manufacturing_release=False)
(OUT/'checkpoint-review.json').write_text(json.dumps(meta,indent=2))
remaining=[dict(net=n['name'],open_objects=len(n['list'])) for c in drc if c['name']=='Connection Error' for n in c['list']]
with (OUT/'remaining-networks.csv').open('w',newline='',encoding='utf-8-sig') as f:
 writer=csv.DictWriter(f,fieldnames=['net','open_objects']);writer.writeheader();writer.writerows(remaining)
archive=OUT/'native-bus-return-repaired-WORK-IN-PROGRESS.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in PROJECT.rglob('*'):
  if p.is_file():z.write(p,p.relative_to(PROJECT))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None;assert hashlib.sha256(z.read('pcb/PCB1.epcb2')).hexdigest()==sha(pcb)
meta['native_archive_sha256']=sha(archive);(OUT/'checkpoint-review.json').write_text(json.dumps(meta,indent=2))
pointer=read(ROOT/'REGIONAL-WORK-IN-PROGRESS.json');pointer.update(updated_at=meta['updated_at'],session=native.SESSION,pcb_sha256=meta['pcb_sha256'],source_capture=str(OUT/'checkpoint-capture.json'),drc=str(OUT/'checkpoint-drc.json'),review=str(OUT/'checkpoint-review.json'),readme=str(OUT/'README.md'),native_drc=meta['native_drc'],status='saved_reopened_verified_construction_checkpoint_not_promoted',router_status='R24 terminal without complete nets; no import. BUS_RETURN missing via repaired natively and verified.',next_action='Do not replay R24. Inspect the unescaped MUX/U8 pin corridors and jointly reroute blocking local copper; preserve sensitive sensing/audio and recover affected power/ground. Remaining 63 objects across 14 nets.')
pointer['closed_nets_this_recovery']=list(dict.fromkeys(pointer['closed_nets_this_recovery']+['BUS_RETURN']))
(ROOT/'REGIONAL-WORK-IN-PROGRESS.json').write_text(json.dumps(pointer,indent=2))
summary='2026-10-22 BUS_RETURN 已补缺失换层孔及邻近 GND 孔，保存重开后原生 DRC：0 间距 / 0 物理 / 63 未连通（14 网）；实际交付及最新源哈希见 bus-return-repair-20261022/checkpoint-review.json。R24 未闭合完整网络，未导入。夜间本对话续跑 automation id=pcb，每30分钟唤醒；额度耗尽不能绕过，保留断点接续。\n\n'
for name in ['AUTONOMOUS-CURRENT.md','LATEST.md']:
 p=ROOT/name;p.write_text(summary+p.read_text(encoding='utf8'),encoding='utf8')
print(json.dumps(meta,indent=2),flush=True)
