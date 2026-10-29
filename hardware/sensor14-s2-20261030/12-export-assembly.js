const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(d?.parentProjectUuid!=='79821b06a0e7bc13c8bceed705b60a9be12d79e3b222544cbfdedfb9f0f50241'||d.uuid!=='f52674d6627fca6f')throw Error('Wrong S2 PCB');
const files=[];
for(const [kind,name] of [['BOM','Sensor14Bank-S2-BOM-NATIVE.csv'],['CPL','Sensor14Bank-S2-CPL-NATIVE.csv'],['IPC','Sensor14Bank-S2-NATIVE.ipc']]){
 const f=kind==='BOM'?await eda.pcb_ManufactureData.getBomFile(name,'csv'):kind==='CPL'?await eda.pcb_ManufactureData.getPickAndPlaceFile(name,'csv','mm'):await eda.pcb_ManufactureData.getIpcD356AFile(name);
 if(!f||!f.size)throw Error('No native '+kind);
 files.push({kind,output_basename:name,bytes:f.size,data_bytes:Array.from(new Uint8Array(await f.arrayBuffer()))});
}
return {doc:d,files};
