from pathlib import Path
import subprocess,os,json,hashlib,datetime
B=Path(r'D:\FPGA-Project\codex-deliverables\dual-screen-review-20261020-v2');E=B/'module-plan-current-evidence'
repo=Path(r'C:\Users\Sakuya\.codex\worktrees\4a4b\FPGA-Music-project');ref='refs/heads/codex/pcb-paused-status-20261025'
def G(*a,**kw):return subprocess.check_output(['git',*a],cwd=repo,**kw)
def sha(b):return hashlib.sha256(b).hexdigest()
def js(x):return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
old=G('rev-parse',ref).decode().strip();assert old=='ef3fdb29f03d198fae5956991643b1788c5295eb',old
assert G('remote','get-url','--push','internal').decode().strip()=='https://github.com/sakuyaShining/FPGA-Music-project-internal.git'
assert G('ls-remote','internal',ref).decode().split()[0]==old,'Inspect remote before retry'
status=G('status','--porcelain=v1');head=G('rev-parse','HEAD');fpga=G('rev-parse',old+':fpga');host=G('rev-parse',old+':host')
index=Path(G('rev-parse','--git-path','index').decode().strip());index=index if index.is_absolute() else repo/index;idxsha=sha(index.read_bytes()) if index.exists() else None
stage=json.loads((E/'sensor-fourlayer-progress-current.json').read_text(encoding='utf-8'))
native=Path(r'C:\Users\Sakuya\Documents\LCEDA-Pro\projects\FPGA-Music-U9ControlWork-20261023\pcb\PCB2.epcb2')
assert sha(native.read_bytes())==stage['current_PCB2_SHA']=='617f550eadc818ffab26a3992f2a86bb9f72ed027043c6e64a0c0428077ba643'
assert sha((E/'sensor-fourlayer-native-current.epcb2').read_bytes())==stage['current_PCB2_SHA']
assert stage['accepted'] is False and stage['native_strict_DRC_errors']==0 and stage['independent_reference_failed_segments']==35
checks=json.loads((E/'control-power-current-plan.json').read_text(encoding='utf-8-sig'))['native_file_checks'];changes=[]
for r in checks:
 p=Path(r['file']);h=sha(p.read_bytes())
 if h!=r['actual']:
  assert p.name in ['FPGA-Music-U9ControlWork-20261023.eprj3','Sensor14_frontend.esch2','PCB2.epcb2'],str(p)
  changes.append(dict(file=str(p),before=r['actual'],actual=h))
assert len(changes)==3
m=json.loads(G('show',old+':project/versions/engineering-sources-20261023.json'));updates={}
files=[p for p in E.iterdir() if p.is_file() and p.suffix in {'.py','.js','.json','.md','.png','.wkb','.epcb2','.esch2'} and p.name.startswith(('sensor-fourlayer-','sensor35-','sensor84-','audio-AUX-scope-','control-power-current-plan','purchase-assembly-user-review-','传感小板参考验收口径-'))]
for p in files:
 dest='hardware/current/module-plan/evidence/'+p.name;b=p.read_bytes();prior=m['areas']['hardware']['files'].get(dest[len('hardware/current/'):],{})
 if prior.get('stored_sha256')!=sha(b):updates[dest]=b
for n in ['PCB-CURRENT-CAPACITY-RECOVERY-20261024.json','PCB-ACTIVE-WORK.json','实体交付当前入口.json','模块方案-当前证据.json','模块方案-当前工作单.md']:
 updates['hardware/current/module-plan/'+n]=(B/n).read_bytes()
now=datetime.datetime.now().astimezone().isoformat();c=json.loads(G('show',old+':hardware/current/CURRENT-HARDWARE.json'))
c['last_metadata_update']=now;c['module_delivery_main']['sensor_fourlayer_trial_current']=stage
c['module_delivery_main']['sensor35_numeric_review']='module-plan/evidence/sensor35-numeric-review-current.md'
c['module_delivery_main']['current_purchase_assembly_review']='module-plan/evidence/purchase-assembly-user-review-current.md'
c['module_delivery_main']['complete_purchase_plan']=False;updates['hardware/current/CURRENT-HARDWARE.json']=js(c)
s=G('show',old+':hardware/current/README.md').decode('utf-8');marker='\n## Current35 numeric review and assembly status'
s=s.split(marker)[0]+marker+'\n\nRead module-plan/evidence/sensor35-numeric-review-current.md and purchase-assembly-user-review-current.md first. Current native source617f550e:302lines51vias,0DRC/0unconnected after reopen. Actual Ground DC and0.1651mm erosion checks pass;35 legacy reference failures remain within own native antipads only. User requested numbers before deciding: no scope approval, no fabrication release. Six preweld sensor boards, complete control/storage/protection, full screen configuration, all accessories and <=700 delivered/preweld budget are not closed. AUX3.5 retained; no internal speaker requirement. Physical84 electrodes include4mounted spares. Original mainPCB951 remains unfinished. No RTL/host edits.\n'
updates['hardware/current/README.md']=s.encode('utf-8')
for p,b in updates.items():
 k=p[len('hardware/current/'):];r=m['areas']['hardware']['files'].get(k,{})
 r.update(stored=p,bytes=len(b),sha256=sha(b),stored_sha256=sha(b),codec='raw',source='Current617f550e native audit and35numeric review; human decision pending, not fabrication accepted; full procurement remains incomplete')
 m['areas']['hardware']['files'][k]=r
m['areas']['hardware'].update(updated_at=now,product_acceptance=False,validation_inherited=False,current_candidate_native_changes=changes)
updates['project/versions/engineering-sources-20261023.json']=js(m)
alt=E/'sensor35-review-publish-current.index';assert not alt.exists(),'Inspect alternate index before resume'
env=dict(os.environ,GIT_INDEX_FILE=str(alt));G('read-tree',old,env=env)
for p,b in updates.items():
 oid=G('hash-object','-w','--stdin',input=b).decode().strip();G('update-index','--add','--cacheinfo','100644',oid,p,env=env)
tree=G('write-tree',env=env).decode().strip();commit=G('commit-tree',tree,'-p',old,input=b'Record actual35 transition clearances and honest purchase assembly status\n').decode().strip()
assert G('rev-parse',commit+':fpga')==fpga and G('rev-parse',commit+':host')==host
for p,b in updates.items():assert sha(G('show',commit+':'+p))==sha(b),p
for k,r in m['areas']['hardware']['files'].items():assert sha(G('show',commit+':'+r['stored']))==r['stored_sha256'],k
assert G('status','--porcelain=v1')==status and G('rev-parse','HEAD')==head and (sha(index.read_bytes()) if index.exists() else None)==idxsha
G('update-ref',ref,commit,old);alt.unlink()
r=dict(at=now,parent_commit=old,commit=commit,branch=ref[len('refs/heads/'):],updated_files=len(updates),hardware_files_SHA_verified=len(m['areas']['hardware']['files']),FPGA_axis_unchanged=True,host_axis_unchanged=True,working_HEAD_index_and_untracked_status_unchanged=True,native_changes_only=changes,not_for_fabrication=True,complete_purchase_plan=False,remote_push_completed=False)
(B/'module-plan-current-publication.json').write_bytes(js(r));print(json.dumps(r,ensure_ascii=True),flush=True)
