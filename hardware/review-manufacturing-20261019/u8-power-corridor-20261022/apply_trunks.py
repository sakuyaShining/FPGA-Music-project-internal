"""Append only independently checked complete clock/recovery trunks."""
from pathlib import Path
import sys,json,hashlib,zipfile
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,str(OUT));from native_project import invoke,PROJECT,SESSION,info
read=lambda p:json.loads(p.read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
audit=read(OUT/'complete-trunk-preflight.json');route=read(OUT/'grid-trunks.json');assert audit['geometric_pass']
assert not (OUT/'native-trunks-apply.json').exists(),'Do not replay copper creation'
assert sha(PROJECT/'pcb/PCB1.epcb2')==read(OUT/'native-stage-meta.json')['pcb_sha256']
assert {n['net'] for n in route['nets']}=={'BUS_SCK','INPUT_LOAD_N'}
doc=invoke('trunks-identity','return await eda.dmt_SelectControl.getCurrentDocumentInfo();',timeout=35)
assert doc['documentType']==3 and doc['parentProjectUuid']==info['parent_project_uuid']
p=ROOT/'REGIONAL-WORK-IN-PROGRESS.json';pointer=read(p);pointer['session']=read(ROOT/'regional-recovery-20261021-r21/native-session.json')['sessionId'];pointer['pending_trial']['session']=SESSION;pointer['pending_trial']['next_action']='Complete local BUS_SCK and INPUT_LOAD_N trunks passed independent validation; append once, rebuild and verify before any promotion.';p.write_text(json.dumps(pointer,indent=2))
with zipfile.ZipFile(OUT/'before-trunk-append.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in PROJECT.rglob('*'):
  if p.is_file():z.write(p,p.relative_to(PROJECT))
code="""
const d=__CLI__.args;const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(doc?.parentProjectUuid!==d.project)throw new Error('Wrong project');await eda.pcb_Drc.stopRealTimeDrc();let createdL=[],createdV=[];
try{for(const p of d.vias){const q=await eda.pcb_PrimitiveVia.create(p.net,p.x,p.y,p.hole,p.diameter);if(!q)throw new Error('Via');createdV.push(q.getState_PrimitiveId());}
for(const p of d.lines){if(![1,16].includes(p.layer))throw new Error('Layer');const q=await eda.pcb_PrimitiveLine.create(p.net,p.layer,p.x1,p.y1,p.x2,p.y2,p.width,false);if(!q)throw new Error('Line');createdL.push(q.getState_PrimitiveId());}
if(!await eda.pcb_Document.save())throw new Error('Save');return {createdL,createdV};
}catch(e){if(createdL.length)await eda.pcb_PrimitiveLine.delete(createdL);if(createdV.length)await eda.pcb_PrimitiveVia.delete(createdV);await eda.pcb_Document.save();throw e;}
"""
result=invoke('append-complete-trunks',code,dict(project=doc['parentProjectUuid'],lines=route['lines'],vias=route['vias']),180);(OUT/'native-trunks-apply.json').write_text(json.dumps(result,indent=2));print('APPLIED',len(result['createdL']),len(result['createdV']),flush=True)
for layer in [1,15,16,2]:
 print('REBUILD',layer,invoke('trunks-rebuild-'+str(layer),"const ps=(await eda.pcb_PrimitivePour.getAll()).filter(p=>p.getState_Layer()===__CLI__.args.layer);if(ps.length!==1||!await ps[0].rebuildCopperRegion())throw new Error('Rebuild');return await eda.pcb_Document.save();",dict(layer=layer),180),flush=True)
drc=invoke('trunks-full-drc','return await eda.pcb_Drc.check(true,false,true);',timeout=180);(OUT/'after-trunks-drc.json').write_text(json.dumps(drc,indent=2))
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT));import grid_route as g;g.invoke=invoke
(OUT/'after-trunks-capture.json').write_text(json.dumps(g.capture()));(OUT/'after-trunks-meta.json').write_text(json.dumps(dict(pcb_sha256=sha(PROJECT/'pcb/PCB1.epcb2')),indent=2));print('DRC',[(c['name'],c.get('count')) for c in drc],flush=True)
