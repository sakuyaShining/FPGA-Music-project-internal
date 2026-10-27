from pathlib import Path
import json,subprocess,os,hashlib,datetime
B=Path(r'D:\FPGA-Project\codex-deliverables\dual-screen-review-20261020-v2');E=B/'module-plan-current-evidence';repo=Path(r'C:\Users\Sakuya\.codex\worktrees\4a4b\FPGA-Music-project');branch='codex/pcb-paused-status-20261025';ref='refs/heads/'+branch
G=lambda *a,**kw:subprocess.check_output(['git',*a],cwd=repo,**kw)
sha=lambda b:hashlib.sha256(b).hexdigest()
js=lambda x:(json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
old=G('rev-parse',ref).decode().strip();assert old=='92d682f2c32e74fc6f00656fbb3f2dd4227ec867',old
assert G('remote','get-url','--push','internal').decode().strip()=='https://github.com/sakuyaShining/FPGA-Music-project-internal.git'
assert G('ls-remote','internal',ref).decode().split()[0]==old
status=G('status','--porcelain=v1');head=G('rev-parse','HEAD');fpga=G('rev-parse',old+':fpga');host=G('rev-parse',old+':host');index=Path(G('rev-parse','--git-path','index').decode().strip());index=index if index.is_absolute() else repo/index;idxsha=sha(index.read_bytes()) if index.exists() else None
checks=json.loads((E/'control-power-current-plan.json').read_text(encoding='utf-8-sig'))['native_file_checks'];changes=[]
for r in checks:
 p=Path(r['file']);h=sha(p.read_bytes())
 if h!=r['actual']:
  assert p.name in ['FPGA-Music-U9ControlWork-20261023.eprj3','Sensor14_frontend.esch2','PCB2.epcb2'],str(p)
  changes.append({'file':str(p),'before':r['actual'],'actual':h})
assert len(changes)==3
stage=json.loads((E/'sensor-fourlayer-progress-current.json').read_text(encoding='utf-8'));assert stage['accepted'] is False and stage['native_strict_DRC_errors']==0 and stage['independent_reference_pass'] is False
updates={};extensions={'.py','.js','.json','.md','.png','.wkb','.epcb2','.esch2'}
files=[p for p in E.iterdir() if p.is_file() and p.suffix in extensions and p.name.startswith(('sensor-today-','sensor-fourlayer-','sensor84-','sensor-whole14-')) and 'publish-current' not in p.name]
for p in files:updates['hardware/current/module-plan/evidence/'+p.name]=p.read_bytes()
recovery=(E/'sensor-fourlayer-native-recovery-current/recovery-manifest.json').read_bytes();updates['hardware/current/module-plan/evidence/sensor-fourlayer-recovery-manifest-current.json']=recovery
for n in ['PCB-CURRENT-CAPACITY-RECOVERY-20261024.json','PCB-ACTIVE-WORK.json','\u5b9e\u4f53\u4ea4\u4ed8\u5f53\u524d\u5165\u53e3.json','\u6a21\u5757\u65b9\u6848-\u5f53\u524d\u8bc1\u636e.json','\u6a21\u5757\u65b9\u6848-\u5f53\u524d\u5de5\u4f5c\u5355.md']:updates['hardware/current/module-plan/'+n]=(B/n).read_bytes()
now=datetime.datetime.now().astimezone().isoformat();c=json.loads(G('show',old+':hardware/current/CURRENT-HARDWARE.json'));c['last_metadata_update']=now;c['module_delivery_main']['sensor_fourlayer_trial_current']=stage;c['module_delivery_main']['sensor84_semantic_map']='module-plan/evidence/sensor84-semantic-wiring-current.json';c['module_delivery_main']['complete_purchase_plan']=False;updates['hardware/current/CURRENT-HARDWARE.json']=js(c)
t=G('show',old+':hardware/current/README.md').decode('utf-8');marker='\n## Current Sensor14Bank fourlayer trial';updates['hardware/current/README.md']=(t.split(marker)[0]+marker+'\n\nReal native fourlayer candidate:28parts/150PAD/223lines/48vias;35explicitPAD changes match schematic; native strictDRC0 and zero unconnected after actual pours/save-close-reopen. All91sourceCu retained. Independent Ground reference has34failedsegments; fullDC/minneck/oldcontacts/stack/assembly/purchase budget/delivery remain pending. This is NOT fabrication acceptance. Original mainPCB951 remains42connectionerrors12nets. Complete84semantic wiring proposal generated:75pitch+5octave+4spare; noRTLwrite. Read module-plan/evidence/sensor-fourlayer-progress-current.md/json first. NEVER replay terminal apply jobs.\n').encode('utf-8')
m=json.loads(G('show',old+':project/versions/engineering-sources-20261023.json'))
for p,b in updates.items():
 k=p[len('hardware/current/'):] ;r=m['areas']['hardware']['files'].get(k,{});r.update(stored=p,bytes=len(b),sha256=sha(b),stored_sha256=sha(b),codec='raw',source='Own Sensor14Bank native4layer trial0DRC afterreopen, independentreference34segmentsFAIL; NOTFORFAB; all12retained, noRTL/order changes');m['areas']['hardware']['files'][k]=r
m['areas']['hardware'].update(updated_at=now,product_acceptance=False,validation_inherited=False);m['areas']['hardware']['current_candidate_native_changes']=changes;updates['project/versions/engineering-sources-20261023.json']=js(m)
alt=E/'sensor-fourlayer-publish-current.index';assert not alt.exists();env=dict(os.environ,GIT_INDEX_FILE=str(alt));G('read-tree',old,env=env)
for p,b in updates.items():
 oid=G('hash-object','-w','--stdin',input=b).decode().strip();G('update-index','--add','--cacheinfo','100644',oid,p,env=env)
tree=G('write-tree',env=env).decode().strip();commit=G('commit-tree',tree,'-p',old,input=b'Preserve native Sensor14Bank fourlayer zero-DRC trial and unresolved reference audit\n').decode().strip();assert G('rev-parse',commit+':fpga')==fpga and G('rev-parse',commit+':host')==host
for k,r in m['areas']['hardware']['files'].items():assert sha(G('show',commit+':'+r['stored']))==r['stored_sha256'],k
assert G('status','--porcelain=v1')==status and G('rev-parse','HEAD')==head and (sha(index.read_bytes()) if index.exists() else None)==idxsha
G('update-ref',ref,commit,old);alt.unlink();r={'at':now,'parent_commit':old,'commit':commit,'branch':branch,'updated_files':len(updates),'hardware_files_SHA_verified':len(m['areas']['hardware']['files']),'FPGA_axis_unchanged':True,'host_axis_unchanged':True,'working_HEAD_index_and_untracked_status_unchanged':True,'native_changes_only':changes,'not_for_fabrication':True,'complete_purchase_plan':False,'remote_push_completed':False};(B/'module-plan-current-publication.json').write_bytes(js(r));print(json.dumps(r,ensure_ascii=True),flush=True)
