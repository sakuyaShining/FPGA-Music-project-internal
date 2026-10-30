// Execute only after reconnect and independent project/document identity confirmation.
const expected='ed8774d93e047c8f9ccedcca6ba91d2fa463cba9903d0b970ee0d079a932f37b';
async function identity(){const p=await eda.dmt_Project.getCurrentProjectInfo();const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(p?.uuid!==expected||p.friendlyName!=='Electrode84-450-CANDIDATE'||d?.parentProjectUuid!==expected||d.uuid!=='e450000000000002')throw Error('Wrong full84 project/document');return d;}
const before=await identity();
const saved=await eda.pcb_Document.save();if(saved!==true)throw Error('Save failed');
await identity();const closed=await eda.dmt_EditorControl.closeDocument(before.tabId);if(closed!==true)throw Error('Close failed');
const tab=await eda.dmt_EditorControl.openDocument('e450000000000002');const reopened=await identity();
const violations=await eda.pcb_Drc.check(true,false,true);await identity();
return {before,saved,closed,tab,reopened,violations,components:(await eda.pcb_PrimitiveComponent.getAll()).length,pads:(await eda.pcb_PrimitivePad.getAll()).length,vias:(await eda.pcb_PrimitiveVia.getAll()).length,fills:(await eda.pcb_PrimitiveFill.getAll()).length,manufacturing_release:false};
