"""Archive and promote only the source-bound, reopened, zero-clearance r7."""
import sys,json,hashlib,zipfile,copy,csv
from pathlib import Path
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;D=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2');sys.path.insert(0,str(BASE));from native_project import PROJECT,SESSION,info
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text(encoding='utf-8'));save=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
previous=read(ROOT/'ACTIVE-ROUTING-CANDIDATE.json');assert previous['pcb_sha256']==info['source_pcb_sha256'] and 'Stackup-20261021-r5' in previous['project']
review=read(BASE/'final-layout-review.json');assert review['native_drc']=={'Connection Error':62} and review['original_r5_19_files_unchanged'] and review['new_local_copper_matches_plan'] and review['audio_copper_unchanged']
PCB=PROJECT/'pcb/PCB1.epcb2';assert sha(PCB)==review['pcb_sha256'];files={p.relative_to(PROJECT).as_posix():sha(p) for p in PROJECT.rglob('*') if p.is_file()};assert len(files)==19
archive=D/'native-4L-230-0clear-62open-local-layout-r7-20261021-CANDIDATE.zip';assert not archive.exists()
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
 for rel in files:z.write(PROJECT/rel,rel)
with zipfile.ZipFile(archive) as z:assert z.testzip() is None and all(hashlib.sha256(z.read(rel)).hexdigest()==h for rel,h in files.items())
working=copy.deepcopy(previous);working.update(updated_utc=datetime.now(timezone.utc).isoformat(),role='Active r7 routing candidate: C35 bypass relocation verified; procurement/manufacturing baseline remains preserved r3',project=str(PROJECT),session=SESSION,checkpoint='local-layout-20261021-r7/native-candidate-checkpoint.json',source_capture='local-layout-20261021-r7/native-verified-capture.json',source_capture_sha256=sha(BASE/'native-verified-capture.json'),pcb_sha256=sha(PCB),api_lines=review['api_lines'],native_copper_line_records=review['native_lines'],native_microtracks=28,vias=520,components=230,pads=1079,files=files,native_zip=str(archive),native_zip_sha256=sha(archive),previous_checkpoint=previous['checkpoint'],previous_active_pcb_sha256=previous['pcb_sha256'],components_moved=['C35'],original_r5_source_files_unchanged=True,legacy_CPL_C35_position_stale=True,decoupling_layout_verified=True,decoupling_power_transient_qualified=False,decoupling_review='local-layout-20261021-r7/final-layout-review.json',r3_via_net_reduction=13,manufacturing_release=False)
save(BASE/'native-candidate-checkpoint.json',working);save(ROOT/'ACTIVE-ROUTING-CANDIDATE.json',working);save(D/'ACTIVE-ROUTING-CANDIDATE.json',working)
actual=read(BASE/'native-final-decoupling-audit.json')['result']['actual_component'];first=read(BASE/'native-decoupling-audit.json')['result']['priorC'];placement=dict(ref='C35',before_component_origin_mm=[first['x']*.0254,first['y']*.0254],before_rotation=first['rotation'],after_component_origin_mm=[actual['x']*.0254,actual['y']*.0254],after_rotation=actual['rotation'],source_pcb_before_sha256=previous['pcb_sha256'],source_pcb_after_sha256=working['pcb_sha256'],native_export=False,manufacturing_CPL_ready=False)
save(BASE/'C35-placement-change.json',placement)
print(json.dumps({k:v for k,v in working.items() if k not in ['files']},indent=2),flush=True)
