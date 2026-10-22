"""Refresh native review PDF/CPL for the immutable 0-clearance/149-open snapshot."""
import hashlib
import json
import shutil
from pathlib import Path
from native_review import ROOT,PROJECT,invoke

checkpoint=json.loads((ROOT/'route-checkpoint-0clear-149open.json').read_text(encoding='utf-8'))
before=hashlib.sha256((PROJECT/'pcb/PCB1.epcb2').read_bytes()).hexdigest();assert before==checkpoint['pcb_sha256']
source=json.loads((ROOT/'grid-source-core-fresh.json').read_text(encoding='utf-8'))
assert len(source['lines'])==checkpoint['lines'] and len(source['vias'])==checkpoint['vias']
(ROOT/'pcb-current-copper.json').write_text(json.dumps(source,indent=2),encoding='utf-8')
out=PROJECT/'review-exports/v2';dest=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')
result=invoke('checkpoint149-native-export',"""const result=[];for(const type of ['pdf','cpl']){const name=type==='pdf'?'pcb-native-0clear-149open-CANDIDATE.pdf':'cpl-native-230-DRAFT-NOT-FOR-ORDER.csv';const f=type==='pdf'?await eda.pcb_ManufactureData.getPdfFile('pcb-native-0clear-149open-CANDIDATE','paged',{displayAttributesAsMenu:true,showOutlineOnly:false}):await eda.pcb_ManufactureData.getPickAndPlaceFile('cpl-native-230-DRAFT-NOT-FOR-ORDER','csv','mm');if(!f)throw new Error('Export '+type);const saved=await eda.sys_FileSystem.saveFileToFileSystem(__CLI__.args.path+'/'+name,f,undefined,true);if(!saved)throw new Error('Save '+type);result.push({name,size:f.size,saved});}return result;""",{'path':out.as_posix()},240)
after=hashlib.sha256((PROJECT/'pcb/PCB1.epcb2').read_bytes()).hexdigest();assert after==before
files={}
for item in result:
    p=out/item['name'];shutil.copy2(p,dest/p.name);files[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
audit={'source_pcb_sha256':before,'source_unchanged_during_export':True,'files':files,'native_exports':result,'manufacturing_release':False}
(ROOT/'checkpoint149-export-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print(json.dumps(audit,indent=2),flush=True)
