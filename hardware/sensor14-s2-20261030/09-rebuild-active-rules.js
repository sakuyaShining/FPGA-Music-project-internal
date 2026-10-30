const expected='79821b06a0e7bc13c8bceed705b60a9be12d79e3b222544cbfdedfb9f0f50241';
async function checkIdentity(){const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(d?.parentProjectUuid!==expected||d?.uuid!=='f52674d6627fca6f')throw Error('Wrong PCB; no mutation allowed');return d;}
await checkIdentity();
const regions=await eda.pcb_PrimitiveRegion.getAll();if(regions.length!==22)throw Error('Wrong region count');
const pours=await eda.pcb_PrimitivePour.getAll();if(pours.length!==3)throw Error('Wrong pour count');
const rebuilt=[];
for(const p of pours){await checkIdentity();const copper=await p.rebuildCopperRegion();if(!copper)throw Error('Native rebuild failed layer '+p.getState_Layer());rebuilt.push({id:p.getState_PrimitiveId(),layer:p.getState_Layer(),result:true});}
await checkIdentity();const saved=await eda.pcb_Document.save();if(!saved)throw Error('Native save failed');
return {doc:await checkIdentity(),rebuilt,saved,region_count:regions.length};
