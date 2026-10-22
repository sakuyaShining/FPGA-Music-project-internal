"""Versioned native schematic/PCB review exports; no Gerber release."""
import json
import shutil
import time
from pathlib import Path
from native_review import ROOT,PROJECT,invoke

DEST=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')
OUT=PROJECT/'review-exports/v2'
OUT.mkdir(parents=True,exist_ok=True)

def save_call(name,code,args,timeout=180):
    result=invoke(name,code,args,timeout)
    print(name,result,flush=True)
    return result

save_call('v2-export-schematic',"""
const f=await eda.sch_ManufactureData.getExportDocumentFile('dual-screen-review-v2','PDF',{theme:'Default',size:'Original Size'},'Current Schematic',{range:'All',outputMethod:'Merged sheet'});if(!f)throw new Error('No PDF');const saved=await eda.sys_FileSystem.saveFileToFileSystem(__CLI__.args.pdf,f,undefined,true);return {name:f.name,size:f.size,saved};""",{'pdf':(OUT/'dual-screen-review-v2.pdf').as_posix()},240)
if not (OUT/'schematic-png-v2.zip').exists():
    save_call('v2-export-schematic-png',"""const f=await eda.sch_ManufactureData.getPngFile('dual-screen-review-v2',{width:4096});if(!f)throw new Error('No PNG');return {size:f.size,saved:await eda.sys_FileSystem.saveFileToFileSystem(__CLI__.args.path,f,undefined,true)};""",{'path':(OUT/'schematic-png-v2.zip').as_posix()},240)
save_call('v2-focus-pcb-export',"""const id=await eda.dmt_EditorControl.openDocument('c3fd8656cf425e9f');if(!id)throw new Error('PCB not active');return id;""",{})
time.sleep(3)
save_call('v2-export-pcb-review',"""const result=[];
for(const [name,kind] of [['pcb-placement-review.pdf','pdf'],['cpl-DRAFT-NOT-FOR-ORDER.csv','cpl'],['carrier-routing-candidate.dsn','dsn']]){
let f=kind==='pdf'?await eda.pcb_ManufactureData.getPdfFile('pcb-placement-review','paged',{displayAttributesAsMenu:false,showOutlineOnly:false}):kind==='cpl'?await eda.pcb_ManufactureData.getPickAndPlaceFile('cpl-DRAFT-NOT-FOR-ORDER','csv','mm'):await eda.pcb_ManufactureData.getDsnFile('carrier-routing-candidate');if(!f)throw new Error('No '+kind);const saved=await eda.sys_FileSystem.saveFileToFileSystem(__CLI__.args.out+'/'+name,f,undefined,true);result.push({name,size:f.size,saved});}return result;""",{'out':OUT.as_posix()},240)
DEST.mkdir(parents=True,exist_ok=True)
for p in OUT.iterdir():
    if p.is_file():shutil.copy2(p,DEST/p.name)
print('versioned native review exports',DEST,flush=True)
