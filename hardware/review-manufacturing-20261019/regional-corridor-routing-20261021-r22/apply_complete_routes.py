"""Apply only three fully validated reconnections to the existing isolated regional project."""
from pathlib import Path
import sys,json,hashlib
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent;BASE=ROOT/'regional-recovery-20261021-r21'
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BASE))
from native_project import invoke,PROJECT,info
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
audit=json.loads((OUT/'complete-routes-validation.json').read_text(encoding='utf8'));route=json.loads((OUT/'accepted-complete-copper.json').read_text(encoding='utf8'))
assert audit['geometric_pass'] and sha(PROJECT/'pcb/PCB1.epcb2')==audit['source_pcb_sha256']
assert not (OUT/'native-complete-routes-apply.json').exists()
code="""
const d=__CLI__.args;const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(doc?.parentProjectUuid!==d.project)throw new Error('Wrong project');let createdL=[],createdV=[];
try{for(const p of d.vias){const q=await eda.pcb_PrimitiveVia.create(p.net,p.x,p.y,p.hole,p.diameter);if(!q)throw new Error('Via');createdV.push(q.getState_PrimitiveId());}
for(const p of d.lines){if(![1,16].includes(p.layer))throw new Error('Layer');const q=await eda.pcb_PrimitiveLine.create(p.net,p.layer,p.x1,p.y1,p.x2,p.y2,p.width,false);if(!q)throw new Error('Line');createdL.push(q.getState_PrimitiveId());}
if(!await eda.pcb_Document.save())throw new Error('Save');return {createdL,createdV};
}catch(e){if(createdL.length)await eda.pcb_PrimitiveLine.delete(createdL);if(createdV.length)await eda.pcb_PrimitiveVia.delete(createdV);await eda.pcb_Document.save();throw e;}
"""
result=invoke('apply-complete-reconnections',code,dict(project=info['parent_project_uuid'],**route),180)
(OUT/'native-complete-routes-apply.json').write_text(json.dumps(dict(source_pcb_sha256=audit['source_pcb_sha256'],result=result,selected_nets=audit['selected'],manufacturing_release=False),indent=2),encoding='utf8')
for l in [1,15,16,2]:
    print('REBUILD',l,invoke('reconnections-rebuild-'+str(l),"const ps=(await eda.pcb_PrimitivePour.getAll()).filter(p=>p.getState_Layer()===__CLI__.args.layer);if(ps.length!==1||!await ps[0].rebuildCopperRegion())throw new Error('Rebuild');return await eda.pcb_Document.save();",{'layer':l},180),flush=True)
import grid_route as g;g.invoke=invoke
(OUT/'native-capture.json').write_text(json.dumps(g.capture()),encoding='utf8')
(OUT/'native-source.json').write_text(json.dumps(dict(pcb_sha256=sha(PROJECT/'pcb/PCB1.epcb2'),stage='reconnections_applied_reference_check_pending',manufacturing_release=False),indent=2),encoding='utf8')
print(json.dumps(result,indent=2),flush=True)
