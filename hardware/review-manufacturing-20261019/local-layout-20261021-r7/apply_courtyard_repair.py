"""Move C35 only in isolated r7, preserve snapshot and explicit rollback."""
import sys,json,hashlib,zipfile
from pathlib import Path
from datetime import datetime
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(BASE));sys.path.insert(0,str(ROOT))
from native_project import invoke,PROJECT,info
import grid_route as g;g.invoke=invoke
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert not (BASE/'native-courtyard-repair-audit.json').exists(),'Do not repeat applied layout'
plan=json.loads((BASE/'decoupling-courtyard-repair-plan.json').read_text(encoding='utf-8'));assert sha(PROJECT/'pcb/PCB1.epcb2')==plan['source_pcb_sha256']
source=json.loads((BASE/'first-position-native-verified-capture.json').read_text(encoding='utf-8'));capture=g.capture();canon=lambda d:{k:sorted(d[k],key=lambda p:p['id']) for k in d}
assert canon(source)==canon(capture)
identity="return {document:await eda.dmt_SelectControl.getCurrentDocumentInfo(),components:(await eda.pcb_PrimitiveComponent.getAll()).map(c=>[c.getState_PrimitiveId(),c.getState_Designator(),c.getState_X(),c.getState_Y(),c.getState_Rotation()]).sort((a,b)=>a[0].localeCompare(b[0])),rules:(await eda.pcb_Drc.getCurrentRuleConfiguration()).config};"
before=invoke('before-decoupling-identity',identity);assert before['document']['parentProjectUuid']==info['parent_project_uuid']
snapshot=Path('D:/FPGA-Project/snapshots')/('before-r7-courtyard-repair-'+datetime.now().strftime('%Y%m%d-%H%M%S'));snapshot.mkdir();archive=snapshot/'native-before-decoupling.zip'
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
 for p in PROJECT.rglob('*'):
  if p.is_file():z.write(p,p.relative_to(PROJECT))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
payload={**plan,'project_uuid':info['parent_project_uuid']}
code="const data="+json.dumps(payload)+";"+"""
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(doc?.parentProjectUuid!==data.project_uuid)throw new Error('Wrong project');
await eda.pcb_Drc.stopRealTimeDrc();let c=(await eda.pcb_PrimitiveComponent.getAll()).find(c=>c.getState_Designator()==='C35');if(!c)throw new Error('C35 absent');
const priorC={x:c.getState_X(),y:c.getState_Y(),rotation:c.getState_Rotation()};const all=await eda.pcb_PrimitiveLine.getAll();const priorL=all.filter(p=>data.remove_line_ids.includes(p.getState_PrimitiveId())).map(p=>({id:p.getState_PrimitiveId(),net:p.getState_Net(),layer:p.getState_Layer(),x1:p.getState_StartX(),y1:p.getState_StartY(),x2:p.getState_EndX(),y2:p.getState_EndY(),width:p.getState_LineWidth()}));
if(priorL.length!==data.remove_line_ids.length)throw new Error('Missing source lines');let createdL=[],createdV=[];let removed=false;
const move=async rotation=>{c=await eda.pcb_PrimitiveComponent.modify(c,{rotation});if(!c)throw new Error('Rotate');let ps=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());const xs=ps.map(p=>p.getState_X()),ys=ps.map(p=>p.getState_Y());c=await eda.pcb_PrimitiveComponent.modify(c,{x:c.getState_X()+data.component_x_mm/.0254-(Math.min(...xs)+Math.max(...xs))/2,y:c.getState_Y()+data.component_y_mm/.0254-(Math.min(...ys)+Math.max(...ys))/2});return await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());};
try{
 let ps=await move(data.component_rotation);let expected=data.pads.find(p=>p.n==='1');let p1=ps.find(p=>p.getState_PadNumber()==='1');
 if(Math.hypot(p1.getState_X()-expected.x,p1.getState_Y()-expected.y)*.0254>.003)ps=await move((data.component_rotation+180)%360);
 for(const p of data.pads){const q=ps.find(q=>q.getState_PadNumber()===p.n);if(!q||q.getState_Net()!==p.net||Math.hypot(q.getState_X()-p.x,q.getState_Y()-p.y)*.0254>.003)throw new Error('Relocated pad mismatch '+p.n);}
 if(!await eda.pcb_PrimitiveLine.delete(data.remove_line_ids))throw new Error('Delete local spurs');removed=true;
 for(const v of data.vias){const q=await eda.pcb_PrimitiveVia.create(v.net,v.x,v.y,v.hole,v.diameter,0,null,null,false);if(!q)throw new Error('New ground via');createdV.push(q.getState_PrimitiveId());}
 for(const l of data.lines){const q=await eda.pcb_PrimitiveLine.create(l.net,l.layer,l.x1,l.y1,l.x2,l.y2,l.width,false);if(!q)throw new Error('Local line');createdL.push(q.getState_PrimitiveId());}
 if(!await eda.pcb_Document.save())throw new Error('Save');
 return {priorC,priorL,createdL,createdV,actual_component:{x:c.getState_X(),y:c.getState_Y(),rotation:c.getState_Rotation()},calibrated_to_actual_pad_numbers:true};
}catch(error){
 if(createdL.length)await eda.pcb_PrimitiveLine.delete(createdL);if(createdV.length)await eda.pcb_PrimitiveVia.delete(createdV);c=await eda.pcb_PrimitiveComponent.modify(c,priorC);
 if(removed)for(const l of priorL)await eda.pcb_PrimitiveLine.create(l.net,l.layer,l.x1,l.y1,l.x2,l.y2,l.width,false);await eda.pcb_Document.save();throw error;
}
"""
result=invoke('apply-courtyard-repair',code,timeout=180);after=g.capture();ident=invoke('after-decoupling-identity',identity)
assert [c for c in before['components'] if c[1]!='C35']==[c for c in ident['components'] if c[1]!='C35']
assert sorted([p for p in source['pads'] if p['ref']!='C35'],key=lambda p:p['id'])==sorted([p for p in after['pads'] if p['ref']!='C35'],key=lambda p:p['id'])
assert before['rules']==ident['rules']
assert {p['id']:p for p in source['lines'] if p['id'] not in plan['remove_line_ids']}=={p['id']:p for p in after['lines'] if p['id'] not in result['createdL']}
assert {p['id']:p for p in source['vias']}=={p['id']:p for p in after['vias'] if p['id'] not in result['createdV']}
audit=dict(snapshot=str(archive),snapshot_sha256=sha(archive),source_pcb_sha256=plan['source_pcb_sha256'],plan_sha256=sha(BASE/'decoupling-courtyard-repair-plan.json'),result=result,other_229_components_pads_rules_copper_unchanged=True,manufacturing_release=False)
(BASE/'native-courtyard-repair-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8');(BASE/'native-applied-capture.json').write_text(json.dumps(after,indent=2),encoding='utf-8')
assert all(sha(Path(info['source_project'])/p)==h for p,h in info['source_files'].items());print(json.dumps(audit,indent=2),flush=True)
