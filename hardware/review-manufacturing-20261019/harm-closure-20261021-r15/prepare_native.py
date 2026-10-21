"""Create a source-verified isolated R15 native project, never overwrite R7."""
from pathlib import Path
from datetime import datetime,timezone
import sys,json,hashlib,shutil,zipfile
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,str(ROOT));from native_review import call
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=json.loads((BASE/'plan.json').read_text(encoding='utf-8'))
cp=json.loads((ROOT/'ACTIVE-ROUTING-CANDIDATE.json').read_text(encoding='utf-8'))
assert plan['source_pcb_sha256']==cp['pcb_sha256']
assert plan['total_harm_length_mm']<=100 and plan['new_signal_vias']<=6
assert all(p['complete'] for p in plan['connectivity'].values())
old=Path(cp['project']);assert all(sha(old/r)==v for r,v in cp['files'].items())
new=old.parent/'FPGA-Music-Dualscreen-HarmClosure-20261021-r15'
assert not new.exists(),'Never overwrite an existing native project'
# Reclaim only the old, CLI-owned, saved R5 render; its source remains preserved.
sessions=call('r15-preparation-sessions',['session','list'],90)
previous=ROOT/'stackup-validation-20261021-r5/native-candidate-checkpoint.json'
r5=json.loads(previous.read_text(encoding='utf-8'))
closed=[]
for session in sessions:
    if session['sessionId']=='09c0fd69-4ee1-4b67-83cc-779e92716d04' and session['status']=='alive':
        assert session['origin']=='cli' and session['headless'] and 'Stackup-20261021-r5' in session['path']
        root=Path(session['path']).parent
        assert all(sha(root/r)==v for r,v in r5['files'].items())
        closed.append(call('r15-close-saved-r5',['session','close','--session',session['sessionId']],90))
        assert all(sha(root/r)==v for r,v in r5['files'].items())
new.mkdir()
for rel in cp['files']:
    target=new/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(old/rel,target)
descriptor=new/(old.name+'.eprj3');data=json.loads(descriptor.read_text(encoding='utf-8'))
data['name']=new.name;data['content']='Isolated HARM routing/R30 placement comparison from verified R7. NOT FOR FABRICATION.'
renamed=new/(new.name+'.eprj3');renamed.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');descriptor.unlink()
snapshot=Path('D:/FPGA-Project/snapshots')/('before-harm-r15-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
snapshot.mkdir();archive=snapshot/'native-source-before-r15.zip'
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for p in old.rglob('*'):
        if p.is_file() and p.relative_to(old).as_posix() in cp['files']:z.write(p,p.relative_to(old))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
info=dict(created_utc=datetime.now(timezone.utc).isoformat(),source_project=str(old),source_files=cp['files'],source_pcb_sha256=cp['pcb_sha256'],
          candidate_project=str(new),candidate_descriptor=str(renamed),source_snapshot=str(archive),source_snapshot_sha256=sha(archive),closed_saved_r5_render=closed,manufacturing_release=False)
(BASE/'native-candidate-source.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
session=call('r15-open-isolated',['open','--path',renamed.as_posix(),'--headless','true'],120)
(BASE/'native-session.json').write_text(json.dumps(session,indent=2),encoding='utf-8')
wrapper=(ROOT/'local-layout-20261021-r7/native_project.py').read_text(encoding='utf-8').replace('r7-layout-','r15-harm-').replace('r7 local layout candidate','r15 HARM candidate')
(BASE/'native_project.py').write_text(wrapper,encoding='utf-8')
assert all(sha(old/r)==v for r,v in cp['files'].items())
print(json.dumps(dict(project=str(new),session=session,snapshot=str(archive)),indent=2),flush=True)
