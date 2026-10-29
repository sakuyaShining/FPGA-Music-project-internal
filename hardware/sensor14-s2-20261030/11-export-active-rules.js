const expected='79821b06a0e7bc13c8bceed705b60a9be12d79e3b222544cbfdedfb9f0f50241';
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(doc?.parentProjectUuid!==expected||doc?.uuid!=='f52674d6627fca6f')throw Error('Wrong export PCB');
const file=await eda.pcb_ManufactureData.getGerberFile('Sensor14Bank-S2-Gerber');
if(!file||file.size<1000)throw Error('No Gerber file');
return {doc,file_name:file.name,bytes:file.size,output_basename:'Sensor14Bank-S2-Gerber-ACTIVE-RULES-CANDIDATE.zip',data_bytes:Array.from(new Uint8Array(await file.arrayBuffer()))};
