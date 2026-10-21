"""Fresh native placement export from unchanged quality-r1 PCB; NOT FOR ORDER."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from native_review import PROJECT,invoke
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((ROOT.parent/'route-checkpoint-0clear-78open-quality-r1-20261021.json').read_text(encoding='utf-8'))
before={name:h(PROJECT/name) for name in manifest['files']}
assert before==manifest['files']
target=ROOT/'native-cpl-current-quality-r1-NOT-FOR-ORDER.csv'
try:
    r=invoke('autonomous-r1-current-cpl',"""
const file=await eda.pcb_ManufactureData.getPickAndPlaceFile('current-quality-r1-NOT-FOR-ORDER','csv','mm');
if(!file)throw new Error('No native CPL export');
const saved=await eda.sys_FileSystem.saveFileToFileSystem(__CLI__.args.path,file,undefined,true);
if(!saved)throw new Error('CPL save failed');
return {name:file.name,bytes:file.size,saved};
""",{'pcb':'c3fd8656cf425e9f','path':target.as_posix()},150)
except RuntimeError as error:
    after={name:h(PROJECT/name) for name in manifest['files']}
    report={'export_success':False,'error':str(error),'all_19_native_files_unchanged':before==after,
            'pcb_sha256':manifest['pcb_sha256'],'manufacturing_release':False}
    (ROOT/'native-cpl-export-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    raise
after={name:h(PROJECT/name) for name in manifest['files']}
assert before==after,'Native source changed during export'
assert target.is_file() and target.stat().st_size>100
report={'native_export':r,'pcb_sha256':manifest['pcb_sha256'],'all_19_native_files_unchanged':True,
        'file':str(target),'sha256':h(target),'manufacturing_release':False}
(ROOT/'native-cpl-export-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2),flush=True)
