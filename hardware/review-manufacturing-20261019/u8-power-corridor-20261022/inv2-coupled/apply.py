"""Apply this reviewed copper repair once; retain a verified native recovery ZIP."""
from pathlib import Path
import sys,json,hashlib,zipfile
O=Path(__file__).resolve().parent;B=O.parent;R=B.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(R));sys.path.insert(0,str(B))
import native_project as n
from resume_offline import read_native
import grid_route as g
rd=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p=rd(O/'validated-copper-plan.json');audit=rd(O/'full-preflight.json');pcb=n.PROJECT/'pcb/PCB1.epcb2'
assert audit['geometric_pass'] and not audit['failures']
assert not (O/'native-apply.json').exists(),'Never replay primitive creation'
assert not (O/'native-state.json').exists(),'Read and resume the existing transaction instead'
assert sha(pcb)==p['source_pcb_sha256']=='8b9b68a5f42a446b2c716e41d6693f480fb9c8048e6c1c7080b151244978aa19'
archive=Path(rd(B/'checkpoint-review.json')['archive'])
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 assert hashlib.sha256(z.read('pcb/PCB1.epcb2')).hexdigest()==p['source_pcb_sha256']
doc=n.invoke('inv2-source-identity','return await eda.dmt_SelectControl.getCurrentDocumentInfo();',timeout=35)
assert doc['documentType']==3 and doc['parentProjectUuid']==n.info['parent_project_uuid']
before=dict(project=str(n.PROJECT),session=n.SESSION,source_pcb_sha256=sha(pcb),source_archive=str(archive),source_archive_sha256=sha(archive),plan_sha256=sha(O/'validated-copper-plan.json'),preflight_sha256=sha(O/'full-preflight.json'),files={str(f.relative_to(n.PROJECT)).replace('\\','/'):sha(f) for f in n.PROJECT.rglob('*') if f.is_file()})
(O/'native-before.json').write_text(json.dumps(before,indent=2),encoding='utf8')
state=dict(phase='preflight_pass_native_mutation_starting',source_pcb_sha256=before['source_pcb_sha256'],source_archive=str(archive),session=n.SESSION,native_replay_forbidden=True)
def save_state(phase):
 state.update(phase=phase,pcb_sha256=sha(pcb));(O/'native-state.json').write_text(json.dumps(state,indent=2),encoding='utf8')
save_state(state['phase'])
pointer=rd(R/'REGIONAL-WORK-IN-PROGRESS.json');pointer['pending_trial']=dict(project=str(n.PROJECT),session=n.SESSION,source_pcb_sha256=before['source_pcb_sha256'],source_archive=str(archive),entry=str(O/'native-state.json'),next_action='Inspect transaction state; never repeat creation. After saved57, reopen and audit real copper/ground before promoting. On failure, preserve evidence and restore verified59 ZIP only with owned document closed.');(R/'REGIONAL-WORK-IN-PROGRESS.json').write_text(json.dumps(pointer,indent=2),encoding='utf8')
code="""
const a=__CLI__.args;const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(doc?.parentProjectUuid!==a.project||doc?.documentType!==3)throw new Error('Wrong PCB');await eda.pcb_Drc.stopRealTimeDrc();const createdL=[],createdV=[];
try{
await eda.pcb_PrimitiveLine.delete(a.remove_lines.map(p=>p.id));await eda.pcb_PrimitiveVia.delete(a.remove_vias.map(p=>p.id));
for(const p of a.vias){const q=await eda.pcb_PrimitiveVia.create(p.net,p.x,p.y,p.hole,p.diameter);if(!q)throw new Error('Via creation');createdV.push(q.getState_PrimitiveId());}
for(const p of a.lines){if(![1,16,2].includes(p.layer))throw new Error('Unexpected layer');const q=await eda.pcb_PrimitiveLine.create(p.net,p.layer,p.x1,p.y1,p.x2,p.y2,p.width,false);if(!q)throw new Error('Line creation');createdL.push(q.getState_PrimitiveId());}
if(!await eda.pcb_Document.save())throw new Error('Save');return {ok:true,createdL,createdV};
}catch(e){return {ok:false,error:String(e),createdL,createdV,partial_native_state_requires_review:true};}
"""
result=n.invoke('inv2-apply-reviewed-copper',code,{**p,'project':doc['parentProjectUuid']},180)
(O/'native-apply.json').write_text(json.dumps(result,indent=2),encoding='utf8');assert result['ok'],result
save_state('saved_copper_edit_pours_pending');print('APPLIED',len(result['createdL']),len(result['createdV']),flush=True)
for layer in [1,15,16,2]:
 result=n.invoke('inv2-rebuild-'+str(layer),"const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(d?.parentProjectUuid!==__CLI__.args.project)throw new Error('Wrong PCB');const ps=(await eda.pcb_PrimitivePour.getAll()).filter(p=>p.getState_Layer()===__CLI__.args.layer);if(ps.length!==1||!await ps[0].rebuildCopperRegion())throw new Error('Rebuild');return await eda.pcb_Document.save();",dict(project=doc['parentProjectUuid'],layer=layer),180)
 assert result;save_state('rebuilt_saved_layer_'+str(layer));print('REBUILT',layer,flush=True)
drc=n.invoke('inv2-strict-drc','return await eda.pcb_Drc.check(true,false,true);',timeout=180)
(O/'native-stage-drc.json').write_text(json.dumps(drc,indent=2),encoding='utf8');counts={c['name']:sum(len(v.get('list',[])) for v in c.get('list',[])) for c in drc};print('DRC',counts,flush=True)
g.invoke=n.invoke;cap=g.capture();raw=read_native(pcb)
cap['lines']=[dict(id=i,net=z['netName'],layer=z['layerId'],x1=z['startX'],y1=z['startY'],x2=z['endX'],y2=z['endY'],width=z['width']) for (k,i),z in raw.items() if k=='LINE' and z.get('layerId') in [1,15,16,2]]
cap['vias']=[dict(id=i,net=z['netName'],x=z['centerX'],y=z['centerY'],diameter=z['viaDiameter'],hole=z['holeDiameter']) for (k,i),z in raw.items() if k=='VIA']
(O/'native-stage-capture.json').write_text(json.dumps(cap),encoding='utf8')
save_state('saved_strict_DRC_'+str(counts)+'_reopen_and_reference_review_pending')
assert counts=={'Connection Error':57},counts
assert not any(v['name'] in ['INV2','GND','3V3_PERIPH','BUS_SCK','INPUT_LOAD_N','3V3_IO','5V_PERIPH'] for c in drc for v in c.get('list',[]))
