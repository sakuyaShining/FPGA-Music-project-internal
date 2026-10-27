from pathlib import Path
import subprocess, os, json, hashlib, datetime

B=Path(r'D:\FPGA-Project\codex-deliverables\dual-screen-review-20261020-v2')
E=B/'module-plan-current-evidence'
repo=Path(r'C:\Users\Sakuya\.codex\worktrees\4a4b\FPGA-Music-project')
branch='codex/pcb-paused-status-20261025'
ref='refs/heads/'+branch
def git(*args,input=None,env=None):
 return subprocess.check_output(['git',*args],cwd=repo,input=input,env=env)
def sha(b): return hashlib.sha256(b).hexdigest()
def js(d): return (json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
old=git('rev-parse',ref).decode().strip()
assert old=='a5086e7212ce4607357cdbdc1f3778aa98b19a42', old
assert git('remote','get-url','--push','internal').decode().strip()=='https://github.com/sakuyaShining/FPGA-Music-project-internal.git'
remote=git('ls-remote','internal',ref).decode().split()[0]
assert remote==old, ('Inspect actual remote before any retry',remote)
status=git('status','--porcelain=v1');head=git('rev-parse','HEAD')
fpga=git('rev-parse',old+':fpga');host=git('rev-parse',old+':host')
index_real=repo/'.git'
real_index=Path(git('rev-parse','--git-path','index').decode().strip())
if not real_index.is_absolute(): real_index=repo/real_index
index_sha=sha(real_index.read_bytes()) if real_index.exists() else None
now=datetime.datetime.now().astimezone().isoformat()
current=json.loads(git('show',old+':hardware/current/CURRENT-HARDWARE.json'))
manifest=json.loads(git('show',old+':project/versions/engineering-sources-20261023.json'))
updates={}
filemap=json.loads((E/'audio-current-stage-file-map.json').read_text(encoding='utf-8'))
for name in filemap['evidence_files']+['audio-current-stage-file-map.json','audio-publish-current-stage.py']:
 updates['hardware/current/module-plan/evidence/'+name]=(E/name).read_bytes()
for name in ['模块方案-当前工作单.md','模块方案-当前证据.json']:
 updates['hardware/current/module-plan/'+name]=(B/name).read_bytes()
updates['hardware/current/module-plan/227件功能分块与混合方案映射-current.json']=Path(filemap['mapping_source']).read_bytes()
current['last_metadata_update']=now
current['module_delivery_main']['audio_contract']='module-plan/evidence/audio-010313400000-wiring-current.md'
current['module_delivery_main']['audio_stage']='Exact55CNY SKU010313400000 pins/0x4D DAC/0x60 TPA and original17item reconciliation:11schematic subfunctions,6pending, nofunction removed and no complete module acceptance. Registered producer F07 clock/format/initialization gap saved; no RTL edits. Playback sourcing includes exact unavailable/rejected items, no complete quoted purchase chain.'
current['module_delivery_main']['audio_playback_sourcing']='module-plan/evidence/audio-playback-sourcing-current.json'
updates['hardware/current/CURRENT-HARDWARE.json']=js(current)
readme=git('show',old+':hardware/current/README.md').decode('utf-8')
marker='\n## 当前音频模块核对'
readme=readme.split(marker)[0]+marker+'（10月27日）\n\n'
readme+='55元斑梨SKU010313400000逐针接线、DAC0x4D/耳放0x60与原17件音频功能映射已保存到module-plan/evidence/audio-010313400000-wiring-current.md。11项仅有原理图子功能证据、6项仍待覆盖；227功能全部保留。F07记录当前登记producer实际时钟、格式和完整初始化缺口，没有改RTL。DFR功放有货但仍缺适配播放链；FIT0502实际缺货，低价3525BOX因1.5kHz起的原厂有效频段未选作唯一乐器扬声器。完整700元清远可买清单/交期仍未闭合，不得下单。原主板及当前Sensor14Bank本轮40项文件哈希保持。\n'
updates['hardware/current/README.md']=readme.encode('utf-8')
for path,data in updates.items():
 key=path.removeprefix('hardware/current/')
 rec=manifest['areas']['hardware']['files'].get(key,{})
 rec.update(stored=path,bytes=len(data),sha256=sha(data),stored_sha256=sha(data),codec='raw',source='Current audio module primary-source and registered-producer read-only review; original227 retained; no CAD/RTL edits')
 manifest['areas']['hardware']['files'][key]=rec
manifest['areas']['hardware']['updated_at']=now
manifest['areas']['hardware']['product_acceptance']=False
manifest['areas']['hardware']['validation_inherited']=False
manifest['areas']['hardware']['audio_review_scope']='Exact55CNY module pins and17originalitem reconciliation;11schematic subfunctions only/6pending,0fullyaccepted moduleitems. Current audio clock/init F07 documented. Native40files unchanged; whole purchasing/700CNY/delivery/physical acceptance open.'
updates['project/versions/engineering-sources-20261023.json']=js(manifest)
alt=E/'audio-publish-current.index'
assert not alt.exists(), 'Own alternate index exists: inspect previous operation, do not replay blindly'
env=dict(os.environ,GIT_INDEX_FILE=str(alt))
git('read-tree',old,env=env)
for path,data in updates.items():
 oid=git('hash-object','-w','--stdin',input=data).decode().strip()
 git('update-index','--add','--cacheinfo','100644',oid,path,env=env)
tree=git('write-tree',env=env).decode().strip()
commit=git('commit-tree',tree,'-p',old,input=b'Document exact audio module pin contract and original BOM coverage\n').decode().strip()
assert git('rev-parse',commit+':fpga')==fpga and git('rev-parse',commit+':host')==host
for path,data in updates.items(): assert sha(git('show',commit+':'+path))==sha(data),path
for key,rec in manifest['areas']['hardware']['files'].items():
 assert sha(git('show',commit+':'+rec['stored']))==rec['stored_sha256'], key
assert git('status','--porcelain=v1')==status and git('rev-parse','HEAD')==head
assert (sha(real_index.read_bytes()) if real_index.exists() else None)==index_sha
record=dict(at=now,parent_commit=old,commit=commit,branch=branch,files_updated=list(updates),hardware_files_SHA_verified=len(manifest['areas']['hardware']['files']),FPGA_axis_unchanged=True,host_axis_unchanged=True,native40_unchanged=True,working_HEAD_index_and_untracked_status_unchanged=True,not_for_fabrication=True,complete_purchase_plan=False,remote_push_completed=False)
git('update-ref',ref,commit,old)
(B/'module-plan-current-publication.json').write_bytes(js(record))
alt.unlink()
print(json.dumps(record,ensure_ascii=False))
