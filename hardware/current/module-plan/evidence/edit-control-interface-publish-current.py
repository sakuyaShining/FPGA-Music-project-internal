from pathlib import Path
import subprocess,os,json,hashlib,datetime
B=Path(r'D:\FPGA-Project\codex-deliverables\dual-screen-review-20261020-v2');E=B/'module-plan-current-evidence';repo=Path(r'C:\Users\Sakuya\.codex\worktrees\4a4b\FPGA-Music-project');ref='refs/heads/codex/pcb-paused-status-20261025'
def G(*a,**kw):return subprocess.check_output(['git',*a],cwd=repo,**kw)
def sha(b):return hashlib.sha256(b).hexdigest()
def js(x):return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
old=G('rev-parse',ref).decode().strip();assert old=='566387ea43ce22618b7eacf9c20a80aaba9fd6a6',old
assert G('remote','get-url','--push','internal').decode().strip()=='https://github.com/sakuyaShining/FPGA-Music-project-internal.git'
assert G('ls-remote','internal',ref).decode().split()[0]==old,'Inspect network result/state before retry'
status=G('status','--porcelain=v1');head=G('rev-parse','HEAD');fpga=G('rev-parse',old+':fpga');host=G('rev-parse',old+':host');index=Path(G('rev-parse','--git-path','index').decode().strip());index=index if index.is_absolute() else repo/index;idxsha=sha(index.read_bytes()) if index.exists() else None
prior=json.loads((B/'module-plan-current-publication.json').read_text(encoding='utf-8'));assert prior['remote_verified_commit']==old and prior['hardware_files_manifest_count']==427
currentchanges={r['file']:r['actual'] for r in prior['native_changes_only']}
checks=json.loads((E/'control-power-current-plan.json').read_text(encoding='utf-8-sig'))['native_file_checks']
for r in checks:assert sha(Path(r['file']).read_bytes())==currentchanges.get(r['file'],r['actual']),r['file']
proposal=json.loads((E/'edit-control-interface-current.json').read_text(encoding='utf-8'))
for p in proposal['registered_producer_recheck']:assert sha(Path(p['path']).read_bytes())==p['current_sha']
assert proposal['model_verification']['all_parallel_pairs']==65536 and proposal['RTL_changed'] is False
updates={}
for n in ['edit-control-interface-current.py','edit-control-interface-current.json','edit-control-interface-current.md','edit-control-parts-lookup-current.json','edit-control-parts-jlcsearch-current.json','edit-control-interface-publish-current.py','control64-candidate-BOM-current.json','control64-candidate-BOM-current.csv','Nano-TF-storage-scope-current.json','Nano-TF-storage-scope-current.md','Nano20K-TF-proof-current.png','module-readiness-current.py','module-readiness-current.json','module-readiness-current.md','purchase-assembly-user-review-current.md']:
 updates['hardware/current/module-plan/evidence/'+n]=(E/n).read_bytes()
for n in ['PCB-CURRENT-CAPACITY-RECOVERY-20261024.json','PCB-ACTIVE-WORK.json','实体交付当前入口.json','模块方案-当前证据.json','模块方案-当前工作单.md']:
 updates['hardware/current/module-plan/'+n]=(B/n).read_bytes()
now=datetime.datetime.now().astimezone().isoformat();c=json.loads(G('show',old+':hardware/current/CURRENT-HARDWARE.json'));c['last_metadata_update']=now
c['module_delivery_main']['current_readiness']='module-plan/evidence/module-readiness-current.json';c['module_delivery_main']['edit_three_action_proposal']='module-plan/evidence/edit-control-interface-current.md';c['module_delivery_main']['Nano_TF_scope']='module-plan/evidence/Nano-TF-storage-scope-current.md';c['module_delivery_main']['complete_purchase_plan']=False;updates['hardware/current/CURRENT-HARDWARE.json']=js(c)
s=G('show',old+':hardware/current/README.md').decode('utf-8');s+='\n\n## Independent edit action proposal and actual remaining gates\n\nRead module-plan/evidence/module-readiness-current.md first: six remaining delivery gate groups, not onlySAVE/CANCEL. Three separate physical APPLY/SAVE/CANCEL candidate inputs use one additional LV165 in the same existing serial bus;8new components, no extra externalFPGA GPIO, original8-bit encoding preserved after normalization.65536offlineparallelstates checked; noRTL/CAD/board acceptance. Original56+8=64candidate component allocation excludes newconnectors andmanufacturingpreweld costs. Nano3921 page5 proves ownedTFsocket, pullups/decoupling; no separate FPGA-sideTFreader module. Card SKU and actual PCM recordplay still open; FIT0570/FIT0394 discontinued.35reference-scope decision andfull<=700preweld/freight budget remain pending.\n';updates['hardware/current/README.md']=s.encode('utf-8')
m=json.loads(G('show',old+':project/versions/engineering-sources-20261023.json'))
for p,b in updates.items():
 k=p[len('hardware/current/'):];r=m['areas']['hardware']['files'].get(k,{})
 r.update(stored=p,bytes=len(b),sha256=sha(b),stored_sha256=sha(b),codec='raw',source='Concrete3independent action serial-chain proposal and ownedNanoTF evidence;64candidate electrical rows, no product/preweld/purchase acceptance; native andregisteredRTL unchanged')
 m['areas']['hardware']['files'][k]=r
m['areas']['hardware'].update(updated_at=now,product_acceptance=False,validation_inherited=False);updates['project/versions/engineering-sources-20261023.json']=js(m)
alt=E/'edit-control-interface-publish-current.index';assert not alt.exists();env=dict(os.environ,GIT_INDEX_FILE=str(alt));G('read-tree',old,env=env)
for p,b in updates.items():
 oid=G('hash-object','-w','--stdin',input=b).decode().strip();G('update-index','--add','--cacheinfo','100644',oid,p,env=env)
tree=G('write-tree',env=env).decode().strip();commit=G('commit-tree',tree,'-p',old,input=b'Add independent edit action wiring proposal and owned Nano TF scope evidence\n').decode().strip()
assert G('rev-parse',commit+':fpga')==fpga and G('rev-parse',commit+':host')==host
for p,b in updates.items():assert sha(G('show',commit+':'+p))==sha(b)
assert G('status','--porcelain=v1')==status and G('rev-parse','HEAD')==head and (sha(index.read_bytes()) if index.exists() else None)==idxsha
G('update-ref',ref,commit,old);alt.unlink()
r=dict(at=now,parent_commit=old,commit=commit,branch=ref[len('refs/heads/'):],updated_files=len(updates),updated_blob_SHA_verified=len(updates),prior427verified_files_inherited=True,hardware_files_manifest_count=len(m['areas']['hardware']['files']),FPGA_axis_unchanged=True,host_axis_unchanged=True,working_HEAD_index_and_untracked_status_unchanged=True,native40_unchanged_this_followup=True,registered_producer13_unchanged=True,native_changes_only=prior['native_changes_only'],not_for_fabrication=True,complete_purchase_plan=False,remote_push_completed=False)
(B/'module-plan-current-publication.json').write_bytes(js(r));print(json.dumps(r,ensure_ascii=True),flush=True)
