"""Apply an independently checked local modify-only patch exactly once."""
from pathlib import Path
import sys,json,hashlib,zipfile,shutil,importlib.util
HOME=Path(__file__).resolve().parent;O=HOME.parent;R=O.parent.parent
D=Path(sys.argv[1]).resolve();assert D.is_relative_to(HOME)
rd=lambda p:json.loads(p.read_text(encoding='utf8'))
wr=lambda p,x:p.write_text(json.dumps(x,indent=2),encoding='utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p=rd(D/'patch.json');st=rd(O/'native-state.json');info=rd(O/'native-candidate-source.json');project=Path(info['candidate_project']);pcb=project/'pcb/PCB1.epcb2'
assert sha(pcb)==p['source_pcb_sha256']==st['pcb_sha256'];assert not (D/'native-state.json').exists(),'Never replay a native patch'
assert p['modify_vias'] and all(v['complete'] for v in p['continuity'].values())
if p.get('ground_return_review'):assert all(v['gap_mm']<1e-5 for v in p['ground_return_review']['modified_track_projections'] if v['layer']==16)
archive=D/'source-native-WORK-IN-PROGRESS.zip';assert not archive.exists()
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for f in project.rglob('*'):
  if f.is_file():z.write(f,f.relative_to(project).as_posix())
with zipfile.ZipFile(archive) as z:assert z.testzip() is None and hashlib.sha256(z.read('pcb/PCB1.epcb2')).hexdigest()==p['source_pcb_sha256']
for name in ['native-stage-capture.json','native-stage-review.json','native-state.json']:shutil.copy2(O/name,D/('source-'+name))
spec=importlib.util.spec_from_file_location('addr3_native',O/'native_project.py');n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
doc=n.invoke('local-patch-'+D.name+'-identity','return await eda.dmt_SelectControl.getCurrentDocumentInfo();',timeout=35);assert doc['documentType']==3 and doc['parentProjectUuid']==info['parent_project_uuid']
state=dict(phase='native_modify_starting',source_pcb_sha256=p['source_pcb_sha256'],source_archive=str(archive),patch_sha256=sha(D/'patch.json'),parent_state=st,native_replay_forbidden=True);wr(D/'native-state.json',state)
code="""
const a=__CLI__.args,d=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(d?.parentProjectUuid!==a.project||d?.documentType!==3)throw new Error('Wrong PCB');await eda.pcb_Drc.stopRealTimeDrc();const changedV=[],changedL=[];
for(const z of a.modify_vias){const b=await eda.pcb_PrimitiveVia.get(z.before.id);if(!b||Math.hypot(b.getState_X()-z.before.x,b.getState_Y()-z.before.y)>.001)throw new Error('Via before mismatch');if(!await eda.pcb_PrimitiveVia.modify(z.before.id,{x:z.after.x,y:z.after.y}))throw new Error('Via modify');const q=await eda.pcb_PrimitiveVia.get(z.before.id);if(Math.hypot(q.getState_X()-z.after.x,q.getState_Y()-z.after.y)>.001)throw new Error('Via after mismatch');changedV.push(z.before.id);}
for(const z of a.modify_lines){const b=await eda.pcb_PrimitiveLine.get(z.before.id);if(!b||Math.hypot(b.getState_StartX()-z.before.x1,b.getState_StartY()-z.before.y1)>.001||Math.hypot(b.getState_EndX()-z.before.x2,b.getState_EndY()-z.before.y2)>.001)throw new Error('Line before mismatch');if(!await eda.pcb_PrimitiveLine.modify(z.before.id,{startX:z.after.x1,startY:z.after.y1,endX:z.after.x2,endY:z.after.y2}))throw new Error('Line modify');const q=await eda.pcb_PrimitiveLine.get(z.before.id);if(Math.hypot(q.getState_StartX()-z.after.x1,q.getState_StartY()-z.after.y1)>.001||Math.hypot(q.getState_EndX()-z.after.x2,q.getState_EndY()-z.after.y2)>.001)throw new Error('Line after mismatch');changedL.push(z.before.id);}
if(!await eda.pcb_Document.save())throw new Error('Save');return {changedV,changedL};
"""
result=n.invoke('local-patch-'+D.name+'-modify',code,dict(p,project=info['parent_project_uuid']),180);wr(D/'native-apply.json',result)
st.update(phase='reference_patch_saved_pours_pending',pcb_sha256=sha(pcb),latest_expected_capture=str(D/'expected-capture.json'),latest_patch=str(D/'patch.json'));wr(O/'native-state.json',st);print('MODIFIED',result,flush=True)
for layer in [1,15,16,2]:
 assert n.invoke('local-patch-'+D.name+'-rebuild-'+str(layer),"const a=__CLI__.args,d=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(d?.parentProjectUuid!==a.project)throw new Error('Wrong PCB');const ps=(await eda.pcb_PrimitivePour.getAll()).filter(p=>p.getState_Layer()===a.layer);if(ps.length!==1||!await ps[0].rebuildCopperRegion())throw new Error('Rebuild');return await eda.pcb_Document.save();",dict(project=info['parent_project_uuid'],layer=layer),180)
 st.update(phase='local_reference_rebuilt_saved_'+str(layer),pcb_sha256=sha(pcb));wr(O/'native-state.json',st);print('REBUILT',layer,flush=True)
drc=n.invoke('local-patch-'+D.name+'-strict-drc','return await eda.pcb_Drc.check(true,false,true);',timeout=180);wr(D/'strict-drc.json',drc);counts={c['name']:sum(len(v.get('list',[])) for v in c.get('list',[])) for c in drc};st.update(phase='local_reference_strict_drc_actual_review_pending',pcb_sha256=sha(pcb),drc=counts);wr(O/'native-state.json',st);state.update(phase=st['phase'],pcb_sha256=st['pcb_sha256'],drc=counts);wr(D/'native-state.json',state)
pointer=rd(R/'REGIONAL-WORK-IN-PROGRESS.json');pointer['pending_trial'].update(pcb_sha256=st['pcb_sha256'],status=st['phase'],latest_patch=str(D/'patch.json'));wr(R/'REGIONAL-WORK-IN-PROGRESS.json',pointer)
print('DRC',counts,flush=True);assert counts=={'Connection Error':50}
