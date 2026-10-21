"""Create a separate, recoverable native comparison project from verified r3."""
import json,hashlib,shutil,sys
from pathlib import Path
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;sys.path.insert(0,str(ROOT))
from current_state import current_checkpoint
from native_review import PROJECT as OLD,call
_,cp,SRC=current_checkpoint(ROOT);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
qa=json.loads((BASE/'four-layer-mixed/independent-geometry.json').read_text());assert qa['combined_geometry_pass'] and qa['native_pcb_sha256']==cp['pcb_sha256']
NEW=OLD.parent/'FPGA-Music-Dualscreen-4L-Candidate-20261021-r4';assert not NEW.exists(),'Do not overwrite native candidate'
assert all(sha(OLD/p)==h for p,h in cp['files'].items())
NEW.mkdir()
for rel,h in cp['files'].items():
 q=NEW/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(OLD/rel,q)
old_desc=NEW/(OLD.name+'.eprj3');new_desc=NEW/(NEW.name+'.eprj3');d=json.loads(old_desc.read_text(encoding='utf-8'));d['name']=NEW.name;d['content']='Four-layer routing comparison from r3. NOT RELEASED FOR MANUFACTURING. Original 2-layer project is preserved.';new_desc.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');old_desc.unlink()
record=dict(created_utc=datetime.now(timezone.utc).isoformat(),source_project=str(OLD),source_files=cp['files'],source_capture=str(SRC),source_capture_sha256=sha(SRC),candidate_project=str(NEW),candidate_descriptor=str(new_desc),manufacturing_release=False)
(BASE/'native-candidate-source.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
v=call('r4-four-layer-open',['open','--path',new_desc.as_posix(),'--headless','true'],120)
(BASE/'native-session.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(v,ensure_ascii=False))
assert all(sha(OLD/p)==h for p,h in cp['files'].items()),'Original source changed'
