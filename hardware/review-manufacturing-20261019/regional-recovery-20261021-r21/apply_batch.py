"""Apply only the separately verified batch; preserve R19 and R15."""
from pathlib import Path
import json,hashlib,sys
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,str(BASE))
from native_project import invoke,PROJECT,info
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
audit=json.loads((BASE/'batch-validation.json').read_text())
route=json.loads((BASE/'accepted-batch.json').read_text())
assert audit['geometric_pass'] and sha(PROJECT/'pcb/PCB1.epcb2')==audit['source_pcb_sha256']
assert not (BASE/'native-batch-apply.json').exists(),'Do not replay mutation'
doc=invoke('batch-identity','return await eda.dmt_SelectControl.getCurrentDocumentInfo();')
assert doc['documentType']==3
info['parent_project_uuid']=doc['parentProjectUuid']
(BASE/'native-candidate-source.json').write_text(json.dumps(info,indent=2),encoding='utf8')
code="""
const d=__CLI__.args;const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(doc?.parentProjectUuid!==d.project)throw new Error('Wrong project');let createdL=[],createdV=[];
try{for(const p of d.vias){const q=await eda.pcb_PrimitiveVia.create(p.net,p.x,p.y,p.hole,p.diameter);if(!q)throw new Error('Via');createdV.push(q.getState_PrimitiveId());}
for(const p of d.lines){if(![1,16].includes(p.layer))throw new Error('Layer');const q=await eda.pcb_PrimitiveLine.create(p.net,p.layer,p.x1,p.y1,p.x2,p.y2,p.width,false);if(!q)throw new Error('Line');createdL.push(q.getState_PrimitiveId());}
if(!await eda.pcb_Document.save())throw new Error('Save');return {createdL,createdV};
}catch(e){if(createdL.length)await eda.pcb_PrimitiveLine.delete(createdL);if(createdV.length)await eda.pcb_PrimitiveVia.delete(createdV);await eda.pcb_Document.save();throw e;}
"""
result=invoke('apply-batch',code,dict(project=doc['parentProjectUuid'],**route),180)
(BASE/'native-batch-apply.json').write_text(json.dumps(dict(source_pcb_sha256=audit['source_pcb_sha256'],result=result,manufacturing_release=False),indent=2),encoding='utf8')
for layer in [1,15,16,2]:
    print('REBUILD',layer,invoke('batch-rebuild-'+str(layer),"const ps=(await eda.pcb_PrimitivePour.getAll()).filter(p=>p.getState_Layer()===__CLI__.args.layer);if(ps.length!==1||!await ps[0].rebuildCopperRegion())throw new Error('Rebuild');return await eda.pcb_Document.save();",{'layer':layer},180),flush=True)
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
sys.path.insert(0,str(ROOT))
import grid_route as g
g.invoke=invoke
(BASE/'native-batch-capture.json').write_text(json.dumps(g.capture()),encoding='utf8')
(BASE/'native-batch-meta.json').write_text(json.dumps(dict(pcb_sha256=sha(PROJECT/'pcb/PCB1.epcb2')),indent=2),encoding='utf8')
print('APPLIED',len(result['createdL']),len(result['createdV']),flush=True)
