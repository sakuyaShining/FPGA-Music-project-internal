"""Create candidate inner GND pours, rebuild all copper and run full native DRC."""
import json,sys,hashlib
from pathlib import Path
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(BASE));sys.path.insert(0,str(ROOT))
from candidate_native import invoke,info,PROJECT
import grid_route as g;g.invoke=invoke
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();PCB=PROJECT/'pcb/PCB1.epcb2'
assert (BASE/'native-apply-audit.json').exists()
pours=invoke('create-inner-ground',"""if((await eda.pcb_Layer.getTheNumberOfCopperLayers())!==4)throw new Error('Wrong stack');const all=await eda.pcb_PrimitivePour.getAll();const top=all.filter(p=>p.getState_Layer()===1&&p.getState_Net()==='GND');if(top.length!==1)throw new Error('Missing original outline');const result=[];for(const layer of [15,16]){if(all.some(p=>p.getState_Layer()===layer))throw new Error('Inner ground already created');const p=await eda.pcb_PrimitivePour.create('GND',layer,top[0].getState_ComplexPolygon(),'solid',false,'R4_CANDIDATE_GND_'+layer,top[0].getState_PourPriority(),top[0].getState_LineWidth(),false);if(!p)throw new Error('Inner ground');result.push({id:p.getState_PrimitiveId(),layer:p.getState_Layer(),name:p.getState_PourName()});}if(!await eda.pcb_Document.save())throw new Error('Save');return result;""",timeout=120)
(BASE/'native-inner-ground.json').write_text(json.dumps(pours,indent=2));print('CREATED INNER GND',pours,flush=True)
for layer in [1,15,16,2]:
 v=invoke('rebuild-ground-'+str(layer),"""const ps=(await eda.pcb_PrimitivePour.getAll()).filter(p=>p.getState_Layer()===__CLI__.args.layer&&p.getState_Net()==='GND');if(ps.length!==1)throw new Error('Ground count');if(!await ps[0].rebuildCopperRegion())throw new Error('Rebuild');if(!await eda.pcb_Document.save())throw new Error('Save');return {layer:__CLI__.args.layer,saved:true};""",dict(layer=layer),180);print(v,flush=True)
v=invoke('reopen-saved-candidate',"""if(!await eda.pcb_Document.save())throw new Error('Save');let d=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(d?.parentProjectUuid!=='dbcb11b6e1bcc817f595b7053414e8dc88b8aec2cb33fa4f75e16a6f290dab6b')throw new Error('Wrong project');if(!await eda.dmt_EditorControl.closeDocument(d.tabId))throw new Error('Close');const tab=await eda.dmt_EditorControl.openDocument('c3fd8656cf425e9f');if(!tab)throw new Error('Reopen');await eda.pcb_Drc.stopRealTimeDrc();return {tab,layers:await eda.pcb_Layer.getTheNumberOfCopperLayers()};""",timeout=120);print('REOPENED',v,flush=True)
before=sha(PCB);drc=invoke('full-drc','return await eda.pcb_Drc.check(true,false,true);',timeout=300);after=sha(PCB)
(BASE/'native-drc.json').write_text(json.dumps(drc,ensure_ascii=False,indent=2),encoding='utf-8');meta=dict(utc=datetime.now(timezone.utc).isoformat(),pcb_sha256_before=before,pcb_sha256_after=after,source_stable=before==after,manufacturing_release=False,sensor_plane_capacitance_not_qualified=True,stackup_not_factory_qualified=True)
(BASE/'native-drc-meta.json').write_text(json.dumps(meta,indent=2));print('DRC',[(x['name'],x.get('count')) for x in drc],flush=True);assert before==after
capture=g.capture();(BASE/'native-verified-capture.json').write_text(json.dumps(capture,indent=2))
assert all(sha(Path(info['source_project'])/p)==h for p,h in info['source_files'].items()),'Original 2-layer baseline changed'
print('ORIGINAL TWO LAYER BASELINE UNCHANGED',flush=True)
