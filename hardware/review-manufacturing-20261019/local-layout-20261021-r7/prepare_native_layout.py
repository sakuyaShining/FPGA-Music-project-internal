"""Clone verified r5 into an isolated audio comparison, never overwrite source."""
import json,hashlib,shutil,sys
from pathlib import Path
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;sys.path.insert(0,str(ROOT))
from native_review import call
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cp=json.loads((ROOT/'ACTIVE-ROUTING-CANDIDATE.json').read_text(encoding='utf-8'));qa=json.loads((BASE/'decoupling-plan.json').read_text(encoding='utf-8'))
assert qa['source_pcb_sha256']==cp['pcb_sha256'] and qa['min_gap_mm']>=.165 and qa['vcc_centerline_mm']<=2.5
OLD=Path(cp['project']);NEW=OLD.parent/'FPGA-Music-Dualscreen-LocalLayout-20261021-r7';assert not NEW.exists(),'Do not overwrite a native candidate'
assert all(sha(OLD/p)==h for p,h in cp['files'].items())
NEW.mkdir()
for rel,h in cp['files'].items():
 q=NEW/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(OLD/rel,q)
old=NEW/(OLD.name+'.eprj3');desc=NEW/(NEW.name+'.eprj3');data=json.loads(old.read_text(encoding='utf-8'));data['name']=NEW.name;data['content']='Isolated local decoupling and control closure from verified r5. NOT FOR FABRICATION.';desc.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');old.unlink()
info=dict(created_utc=datetime.now(timezone.utc).isoformat(),source_project=str(OLD),source_files=cp['files'],source_capture=str(ROOT/cp['source_capture']),source_capture_sha256=cp['source_capture_sha256'],candidate_project=str(NEW),candidate_descriptor=str(desc),source_pcb_sha256=cp['pcb_sha256'],manufacturing_release=False)
(BASE/'native-candidate-source.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
v=call('r7-layout-open',['open','--path',desc.as_posix(),'--headless','true'],120);(BASE/'native-session.json').write_text(json.dumps(v,indent=2),encoding='utf-8');print(json.dumps(v),flush=True)
wrapper=(ROOT/'stackup-validation-20261021-r5/native_project.py').read_text(encoding='utf-8').replace('source-and-stack-edit.json','native-candidate-source.json').replace('r5-stack-','r7-layout-').replace('r5 physical-stack candidate','r7 local layout candidate')
(BASE/'native_project.py').write_text(wrapper,encoding='utf-8')
sys.path.insert(0,str(BASE));from native_project import invoke
invoke('open-pcb',"return await eda.dmt_EditorControl.openDocument('c3fd8656cf425e9f');")
identity=invoke('project-identity',"return await eda.dmt_SelectControl.getCurrentDocumentInfo();");assert identity['parentProjectUuid']!='1860e3c87e09e290a7d637b5db3403ee40f4270da5d5610376c2de58da356707'
info['parent_project_uuid']=identity['parentProjectUuid'];(BASE/'native-candidate-source.json').write_text(json.dumps(info,indent=2),encoding='utf-8');(BASE/'native-project-identity.json').write_text(json.dumps(identity,indent=2),encoding='utf-8')
assert sha(NEW/'pcb/PCB1.epcb2')==cp['pcb_sha256'];assert all(sha(OLD/p)==h for p,h in cp['files'].items())
print('Independent r7 project/session created; r5 unchanged',flush=True)
