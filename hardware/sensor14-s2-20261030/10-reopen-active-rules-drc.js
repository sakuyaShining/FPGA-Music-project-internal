const expected='79821b06a0e7bc13c8bceed705b60a9be12d79e3b222544cbfdedfb9f0f50241';
const current=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(current?.parentProjectUuid!==expected||current?.uuid!=='f52674d6627fca6f')throw Error('Wrong PCB');
const closed=await eda.dmt_EditorControl.closeDocument(current.tabId);if(!closed)throw Error('Close failed');
const tab=await eda.dmt_EditorControl.openDocument('f52674d6627fca6f');
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(doc?.parentProjectUuid!==expected||doc?.uuid!=='f52674d6627fca6f')throw Error('Wrong reopened PCB');
const violations=await eda.pcb_Drc.check(true,false,true);
return {closed,tab,doc,violations,region_count:(await eda.pcb_PrimitiveRegion.getAll()).length};
