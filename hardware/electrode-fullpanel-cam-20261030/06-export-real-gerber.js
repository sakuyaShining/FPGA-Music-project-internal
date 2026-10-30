const expected='ed8774d93e047c8f9ccedcca6ba91d2fa463cba9903d0b970ee0d079a932f37b';
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(doc?.parentProjectUuid!==expected||doc.uuid!=='e450000000000002')throw Error('Wrong full84 export source');
const file=await eda.pcb_ManufactureData.getGerberFile('Electrode84-450-Gerber-CANDIDATE');
const after=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(after?.parentProjectUuid!==expected||after.uuid!==doc.uuid)throw Error('Source switched during export');
if(!file||file.size<1000)throw Error('No real Gerber export');
return {doc,after,file_name:file.name,bytes:file.size,output_basename:'Electrode84-450-Gerber-NATIVE-CANDIDATE.zip',data_bytes:Array.from(new Uint8Array(await file.arrayBuffer())),manufacturing_release:false};
