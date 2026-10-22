"""One recoverable native copy, no changes to the verified source57 project."""
from pathlib import Path
import sys,json,hashlib,shutil,zipfile
O=Path(__file__).resolve().parent;B=O.parent;R=B.parent
sys.path[:0]=[str(R),str(O)]
from native_review import call
rd=lambda p:json.loads(p.read_text(encoding='utf8'))
wr=lambda p,x:p.write_text(json.dumps(x,indent=2),encoding='utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=rd(O/'grounded-plan.json');review=rd(O/'full-preflight.json');ground=rd(O/'ground-preflight.json')
assert review['geometric_pass'] and not review['failures'];assert all(p['complete'] for p in review['continuity'].values())
assert ground['base_preflight_sha256']==sha(O/'full-preflight.json')
assert not (O/'native-state.json').exists(),'Inspect existing native transaction; never replay creation'
source=Path(rd(R/'REGIONAL-WORK-IN-PROGRESS.json')['project']);assert sha(source/'pcb/PCB1.epcb2')==plan['source_pcb_sha256']
archive=Path(rd(B/'inv2-coupled/checkpoint-review.json')['archive'])
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None and hashlib.sha256(z.read('pcb/PCB1.epcb2')).hexdigest()==plan['source_pcb_sha256']
project=source.parent/'FPGA-Music-Dualscreen-Addr3Work-20261022'
if (O/'native-candidate-source.json').exists():
 info=rd(O/'native-candidate-source.json');files=info['source_files'];session=rd(O/'native-session.json');descriptor=Path(info['candidate_descriptor'])
 assert Path(info['candidate_project'])==project and sha(project/'pcb/PCB1.epcb2')==plan['source_pcb_sha256']
 sessions=call('addr3-resume-existing-session',['session','list'],45)
 assert any(x['sessionId']==session['sessionId'] and x['status']=='alive' and Path(x['path'])==descriptor for x in sessions),'Inspect owned session; do not reopen blindly'
else:
 assert not project.exists();files={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*') if p.is_file()}
 shutil.copytree(source,project);old=project/(source.name+'.eprj3');desc=rd(old);desc.update(name=project.name,content='ADDR3 seven-node closure with two sensing nets recovered; independent construction checkpoint, NOT FOR FABRICATION.');descriptor=project/(project.name+'.eprj3');wr(descriptor,desc);old.unlink()
 info=dict(source_project=str(source),source_files=files,source_pcb_sha256=plan['source_pcb_sha256'],source_archive=str(archive),candidate_project=str(project),candidate_descriptor=str(descriptor),manufacturing_release=False)
 wr(O/'native-candidate-source.json',info)
 session=call('addr3-native-open',['open','--path',str(descriptor),'--headless','true'],120);wr(O/'native-session.json',session)
wrapper=(B/'native_project.py').read_text(encoding='utf8').replace('ROOT=BASE.parent','ROOT=BASE.parent.parent').replace("'u8-native-'","'addr3-native-'")
(O/'native_project.py').write_text(wrapper,encoding='utf8')
import importlib.util
spec=importlib.util.spec_from_file_location('addr3_native_project',O/'native_project.py');n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
doc=None
for i in range(5):
 docs=n.invoke('ready-'+str(i),'await new Promise(r=>setTimeout(r,2000));return await eda.dmt_Pcb.getAllPcbsInfo();',timeout=35)
 if not docs:continue
 n.invoke('open-pcb-'+str(i),"return await eda.dmt_EditorControl.openDocument('c3fd8656cf425e9f');",timeout=55)
 doc=n.invoke('identity-'+str(i),'return await eda.dmt_SelectControl.getCurrentDocumentInfo();',timeout=35)
 if doc and doc.get('documentType')==3:break
assert doc and doc['documentType']==3 and doc['parentProjectUuid']!=rd(B/'native-candidate-source.json')['parent_project_uuid']
info['parent_project_uuid']=doc['parentProjectUuid'];wr(O/'native-candidate-source.json',info);assert sha(project/'pcb/PCB1.epcb2')==plan['source_pcb_sha256']
state=dict(phase='native_mutation_starting',source_pcb_sha256=plan['source_pcb_sha256'],project=str(project),session=session['sessionId'],parent_project_uuid=doc['parentProjectUuid'],plan_sha256=sha(O/'grounded-plan.json'),native_replay_forbidden=True)
def phase(s):
 state.update(phase=s,pcb_sha256=sha(project/'pcb/PCB1.epcb2'));wr(O/'native-state.json',state)
phase(state['phase']);pointer=rd(R/'REGIONAL-WORK-IN-PROGRESS.json');pointer['pending_trial']=dict(project=str(project),session=session['sessionId'],entry=str(O/'native-state.json'),source_pcb_sha256=plan['source_pcb_sha256'],next_action='Inspect transaction, never replay primitive creation. Finish pours, strict DRC, save/reopen and actual reference review before promotion. Verified source57 is untouched.');wr(R/'REGIONAL-WORK-IN-PROGRESS.json',pointer)
code="""
const a=__CLI__.args,d=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(d?.parentProjectUuid!==a.project||d?.documentType!==3)throw new Error('Wrong PCB');await eda.pcb_Drc.stopRealTimeDrc();const createdL=[],createdV=[];
try{await eda.pcb_PrimitiveLine.delete(a.remove_lines.map(p=>p.id));await eda.pcb_PrimitiveVia.delete(a.remove_vias.map(p=>p.id));
for(const p of a.vias){const q=await eda.pcb_PrimitiveVia.create(p.net,p.x,p.y,p.hole,p.diameter);if(!q)throw new Error('Via create');createdV.push(q.getState_PrimitiveId());}
for(const p of a.lines){if(![1,16,2].includes(p.layer))throw new Error('Layer');const q=await eda.pcb_PrimitiveLine.create(p.net,p.layer,p.x1,p.y1,p.x2,p.y2,p.width,false);if(!q)throw new Error('Line create');createdL.push(q.getState_PrimitiveId());}
if(!await eda.pcb_Document.save())throw new Error('Save');return {ok:true,createdL,createdV};}catch(e){return {ok:false,error:String(e),createdL,createdV,partial_native_state_requires_review:true};}
"""
result=n.invoke('apply-once',code,dict(plan,project=doc['parentProjectUuid']),180);wr(O/'native-apply.json',result);assert result['ok'],result;phase('saved_copper_pours_pending');print('APPLIED',len(result['createdL']),len(result['createdV']),flush=True)
for layer in [1,15,16,2]:
 result=n.invoke('rebuild-'+str(layer),"const a=__CLI__.args,d=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(d?.parentProjectUuid!==a.project)throw new Error('Wrong PCB');const ps=(await eda.pcb_PrimitivePour.getAll()).filter(p=>p.getState_Layer()===a.layer);if(ps.length!==1||!await ps[0].rebuildCopperRegion())throw new Error('Rebuild');return await eda.pcb_Document.save();",dict(project=doc['parentProjectUuid'],layer=layer),180)
 assert result;phase('rebuilt_saved_layer_'+str(layer));print('REBUILT',layer,flush=True)
drc=n.invoke('strict-drc','return await eda.pcb_Drc.check(true,false,true);',timeout=180);wr(O/'native-stage-drc.json',drc);counts={c['name']:sum(len(v.get('list',[])) for v in c.get('list',[])) for c in drc};state['drc']=counts;phase('strict_drc_saved_reopen_reference_review_pending');print('DRC',counts,flush=True)
assert counts=={'Connection Error':50},counts
assert all(sha(source/p)==h for p,h in files.items()),'Verified source changed'
