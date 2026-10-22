"""Archive the source-verified ordered physical stack, keeping r3/r4 immutable."""
import sys,json,hashlib,zipfile,collections
from pathlib import Path
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;sys.path.insert(0,str(BASE));sys.path.insert(0,str(ROOT))
from native_project import PROJECT,SESSION,info
from resume_offline import read_native
read=lambda p:json.loads(p.read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();save=lambda p,o:p.write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8')
previous=read(ROOT/'ACTIVE-ROUTING-CANDIDATE.json');verified=read(BASE/'native-stack-verification.json');assert previous['pcb_sha256']==info['source_pcb_sha256'];assert verified['physical_stack_structure_verified'];assert sha(PROJECT/'pcb/PCB1.epcb2')==verified['pcb_sha256']
oldcap=read(ROOT/previous['source_capture']);capture=read(BASE/'native-verified-capture.json');canon=lambda o:{k:sorted(o[k],key=lambda p:p['id']) for k in ['pads','lines','vias']};assert canon(oldcap)==canon(capture)
files={p.relative_to(PROJECT).as_posix():sha(p) for p in PROJECT.rglob('*') if p.is_file()};assert len(files)==19
D=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2');archive=D/'native-4L-230-0clear-62open-stackup-r5-20261021-CANDIDATE.zip';assert not archive.exists(),'Never overwrite a native checkpoint'
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
 for p in files:z.write(PROJECT/p,p)
with zipfile.ZipFile(archive) as z:assert z.testzip() is None and all(hashlib.sha256(z.read(p)).hexdigest()==h for p,h in files.items())
cp={**previous,'updated_utc':datetime.now(timezone.utc).isoformat(),'role':'Active routing candidate with ordered physical stack verified; procurement baseline remains r3 pending routing/return/sensor/factory qualification','project':str(PROJECT),'session':SESSION,'checkpoint':'stackup-validation-20261021-r5/native-candidate-checkpoint.json','source_capture':'stackup-validation-20261021-r5/native-verified-capture.json','source_capture_sha256':sha(BASE/'native-verified-capture.json'),'pcb_sha256':verified['pcb_sha256'],'native_zip':str(archive),'native_zip_sha256':sha(archive),'files':files,'physical_stack_metadata_complete':True,'physical_stack_structure_verified':True,'physical_stack_audit':'stackup-validation-20261021-r5/native-stack-verification.json','previous_checkpoint':previous['checkpoint'],'dielectric_loss_properties_qualified':False,'factory_stack_approval':False,'nominal_finished_thickness_mm':1.6,'serialized_finished_thickness_with_mask_mm':verified['finished_with_preserved_mask_mm']}
save(BASE/'native-candidate-checkpoint.json',cp);save(ROOT/'ACTIVE-ROUTING-CANDIDATE.json',cp);save(D/'ACTIVE-ROUTING-CANDIDATE.json',cp)
assert all(sha(Path(info['source_project'])/p)==h for p,h in info['source_files'].items())
report=dict(checkpoint=cp['checkpoint'],pcb_sha256=cp['pcb_sha256'],zip=str(archive),zip_sha256=sha(archive),all_planar_copper_and_native_api_capture_unchanged=True,archive_crc_and_19_hashes_verified=True,previous_r4_source_19_hashes_unchanged=True,physical_stack_complete=True,drc_0clear_0physical_62open=True,manufacturing_release=False);save(BASE/'final-verification.json',report);print(json.dumps(report,indent=2))
