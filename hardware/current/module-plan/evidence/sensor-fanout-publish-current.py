from pathlib import Path
import subprocess,os,json,hashlib,datetime
B=Path(r'D:\FPGA-Project\codex-deliverables\dual-screen-review-20261020-v2');E=B/'module-plan-current-evidence'
repo=Path(r'C:\Users\Sakuya\.codex\worktrees\4a4b\FPGA-Music-project');branch='codex/pcb-paused-status-20261025';ref='refs/heads/'+branch
def git(*a,input=None,env=None):return subprocess.check_output(['git',*a],cwd=repo,input=input,env=env)
def sha(b):return hashlib.sha256(b).hexdigest()
def js(d):return (json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
old=git('rev-parse',ref).decode().strip();assert old=='682fafc43e617fef456dab316166b2e54443db25',old
assert git('remote','get-url','--push','internal').decode().strip()=='https://github.com/sakuyaShining/FPGA-Music-project-internal.git'
assert git('ls-remote','internal',ref).decode().split()[0]==old,'Remote changed; inspect first'
status=git('status','--porcelain=v1');head=git('rev-parse','HEAD');fpga=git('rev-parse',old+':fpga');host=git('rev-parse',old+':host')
index=Path(git('rev-parse','--git-path','index').decode().strip());index=index if index.is_absolute() else repo/index
indexsha=sha(index.read_bytes()) if index.exists() else None
fm=json.loads((E/'sensor-fanout-stage-file-map-current.json').read_text(encoding='utf-8'))
assert all(sha(Path(r['file']).read_bytes())==r['actual'] for r in fm['native_file_checks'])
updates={}
for n in fm['evidence_files']+['sensor-fanout-stage-file-map-current.json','sensor-fanout-publish-current.py']:
 updates['hardware/current/module-plan/evidence/'+n]=(E/n).read_bytes()
for n in ['模块方案-当前工作单.md','模块方案-当前证据.json']:updates['hardware/current/module-plan/'+n]=(B/n).read_bytes()
now=datetime.datetime.now().astimezone().isoformat()
c=json.loads(git('show',old+':hardware/current/CURRENT-HARDWARE.json'));c['last_metadata_update']=now
c['module_delivery_main']['electrode_channel_plan']='module-plan/evidence/sensor-header-fanout-current.md'
c['module_delivery_main']['electrode_stage']='Offline explicit geometry:14header fanouts+14NCbridges+left8complete E paths physical/allPADconnectivity pass after14Ground-return-via mirrors. Right6/7controls and actualGround reference remain. Proposed22PAD changes NOT applied. Native40unchanged;21nets56items remain. No purchase/manufacturing release.'
updates['hardware/current/CURRENT-HARDWARE.json']=js(c)
t=git('show',old+':hardware/current/README.md').decode('utf-8');marker='\n## 当前明确扇出候选'
updates['hardware/current/README.md']=(t.split(marker)[0]+marker+'（10月27日）\n\n离线镜像14个J1回流孔后，14路排针—ESD扇出、14段NC短桥及左8路完整电极路径共同物理/全PAD连通检查通过。右6电极路径及7控制网、实际Ground重铺完整参考仍未过门；假设模型TH终端外仍有0.000492292mm²缺失，未扩例外。22PAD/14孔均未原生改动，当前源仍21网56项。详见module-plan/evidence/sensor-header-fanout-current.md。完整700元可买清单/预焊交期仍未闭合。\n').encode('utf-8')
m=json.loads(git('show',old+':project/versions/engineering-sources-20261023.json'))
for p,b in updates.items():
 k=p.removeprefix('hardware/current/');r=m['areas']['hardware']['files'].get(k,{})
 r.update(stored=p,bytes=len(b),sha256=sha(b),stored_sha256=sha(b),codec='raw',source='Explicit14header fanout and left8complete paths proposal; native40 unchanged, no RTL writes')
 m['areas']['hardware']['files'][k]=r
m['areas']['hardware'].update(updated_at=now,product_acceptance=False,validation_inherited=False)
m['areas']['hardware']['electrode_candidate_scope']='14headerfanout+14NC+8complete E paths physical/4PAD connectivity pass;14via mirrors and22PAD candidate only. Right6/7controls/actualGround pending. Native unchanged.'
updates['project/versions/engineering-sources-20261023.json']=js(m)
alt=E/'sensor-fanout-publish-current.index';assert not alt.exists(),'Inspect own prior alternate index'
env=dict(os.environ,GIT_INDEX_FILE=str(alt));git('read-tree',old,env=env)
for p,b in updates.items():
 oid=git('hash-object','-w','--stdin',input=b).decode().strip();git('update-index','--add','--cacheinfo','100644',oid,p,env=env)
tree=git('write-tree',env=env).decode().strip();commit=git('commit-tree',tree,'-p',old,input=b'Record explicit sensor fanout and left8 path candidate\n').decode().strip()
assert git('rev-parse',commit+':fpga')==fpga and git('rev-parse',commit+':host')==host
for p,b in updates.items():assert sha(git('show',commit+':'+p))==sha(b),p
for k,r in m['areas']['hardware']['files'].items():assert sha(git('show',commit+':'+r['stored']))==r['stored_sha256'],k
assert git('status','--porcelain=v1')==status and git('rev-parse','HEAD')==head
assert (sha(index.read_bytes()) if index.exists() else None)==indexsha
git('update-ref',ref,commit,old)
r=dict(at=now,parent_commit=old,commit=commit,branch=branch,files_updated=list(updates),hardware_files_SHA_verified=len(m['areas']['hardware']['files']),FPGA_axis_unchanged=True,host_axis_unchanged=True,native40_unchanged=True,working_HEAD_index_and_untracked_status_unchanged=True,not_for_fabrication=True,complete_purchase_plan=False,remote_push_completed=False)
(B/'module-plan-current-publication.json').write_bytes(js(r));alt.unlink();print(json.dumps(r,ensure_ascii=False))
