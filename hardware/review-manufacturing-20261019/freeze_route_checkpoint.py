"""Freeze a saved, source-bound native DRC checkpoint; never release fabrication."""
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path
from native_review import ROOT,PROJECT,invoke

stage=sys.argv[1];drc_path=ROOT/f'drc-stage-{stage}.json'
tag=sys.argv[2] if len(sys.argv)>2 else ''
assert not tag or re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',tag),'Use a short safe checkpoint label'
suffix=('-'+tag) if tag else ''
drc=json.loads(drc_path.read_text(encoding='utf-8'));meta=json.loads((ROOT/f'drc-stage-{stage}.meta.json').read_text())
assert meta['source_stable_during_drc']
assert hashlib.sha256((PROJECT/'pcb/PCB1.epcb2').read_bytes()).hexdigest()==meta['pcb_sha256_after'],'Source changed after DRC'
assert all(c['name']=='Connection Error' for c in drc),'Checkpoint has non-connectivity DRC errors'
unconnected=sum(c.get('count',0) for c in drc)
pending=[n['name'] for c in drc for n in c.get('list',[])]
counts=invoke('freeze-counts-'+stage,"""return {components:(await eda.pcb_PrimitiveComponent.getAll()).length,lines:(await eda.pcb_PrimitiveLine.getAll()).length,vias:(await eda.pcb_PrimitiveVia.getAll()).length,poured:(await eda.pcb_PrimitivePoured.getAll()).length};""")
assert counts['components']==230 and counts['poured']==2
out=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')
archive=out/f'native-230-0clear-{unconnected}open{suffix}-CANDIDATE.zip';assert not archive.exists(),'Keep existing checkpoint'
files={}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(PROJECT.rglob('*')):
        if not p.is_file() or 'review-exports' in p.relative_to(PROJECT).parts:continue
        rel=p.relative_to(PROJECT).as_posix();data=p.read_bytes();files[rel]=hashlib.sha256(data).hexdigest();z.writestr(rel,data)
assert files['pcb/PCB1.epcb2']==meta['pcb_sha256_after']
checkpoint={**counts,'clearance_errors':0,'physical_errors':0,'unconnected_errors':unconnected,'pending_nets':pending,
            'all_mux_and_rc_signal_nets_closed':not any(re.fullmatch(r'L[0-5]_[ME]\d\d|RC[0-5]',n) for n in pending),
            'manufacturing_release':False,'native_zip':str(archive),'native_zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
            'drc_stage':stage,'drc_sha256':hashlib.sha256(drc_path.read_bytes()).hexdigest(),'pcb_sha256':meta['pcb_sha256_after'],'files':files}
name=f'route-checkpoint-0clear-{unconnected}open{suffix}.json'
(ROOT/name).write_text(json.dumps(checkpoint,indent=2),encoding='utf-8');shutil.copy2(ROOT/name,out/name)
shutil.copy2(drc_path,out/f'drc-0clear-{unconnected}open{suffix}.json')
(out/'CURRENT-CHECKPOINT.json').write_text(json.dumps(checkpoint,indent=2),encoding='utf-8')
print({k:v for k,v in checkpoint.items() if k not in ['files','pending_nets']},flush=True)
