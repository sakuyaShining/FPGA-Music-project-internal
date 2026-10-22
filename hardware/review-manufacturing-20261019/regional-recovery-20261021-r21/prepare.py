"""Resume the saved R19 stage 2 in an isolated, current-account native session."""
from pathlib import Path
import hashlib, json, shutil, sys, zipfile
BASE=Path(__file__).resolve().parent
ROOT=BASE.parent
sys.path.insert(0,str(ROOT))
from native_review import call
read=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old=Path(read(ROOT/'regional-layout-20261021-r19/native-candidate-source.json')['candidate_project'])
expected=read(ROOT/'regional-layout-20261021-r19/native-stage2-drc-meta.json')['pcb_sha256']
assert sha(old/'pcb/PCB1.epcb2')==expected,'R19 changed; do not resume stale geometry'
new=old.parent/'FPGA-Music-Dualscreen-RegionalRecovery-20261021-r21'
assert not new.exists(),'Do not overwrite a recovery project'
files={p.relative_to(old).as_posix():sha(p) for p in old.rglob('*') if p.is_file()}
with zipfile.ZipFile(BASE/'source-stage2.zip','x',zipfile.ZIP_DEFLATED) as z:
    for rel in files:z.write(old/rel,rel)
new.mkdir()
for rel in files:
    target=new/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(old/rel,target)
descriptor=new/(old.name+'.eprj3')
data=read(descriptor);data['name']=new.name;data['content']='R19 stage2 recovery and coordinated reconnection. WORK IN PROGRESS, not for fabrication.'
renamed=new/(new.name+'.eprj3')
renamed.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');descriptor.unlink()
session=call('r21-open',['open','--path',str(renamed),'--headless','true'],120)
(BASE/'native-session.json').write_text(json.dumps(session,indent=2),encoding='utf8')
info=dict(source_project=str(old),source_files=files,source_pcb_sha256=expected,candidate_project=str(new),candidate_descriptor=str(renamed),manufacturing_release=False)
(BASE/'native-candidate-source.json').write_text(json.dumps(info,indent=2),encoding='utf8')
print(json.dumps(session),flush=True)
