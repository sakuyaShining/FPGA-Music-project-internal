from pathlib import Path
import subprocess,os,json,hashlib,datetime
B=Path(r'D:\FPGA-Project\codex-deliverables\dual-screen-review-20261020-v2');E=B/'module-plan-current-evidence'
repo=Path(r'C:\Users\Sakuya\.codex\worktrees\4a4b\FPGA-Music-project');branch='codex/pcb-paused-status-20261025';ref='refs/heads/'+branch
def git(*a,input=None,env=None):return subprocess.check_output(['git',*a],cwd=repo,input=input,env=env)
def sha(b):return hashlib.sha256(b).hexdigest()
def js(d):return (json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
old=git('rev-parse',ref).decode().strip();assert old=='dfa046b296a3f6d5e7d2f63d31047fd5e00b14a2',old
assert git('remote','get-url','--push','internal').decode().strip()=='https://github.com/sakuyaShining/FPGA-Music-project-internal.git'
assert git('ls-remote','internal',ref).decode().split()[0]==old,'Remote changed; inspect first'
status=git('status','--porcelain=v1');head=git('rev-parse','HEAD');fpga=git('rev-parse',old+':fpga');host=git('rev-parse',old+':host')
index=Path(git('rev-parse','--git-path','index').decode().strip());index=index if index.is_absolute() else repo/index
indexsha=sha(index.read_bytes()) if index.exists() else None
fm=json.loads((E/'delivery-risk-stage-file-map-current.json').read_text(encoding='utf-8'))
assert all(sha(Path(r['file']).read_bytes())==r['actual'] for r in fm['native_file_checks'])
updates={}
for n in fm['evidence_files']+['delivery-risk-stage-file-map-current.json','delivery-risk-publish-current.py']:
 updates['hardware/current/module-plan/evidence/'+n]=(E/n).read_bytes()
for n in ['模块方案-当前工作单.md','模块方案-当前证据.json']:updates['hardware/current/module-plan/'+n]=(B/n).read_bytes()
now=datetime.datetime.now().astimezone().isoformat()
c=json.loads(git('show',old+':hardware/current/CURRENT-HARDWARE.json'));c['last_metadata_update']=now
c['module_delivery_main']['product_spec12_comparison']='module-plan/evidence/product-spec-12-comparison-current.md'
c['module_delivery_main']['delivery_risk_plan']='module-plan/evidence/delivery-risk-plan-current.md'
c['module_delivery_main']['delivery_planning_stage']='Full12 requirement comparison and AUX scope corrected. Controllable paperwork versus uncertain engineering/integration and external assembly/delivery separated. Oct28design checkpoint/Oct30arrival target/Nov3video internal target are not promised dates. No function cuts; no CAD/RTL/order changes; no purchase release.'
updates['hardware/current/CURRENT-HARDWARE.json']=js(c)
t=git('show',old+':hardware/current/README.md').decode('utf-8');marker='\n## 完整交付可控性与十二条核对'
updates['hardware/current/README.md']=(t.split(marker)[0]+marker+'（10月27日）\n\n全部12条逐项对照与可控性倒排见module-plan/evidence/product-spec-12-comparison-current.md及delivery-risk-plan-current.md。R09本为AUX/不装机内喇叭偏好，外接试听功放/喇叭不是AUX必购门；R12按用户授权调整为模块/必要简单预焊小板，完整可装要求不降。84采集位不等于25音位表情已实现。前端/产品固件接合及供应交期均未闭合，10月28日设计检查点、30日到齐与11月3日视频均为内部倒排目标，未获供应商承诺，不保证11月4日全12条交付。不删功能、不改原生/RTL或下单。\n').encode('utf-8')
m=json.loads(git('show',old+':project/versions/engineering-sources-20261023.json'))
for p,b in updates.items():
 k=p.removeprefix('hardware/current/');r=m['areas']['hardware']['files'].get(k,{})
 r.update(stored=p,bytes=len(b),sha256=sha(b),stored_sha256=sha(b),codec='raw',source='Full12 requirement and schedule uncertainty planning; corrected AUX scope; native40 unchanged, no RTL writes')
 m['areas']['hardware']['files'][k]=r
m['areas']['hardware'].update(updated_at=now,product_acceptance=False,validation_inherited=False)
m['areas']['hardware']['delivery_planning_scope']='Full12 retained goals; manufacturing form adjusted by directuser approval. Technical and supplier completion dates remain unproven. No complete procurement release.'
updates['project/versions/engineering-sources-20261023.json']=js(m)
alt=E/'delivery-risk-publish-current.index';assert not alt.exists(),'Inspect own prior alternate index'
env=dict(os.environ,GIT_INDEX_FILE=str(alt));git('read-tree',old,env=env)
for p,b in updates.items():
 oid=git('hash-object','-w','--stdin',input=b).decode().strip();git('update-index','--add','--cacheinfo','100644',oid,p,env=env)
tree=git('write-tree',env=env).decode().strip();commit=git('commit-tree',tree,'-p',old,input=b'Record full product requirement comparison and delivery risk plan\n').decode().strip()
assert git('rev-parse',commit+':fpga')==fpga and git('rev-parse',commit+':host')==host
for p,b in updates.items():assert sha(git('show',commit+':'+p))==sha(b),p
for k,r in m['areas']['hardware']['files'].items():assert sha(git('show',commit+':'+r['stored']))==r['stored_sha256'],k
assert git('status','--porcelain=v1')==status and git('rev-parse','HEAD')==head
assert (sha(index.read_bytes()) if index.exists() else None)==indexsha
git('update-ref',ref,commit,old)
r=dict(at=now,parent_commit=old,commit=commit,branch=branch,files_updated=list(updates),hardware_files_SHA_verified=len(m['areas']['hardware']['files']),FPGA_axis_unchanged=True,host_axis_unchanged=True,native40_unchanged=True,working_HEAD_index_and_untracked_status_unchanged=True,not_for_fabrication=True,complete_purchase_plan=False,remote_push_completed=False)
(B/'module-plan-current-publication.json').write_bytes(js(r));alt.unlink();print(json.dumps(r,ensure_ascii=False))
