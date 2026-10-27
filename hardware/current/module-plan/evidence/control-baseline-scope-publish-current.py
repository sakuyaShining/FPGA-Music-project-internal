from pathlib import Path
import subprocess,os,json,hashlib,datetime
B=Path(r'D:\FPGA-Project\codex-deliverables\dual-screen-review-20261020-v2');E=B/'module-plan-current-evidence';repo=Path(r'C:\Users\Sakuya\.codex\worktrees\4a4b\FPGA-Music-project');ref='refs/heads/codex/pcb-paused-status-20261025'
def G(*a,**kw):return subprocess.check_output(['git',*a],cwd=repo,**kw)
def sha(b):return hashlib.sha256(b).hexdigest()
def js(x):return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
old=G('rev-parse',ref).decode().strip();assert old=='5a2c487c2d589891333db3c52938b670fc5869ec',old
assert G('remote','get-url','--push','internal').decode().strip()=='https://github.com/sakuyaShining/FPGA-Music-project-internal.git'
assert G('ls-remote','internal',ref).decode().split()[0]==old
status=G('status','--porcelain=v1');head=G('rev-parse','HEAD');fpga=G('rev-parse',old+':fpga');host=G('rev-parse',old+':host');index=Path(G('rev-parse','--git-path','index').decode().strip());index=index if index.is_absolute() else repo/index;idxsha=sha(index.read_bytes()) if index.exists() else None
prior=json.loads((B/'module-plan-current-publication.json').read_text(encoding='utf-8'));assert prior['remote_verified_commit']==old and prior['hardware_files_SHA_verified']==421
for r in prior['native_changes_only']:assert sha(Path(r['file']).read_bytes())==r['actual']
proof=json.loads((E/'control-baseline-scope-review-current.json').read_text(encoding='utf-8'));assert proof['actual_schematic_baseline']['LV165']==1 and len(proof['original_schematic_checks'])==2
for r in proof['original_schematic_checks']:assert sha(Path(r['file']).read_bytes())==r['sha256']
updates={}
for n in ['purchase-assembly-user-review-current.md','control-baseline-scope-review-current.md','control-baseline-scope-review-current.json','control-baseline-scope-register-current.py','control-baseline-scope-publish-current.py','harness-sourcing-current.json','harness-56dz2839-current.html']:
 updates['hardware/current/module-plan/evidence/'+n]=(E/n).read_bytes()
for n in ['PCB-CURRENT-CAPACITY-RECOVERY-20261024.json','PCB-ACTIVE-WORK.json','实体交付当前入口.json','模块方案-当前证据.json','模块方案-当前工作单.md']:
 updates['hardware/current/module-plan/'+n]=(B/n).read_bytes()
now=datetime.datetime.now().astimezone().isoformat();c=json.loads(G('show',old+':hardware/current/CURRENT-HARDWARE.json'));c['last_metadata_update']=now;c['module_delivery_main']['control_baseline_scope_correction']=proof;c['module_delivery_main']['complete_purchase_plan']=False;updates['hardware/current/CURRENT-HARDWARE.json']=js(c)
s=G('show',old+':hardware/current/README.md').decode('utf-8');s+='\n\n## Control purchase scope correction\n\nPrevious13buttons/two165 claim withdrawn:8harmonic zones belong onJ10 touch screen. Existing schematic5buttons+push encoder, oneLV165 with serialinput grounded. R06independent edit operations contract remains pending; no GPIO/RTL change or product acceptance. Read control-baseline-scope-review-current.md and corrected purchase-assembly-user-review-current.md. New exact cable SKU evidence remains pending connector/length/current/freight validation.\n';updates['hardware/current/README.md']=s.encode('utf-8')
m=json.loads(G('show',old+':project/versions/engineering-sources-20261023.json'))
for p,b in updates.items():
 k=p[len('hardware/current/'):];r=m['areas']['hardware']['files'].get(k,{})
 r.update(stored=p,bytes=len(b),sha256=sha(b),stored_sha256=sha(b),codec='raw',source='Withdraw unauthorized13button/two165 purchase claim; existing5buttons/pushencoder/one165 verified, fullR06 contract and procurement pending; native/RTL unchanged')
 m['areas']['hardware']['files'][k]=r
m['areas']['hardware'].update(updated_at=now,product_acceptance=False,validation_inherited=False);updates['project/versions/engineering-sources-20261023.json']=js(m)
alt=E/'control-baseline-scope-publish-current.index';assert not alt.exists();env=dict(os.environ,GIT_INDEX_FILE=str(alt));G('read-tree',old,env=env)
for p,b in updates.items():
 oid=G('hash-object','-w','--stdin',input=b).decode().strip();G('update-index','--add','--cacheinfo','100644',oid,p,env=env)
tree=G('write-tree',env=env).decode().strip();commit=G('commit-tree',tree,'-p',old,input=b'Correct control purchase scope against product spec and original165 input map\n').decode().strip()
assert G('rev-parse',commit+':fpga')==fpga and G('rev-parse',commit+':host')==host
for p,b in updates.items():assert sha(G('show',commit+':'+p))==sha(b)
assert G('status','--porcelain=v1')==status and G('rev-parse','HEAD')==head and (sha(index.read_bytes()) if index.exists() else None)==idxsha
G('update-ref',ref,commit,old);alt.unlink()
r=dict(at=now,parent_commit=old,commit=commit,branch=ref[len('refs/heads/'):],updated_files=len(updates),updated_blob_SHA_verified=len(updates),prior421verified_files_inherited=True,hardware_files_manifest_count=len(m['areas']['hardware']['files']),FPGA_axis_unchanged=True,host_axis_unchanged=True,working_HEAD_index_and_untracked_status_unchanged=True,native_unchanged_this_followup=True,native_changes_only=prior['native_changes_only'],not_for_fabrication=True,complete_purchase_plan=False,remote_push_completed=False)
(B/'module-plan-current-publication.json').write_bytes(js(r));print(json.dumps(r,ensure_ascii=True),flush=True)
