"""Deliver exact checkpoints; preserve r5 active and r3 procurement pointers."""
import json,hashlib,shutil,zipfile
from pathlib import Path
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;D=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text(encoding='utf-8'));save=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
active=read(ROOT/'ACTIVE-ROUTING-CANDIDATE.json');assert 'Stackup-20261021-r5' in active['project'] and active['pcb_sha256']=='d21fb5545e51bb27ff5a2e86405c7ea50c80e5664c186543843ede1704eb3fcb'
state=read(ROOT/'CURRENT-STATE.json');assert state['unconnected_errors']==74
cases=[('r3',read(ROOT/state['checkpoint']),Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019')),('r4',read(ROOT/'joint-routing-20261021-r4/native-candidate-checkpoint.json'),None),('r5',active,None),('r6-rejected',read(BASE/'native-candidate-checkpoint.json'),None)]
verified={}
for label,cp,project in cases:
 project=project or Path(cp['project']);assert len(cp['files'])==19
 assert all(sha(project/rel)==h for rel,h in cp['files'].items()),label
 archive=Path(cp['native_zip']);assert sha(archive)==cp['native_zip_sha256']
 with zipfile.ZipFile(archive) as z:assert z.testzip() is None and all(hashlib.sha256(z.read(rel)).hexdigest()==h for rel,h in cp['files'].items()),label
 verified[label]=dict(files=19,pcb_sha256=cp['pcb_sha256'],archive_sha256=cp['native_zip_sha256'],source_matches_archive=True)
for p in [*(ROOT/'stackup-validation-20261021-r5').rglob('*.py'),*BASE.rglob('*.py'),ROOT/'four_layer_geometry.py',ROOT/'native_plane_geometry.py']:
 if '__pycache__' not in p.parts:compile(p.read_text(encoding='utf-8'),str(p),'exec')
packages={}
for folder in [ROOT/'stackup-validation-20261021-r5',BASE]:
 files={}
 for p in folder.rglob('*'):
  if not p.is_file() or '__pycache__' in p.parts or p.name in ['delivery-manifest.json','round-final.json']:continue
  rel=p.relative_to(folder).as_posix();target=D/folder.name/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target);assert sha(p)==sha(target);files[rel]=sha(p)
 manifest=dict(utc=datetime.now(timezone.utc).isoformat(),files=files,manufacturing_release=False,active_candidate='r5',failed_scratch_files_are_not_manufacturing_sources=True)
 if folder==BASE:manifest['diagnostic_archive']=dict(path=cases[-1][1]['native_zip'],sha256=cases[-1][1]['native_zip_sha256'],promoted_to_active=False)
 save(folder/'delivery-manifest.json',manifest);shutil.copy2(folder/'delivery-manifest.json',D/folder.name/'delivery-manifest.json');packages[folder.name]=dict(copied=len(files),indexed=len(files))
rootnames=['CURRENT-STATE.json','ACTIVE-ROUTING-CANDIDATE.json','LATEST.md','AUTONOMOUS-CURRENT.md','release-open-items.csv','README-v2.md','执行计划-20261020.md','采购与制造询价稿.md','four_layer_geometry.py','native_plane_geometry.py']
for name in rootnames:shutil.copy2(ROOT/name,D/name);assert sha(ROOT/name)==sha(D/name)
for name in ['keep-awake-state.json','keep-awake-restart-failure.json']:
 target=D/'task-runtime-20261021'/name;target.parent.mkdir(exist_ok=True);shutil.copy2(ROOT/'task-runtime-20261021'/name,target)
root_hashes={name:sha(D/name) for name in rootnames}
for name in ['CURRENT-PURCHASE-PREP.json','CURRENT-ASSEMBLY-PREP.json']:
 p=D/name;v=read(p);v['updated_utc']=datetime.now(timezone.utc).isoformat();v['delivered_packages'].update(packages);v['root_file_sha256'].update(root_hashes);v['rejected_routing_comparison']={'package':BASE.name,'pcb_sha256':cases[-1][1]['pcb_sha256'],'native_drc':[0,0,62],'active':False,'reason':'nearest reference plane gaps after actual native copper rebuild'};v['temporary_keep_awake_active']=False;v['computer_wake_guaranteed']=False;save(p,v)
p=D/'CURRENT-ROUTING-REVIEW.md';s=p.read_text(encoding='utf-8');s=s.replace('r6音频试布只有离线候选，尚未写入PCB。','r6音频已在独立副本通过完整原生DRC，但最近参考地覆盖不足，已否决；未写入当前R5。');p.write_text(s,encoding='utf-8')
workbook=D/'硬件采购准备-r1.xlsx';assert sha(workbook)=='59938d7887492c61e1b0c32ae14069d3dd1bbcf2c4da1ded779b480d0a9aee5b'
result=dict(utc=datetime.now(timezone.utc).isoformat(),active_candidate='r5',native_sources=verified,packages=packages,root_file_sha256=root_hashes,python_compile_pass=True,workbook_unchanged=True,r6_rejected_for_reference_geometry=True,reference_plot_visually_checked=True,native_drc_not_repeated_without_source_change=True,goal_status='active',automation_id='automation-2',temporary_keep_awake_active=False,manufacturing_release=False)
save(BASE/'round-final.json',result);shutil.copy2(BASE/'round-final.json',D/BASE.name/'round-final.json')
print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
