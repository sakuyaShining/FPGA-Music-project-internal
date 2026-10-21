"""Export an explicitly incomplete local Gerber solely for drill/footprint QA."""
import hashlib
import json
import shutil
import zipfile
from native_review import ROOT,PROJECT,invoke

name='DRAFT-DRILL-AUDIT-169open-NOT-FOR-ORDER.zip'
target=PROJECT/'review-exports/v2'/name
before=hashlib.sha256((PROJECT/'pcb/PCB1.epcb2').read_bytes()).hexdigest()
result=invoke('draft-drill-audit-export',"""
const f=await eda.pcb_ManufactureData.getGerberFile('DRAFT-DRILL-AUDIT-NOT-FOR-ORDER');
if(!f)throw new Error('No draft export');
return {size:f.size,saved:await eda.sys_FileSystem.saveFileToFileSystem(__CLI__.args.path,f,undefined,true)};
""",{'path':target.as_posix()},240)
assert result['saved'] and target.is_file()
destination=__import__('pathlib').Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')/name
shutil.copy2(target,destination)
with zipfile.ZipFile(destination) as archive:
    drills={p:archive.read(p).decode('utf-8',errors='replace') for p in archive.namelist() if p.lower().endswith(('.drl','.txt'))}
report={'file':str(destination),'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),
        'source_board_sha256_before':before,'source_board_sha256_after':hashlib.sha256((PROJECT/'pcb/PCB1.epcb2').read_bytes()).hexdigest(),
        'manufacturing_release':False,'copper_pours_require_rebuild':True,'native_export':result,'drill_files':drills}
(ROOT/'exported-drill-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print({k:v for k,v in report.items() if k!='drill_files'},flush=True)
for name,data in drills.items():print(name,data[:2400],flush=True)
