const p=await eda.dmt_Project.getCurrentProjectInfo();
const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(p?.uuid!=='ed8774d93e047c8f9ccedcca6ba91d2fa463cba9903d0b970ee0d079a932f37b'||d?.uuid!=='e450000000000002')throw Error('Wrong export source');
const files=[];
for(const [kind,fn] of [['BOM',()=>eda.pcb_ManufactureData.getBomFile('Electrode84-BOM','csv')],['CPL',()=>eda.pcb_ManufactureData.getPickAndPlaceFile('Electrode84-CPL','csv','mm')],['IPC356',()=>eda.pcb_ManufactureData.getIpcD356AFile('Electrode84-IPC356')]]){
 const f=await fn();if(!f||!f.size)throw Error('Missing '+kind);
 files.push({kind,bytes:f.size,output_basename:'Electrode84-NATIVE-'+kind+(kind==='IPC356'?'.ipc':'.csv'),data_bytes:Array.from(new Uint8Array(await f.arrayBuffer()))});
}
const after=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(after?.parentProjectUuid!==p.uuid||after.uuid!==d.uuid)throw Error('Source changed');
return {doc:d,files,manufacturing_release:false};
