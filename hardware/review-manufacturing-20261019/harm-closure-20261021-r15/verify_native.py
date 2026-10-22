"""Rebuild actual ground pours, save/reopen and check the isolated R15 PCB."""
from pathlib import Path
from datetime import datetime,timezone
import sys,json,hashlib
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BASE))
from native_project import invoke,PROJECT,info
import grid_route as g
g.invoke=invoke
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();pcb=PROJECT/'pcb/PCB1.epcb2'
assert (BASE/'native-apply-audit.json').exists()
assert not (BASE/'native-drc.json').exists(),'Inspect prior DRC before repeating verification'
for layer in [1,15,16,2]:
    value=invoke('rebuild-ground-'+str(layer),"const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(d?.parentProjectUuid!==__CLI__.args.project)throw new Error('Wrong project');const ps=(await eda.pcb_PrimitivePour.getAll()).filter(p=>p.getState_Layer()===__CLI__.args.layer&&p.getState_Net()==='GND');if(ps.length!==1)throw new Error('Ground count');if(!await ps[0].rebuildCopperRegion())throw new Error('Rebuild');if(!await eda.pcb_Document.save())throw new Error('Save');return {layer:__CLI__.args.layer,saved:true};",dict(layer=layer,project=info['parent_project_uuid']),180)
    print('REBUILT',value,flush=True)
invoke('save-close-reopen',"if(!await eda.pcb_Document.save())throw new Error('Save');const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(d?.parentProjectUuid!==__CLI__.args.project)throw new Error('Wrong project');if(!await eda.dmt_EditorControl.closeDocument(d.tabId))throw new Error('Close');return await eda.dmt_EditorControl.openDocument('c3fd8656cf425e9f');",dict(project=info['parent_project_uuid']),120)
identity=invoke('reopened-identity',"await eda.pcb_Drc.stopRealTimeDrc();return {document:await eda.dmt_SelectControl.getCurrentDocumentInfo(),layers:await eda.pcb_Layer.getTheNumberOfCopperLayers()};")
assert identity['document']['parentProjectUuid']==info['parent_project_uuid'] and identity['layers']==4
before=sha(pcb);drc=invoke('full-drc','return await eda.pcb_Drc.check(true,false,true);',timeout=300);after=sha(pcb)
(BASE/'native-drc.json').write_text(json.dumps(drc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
meta=dict(utc=datetime.now(timezone.utc).isoformat(),pcb_sha256_before=before,pcb_sha256_after=after,source_stable=before==after,reopened_identity=identity,manufacturing_release=False)
(BASE/'native-drc-meta.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
assert before==after
capture=g.capture();(BASE/'native-verified-capture.json').write_text(json.dumps(capture,indent=2),encoding='utf-8')
assert all(sha(Path(info['source_project'])/r)==v for r,v in info['source_files'].items())
print('DRC',[(x['name'],x.get('count')) for x in drc],flush=True)
