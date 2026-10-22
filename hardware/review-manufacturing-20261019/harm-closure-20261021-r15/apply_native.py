"""Apply reviewed R30/HARM candidate only to its isolated R15 session."""
from pathlib import Path
import sys,json,hashlib
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BASE))
from native_project import invoke,PROJECT,info
import grid_route as g
g.invoke=invoke
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert not (BASE/'native-apply-audit.json').exists(),'Do not replay applied trial'
plan=json.loads((BASE/'plan.json').read_text(encoding='utf-8'))
assert sha(PROJECT/'pcb/PCB1.epcb2')==plan['source_pcb_sha256']
before=g.capture();expected=json.loads((ROOT/'local-layout-20261021-r7/native-verified-capture.json').read_text(encoding='utf-8'))
canonical=lambda d:{k:sorted(v,key=lambda p:p['id']) for k,v in d.items()}
assert canonical(before)==canonical(expected),'Candidate no longer matches R7 capture'
identity="return {document:await eda.dmt_SelectControl.getCurrentDocumentInfo(),components:(await eda.pcb_PrimitiveComponent.getAll()).map(c=>[c.getState_PrimitiveId(),c.getState_Designator(),c.getState_X(),c.getState_Y(),c.getState_Rotation()]).sort((a,b)=>a[0].localeCompare(b[0])),rules:await eda.pcb_Drc.getCurrentRuleConfiguration()};"
prior=invoke('before-apply-identity',identity);assert prior['document']['parentProjectUuid']==info['parent_project_uuid']
(BASE/'native-before-capture.json').write_text(json.dumps(before),encoding='utf-8')
(BASE/'native-before-identity.json').write_text(json.dumps(prior,indent=2),encoding='utf-8')
payload={**plan,'project_uuid':info['parent_project_uuid']}
code='const data='+json.dumps(payload)+';'+'''
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(doc?.parentProjectUuid!==data.project_uuid)throw new Error('Wrong isolated project');
const Layers={TOP:1,INNER_2:16};const map={1:Layers.TOP,16:Layers.INNER_2};
await eda.pcb_Drc.stopRealTimeDrc();let c=(await eda.pcb_PrimitiveComponent.getAll()).find(c=>c.getState_Designator()==='R30');if(!c)throw new Error('R30 absent');
const rid=c.getState_PrimitiveId();const prior={x:c.getState_X(),y:c.getState_Y(),rotation:c.getState_Rotation()};let createdL=[],createdV=[];
const refresh=async()=>{c=(await eda.pcb_PrimitiveComponent.getAll()).find(c=>c.getState_PrimitiveId()===rid);if(!c)throw new Error('R30 disappeared');};
const move=async rotation=>{
if(!await eda.pcb_PrimitiveComponent.modify(rid,{rotation}))throw new Error('R30 rotation');await refresh();
let ps=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(rid);const xs=ps.map(p=>p.getState_X()),ys=ps.map(p=>p.getState_Y());
if(!await eda.pcb_PrimitiveComponent.modify(rid,{x:c.getState_X()+data.component_x_mm/.0254-(Math.min(...xs)+Math.max(...xs))/2,y:c.getState_Y()+data.component_y_mm/.0254-(Math.min(...ys)+Math.max(...ys))/2}))throw new Error('R30 translation');
await refresh();return await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(rid);};
try{
 let ps=await move(data.component_rotation);const expected=data.pads.find(p=>p.n==='1');let p1=ps.find(p=>p.getState_PadNumber()==='1');
 if(Math.hypot(p1.getState_X()-expected.x,p1.getState_Y()-expected.y)*.0254>.003)ps=await move((data.component_rotation+180)%360);
 for(const p of data.pads){const q=ps.find(q=>q.getState_PadNumber()===p.n);if(!q||q.getState_Net()!==p.net||Math.hypot(q.getState_X()-p.x,q.getState_Y()-p.y)*.0254>.003)throw new Error('Moved pad mismatch '+p.n);}
 for(const v of data.vias){const q=await eda.pcb_PrimitiveVia.create(v.net,v.x,v.y,v.hole,v.diameter);if(!q)throw new Error('Signal via create');createdV.push(q.getState_PrimitiveId());}
 for(const l of data.lines){if(map[l.layer]===undefined)throw new Error('Unapproved layer');const q=await eda.pcb_PrimitiveLine.create(l.net,map[l.layer],l.x1,l.y1,l.x2,l.y2,l.width,false);if(!q)throw new Error('Track create');createdL.push(q.getState_PrimitiveId());}
 if(!await eda.pcb_Document.save())throw new Error('Save failed');
 return {prior,createdL,createdV,actual_component:{id:rid,x:c.getState_X(),y:c.getState_Y(),rotation:c.getState_Rotation()},calibrated_to_actual_pad_numbers:true};
}catch(error){
 if(createdL.length)await eda.pcb_PrimitiveLine.delete(createdL);if(createdV.length)await eda.pcb_PrimitiveVia.delete(createdV);await eda.pcb_PrimitiveComponent.modify(rid,prior);await eda.pcb_Document.save();throw error;
}
'''
(BASE/'native-mutation-state.json').write_text(json.dumps(dict(state='applying',plan_sha256=sha(BASE/'plan.json'),source_pcb_sha256=plan['source_pcb_sha256']),indent=2),encoding='utf-8')
result=invoke('apply-harm',code,timeout=180)
after=g.capture();ident=invoke('after-apply-identity',identity)
assert [p for p in prior['components'] if p[1]!='R30']==[p for p in ident['components'] if p[1]!='R30']
assert sorted([p for p in before['pads'] if p['ref']!='R30'],key=lambda p:p['id'])==sorted([p for p in after['pads'] if p['ref']!='R30'],key=lambda p:p['id'])
assert prior['rules']==ident['rules']
for old in before['vias']:assert old in after['vias']
audit=dict(source_pcb_sha256=plan['source_pcb_sha256'],applied_pcb_sha256=sha(PROJECT/'pcb/PCB1.epcb2'),plan_sha256=sha(BASE/'plan.json'),result=result,
           unchanged_other229_components_pads_rules_and_existing_vias=True,native_full_drc_pending=True,manufacturing_release=False)
(BASE/'native-apply-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
(BASE/'native-applied-capture.json').write_text(json.dumps(after),encoding='utf-8')
(BASE/'native-mutation-state.json').write_text(json.dumps(dict(state='applied_pending_drc',audit='native-apply-audit.json'),indent=2),encoding='utf-8')
assert all(sha(Path(info['source_project'])/r)==v for r,v in info['source_files'].items())
print(json.dumps(audit,indent=2),flush=True)
