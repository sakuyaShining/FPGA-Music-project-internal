from pathlib import Path
import subprocess,os,json,hashlib,datetime
B=Path(r'D:\FPGA-Project\codex-deliverables\dual-screen-review-20261020-v2');E=B/'module-plan-current-evidence'
repo=Path(r'C:\Users\Sakuya\.codex\worktrees\4a4b\FPGA-Music-project')
branch='codex/pcb-paused-status-20261025';ref='refs/heads/'+branch
def git(*a,input=None,env=None):return subprocess.check_output(['git',*a],cwd=repo,input=input,env=env)
def sha(b):return hashlib.sha256(b).hexdigest()
def js(d):return (json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
old=git('rev-parse',ref).decode().strip();assert old=='d990a05920671cd7cfcb9eccdfce93647065b9be',old
assert git('remote','get-url','--push','internal').decode().strip()=='https://github.com/sakuyaShining/FPGA-Music-project-internal.git'
assert git('ls-remote','internal',ref).decode().split()[0]==old,'Remote changed; inspect before continuation'
status=git('status','--porcelain=v1');head=git('rev-parse','HEAD')
fpga=git('rev-parse',old+':fpga');host=git('rev-parse',old+':host')
realindex=Path(git('rev-parse','--git-path','index').decode().strip())
if not realindex.is_absolute():realindex=repo/realindex
realindexsha=sha(realindex.read_bytes()) if realindex.exists() else None
proof=json.loads((E/'control-power-current-plan.json').read_text(encoding='utf-8'))
assert all(sha(Path(r['file']).read_bytes())==r['actual'] for r in proof['native_file_checks']),'Native CAD changed; review before publishing preservation claim'
now=datetime.datetime.now().astimezone().isoformat();updates={}
fm=json.loads((E/'control-power-current-stage-file-map.json').read_text(encoding='utf-8'))
for n in fm['evidence_files']+['control-power-current-stage-file-map.json','control-power-publish-current.py']:
 updates['hardware/current/module-plan/evidence/'+n]=(E/n).read_bytes()
for n in ['模块方案-当前工作单.md','模块方案-当前证据.json']:updates['hardware/current/module-plan/'+n]=(B/n).read_bytes()
updates['hardware/current/module-plan/227件功能分块与混合方案映射-current.json']=Path(fm['mapping_source']).read_bytes()
c=json.loads(git('show',old+':hardware/current/CURRENT-HARDWARE.json'));c['last_metadata_update']=now
c['module_delivery_main']['control_power_contract']='module-plan/evidence/control-power-current-plan.md'
c['module_delivery_main']['control_power_stage']='Original56functions retained.5domestic priced through-hole lines includingMOQ33.704CNY before carrier/assembly/wiring/freight. Original23.7k1% TPS2553 threshold1.002..1.184A; no threshold relaxation or default speaker loading. Exact remaining preweld modules/whole700budget not accepted; no CAD/RTL edits.'
updates['hardware/current/CURRENT-HARDWARE.json']=js(c)
t=git('show',old+':hardware/current/README.md').decode('utf-8');marker='\n## 当前控制与供电核对'
t=t.split(marker)[0]+marker+'（10月27日）\n\n控制/存储/接口/供电原56项功能与网络逐项保留。已核5行国内直插器件、插座和去耦实际价/现货/最小购买量，共33.704元，尚缺载体、实际组装、配线、保护和运费。原TPS2553限流按23.7kΩ±1%核为约1.002—1.184A，未放宽；音箱供电须另做完整负载预算。详见module-plan/evidence/control-power-current-plan.md。原227项无删减；本轮原生40项文件哈希未变，未改RTL、烧录或下单，完整700元可买清单/交期仍未收口。\n'
updates['hardware/current/README.md']=t.encode('utf-8')
m=json.loads(git('show',old+':project/versions/engineering-sources-20261023.json'))
for p,b in updates.items():
 k=p.removeprefix('hardware/current/');r=m['areas']['hardware']['files'].get(k,{})
 r.update(stored=p,bytes=len(b),sha256=sha(b),stored_sha256=sha(b),codec='raw',source='Current control/power primary-source procurement and original56function reconciliation; no CAD/RTL writes')
 m['areas']['hardware']['files'][k]=r
m['areas']['hardware'].update(updated_at=now,product_acceptance=False,validation_inherited=False)
m['areas']['hardware']['control_power_scope']='56originalfunctions retained;5lines33.704CNY including MOQ only. Off-state/current-limiter/whole module readiness open. Native40file hashes unchanged.'
updates['project/versions/engineering-sources-20261023.json']=js(m)
alt=E/'control-power-publish-current.index';assert not alt.exists(),'Own alternate index exists; inspect preceding operation'
env=dict(os.environ,GIT_INDEX_FILE=str(alt));git('read-tree',old,env=env)
for p,b in updates.items():
 oid=git('hash-object','-w','--stdin',input=b).decode().strip();git('update-index','--add','--cacheinfo','100644',oid,p,env=env)
tree=git('write-tree',env=env).decode().strip()
commit=git('commit-tree',tree,'-p',old,input=b'Document control and protected power procurement constraints\n').decode().strip()
assert git('rev-parse',commit+':fpga')==fpga and git('rev-parse',commit+':host')==host
for p,b in updates.items():assert sha(git('show',commit+':'+p))==sha(b),p
for k,r in m['areas']['hardware']['files'].items():assert sha(git('show',commit+':'+r['stored']))==r['stored_sha256'],k
assert git('status','--porcelain=v1')==status and git('rev-parse','HEAD')==head
assert (sha(realindex.read_bytes()) if realindex.exists() else None)==realindexsha
git('update-ref',ref,commit,old)
r=dict(at=now,parent_commit=old,commit=commit,branch=branch,files_updated=list(updates),hardware_files_SHA_verified=len(m['areas']['hardware']['files']),FPGA_axis_unchanged=True,host_axis_unchanged=True,native40_unchanged=True,working_HEAD_index_and_untracked_status_unchanged=True,not_for_fabrication=True,complete_purchase_plan=False,remote_push_completed=False)
(B/'module-plan-current-publication.json').write_bytes(js(r));alt.unlink();print(json.dumps(r,ensure_ascii=False))
