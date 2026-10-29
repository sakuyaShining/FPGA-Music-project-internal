const expected='79821b06a0e7bc13c8bceed705b60a9be12d79e3b222544cbfdedfb9f0f50241';
const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(d?.parentProjectUuid!==expected||d.uuid!=='f52674d6627fca6f')throw Error('Wrong S2 PCB');
const regions=await eda.pcb_PrimitiveRegion.getAll();if(regions.length!==22)throw Error('Unexpected region count');
const applied=[];
for(const r of regions){
 const id=r.getState_PrimitiveId();
 const value=await eda.pcb_PrimitiveRegion.modify(id,{ruleType:[7],regionName:'S2-BOTTOM-NO-POURS-'+id});
 if(!value)throw Error('Region modify failed');
 const check=await eda.pcb_PrimitiveRegion.get(id);
 if(!check.getState_RuleType().includes(7))throw Error('No NO_POURS rule readback');
 applied.push({id,rules:check.getState_RuleType(),name:check.getState_RegionName()});
}
const saved=await eda.pcb_Document.save();if(saved!==true)throw Error('Native save failed');
return {doc:d,applied,saved};
