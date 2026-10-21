"""Sync r7 package and current documents, verify protected snapshots and hashes."""
import json,hashlib,shutil,zipfile
from pathlib import Path
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;D=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text(encoding='utf-8'));save=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
cp=read(ROOT/'ACTIVE-ROUTING-CANDIDATE.json');assert cp['pcb_sha256']=='2cec51920011e0e8512956064d1c3b396bc4b98b98a94989432e883b30029eae'
protected={}
cases=[('r3',read(ROOT/'route-checkpoint-0clear-74open-local-power-bus-r3-20261021.json'),Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019')),('r4',read(ROOT/'joint-routing-20261021-r4/native-candidate-checkpoint.json'),None),('r5',read(ROOT/'stackup-validation-20261021-r5/native-candidate-checkpoint.json'),None),('r6-rejected',read(ROOT/'audio-routing-20261021-r6/native-candidate-checkpoint.json'),None),('r7',cp,None)]
for label,c,project in cases:
 project=project or Path(c['project']);assert len(c['files'])==19 and all(sha(project/rel)==v for rel,v in c['files'].items());archive=Path(c['native_zip']);assert sha(archive)==c['native_zip_sha256']
 with zipfile.ZipFile(archive) as z:assert z.testzip() is None and all(hashlib.sha256(z.read(rel)).hexdigest()==h for rel,h in c['files'].items())
 protected[label]=dict(files=19,pcb_sha256=c['pcb_sha256'],archive_sha256=c['native_zip_sha256'],source_matches_archive=True)
for p in BASE.glob('*.py'):compile(p.read_text(encoding='utf-8'),str(p),'exec')
files={}
for p in BASE.rglob('*'):
 if not p.is_file() or '__pycache__' in p.parts or p.name in ['delivery-manifest.json','round-final.json']:continue
 rel=p.relative_to(BASE).as_posix();target=D/BASE.name/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target);assert sha(p)==sha(target);files[rel]=sha(p)
manifest=dict(utc=datetime.now(timezone.utc).isoformat(),files=files,source_pcb_sha256=cp['pcb_sha256'],native_archive_sha256=cp['native_zip_sha256'],first_and_second_positions_are_failed_history=True,manufacturing_release=False);save(BASE/'delivery-manifest.json',manifest);shutil.copy2(BASE/'delivery-manifest.json',D/BASE.name/'delivery-manifest.json')
roots=['CURRENT-STATE.json','ACTIVE-ROUTING-CANDIDATE.json','LATEST.md','AUTONOMOUS-CURRENT.md','release-open-items.csv','README-v2.md','执行计划-20261020.md','采购与制造询价稿.md','装配与分阶段验收-r2.md']
for name in roots:shutil.copy2(ROOT/name,D/name);assert sha(ROOT/name)==sha(D/name)
hashes={name:sha(D/name) for name in roots}
for name in ['CURRENT-PURCHASE-PREP.json','CURRENT-ASSEMBLY-PREP.json']:
 p=D/name;v=read(p);v['updated_utc']=datetime.now(timezone.utc).isoformat();v['active_routing_alternative']=dict(pointer='ACTIVE-ROUTING-CANDIDATE.json',pcb_sha256=cp['pcb_sha256'],logical_copper_layers=4,unconnected_errors=62,physical_stack_metadata_complete=True,physical_stack_structure_verified=True,factory_stack_approval=False,vias=520,components_moved=['C35'],historical_CPL_C35_stale=True,manufacturing_release=False);v['root_file_sha256'].update(hashes);v['delivered_packages'][BASE.name]=dict(copied=len(files),indexed=len(files));save(p,v)
(D/'CURRENT-ROUTING-REVIEW.md').write_text('''# 当前PCB复核 · R7

当前工作源 ACTIVE-ROUTING-CANDIDATE.json → local-layout-20261021-r7。完整原生DRC **0间距/0物理/62未连接（12网）**，230件、520孔。只移动C35及其去耦铜，VCC支路10.11→2.38mm，新增接地孔接入两个内层；音频铜及参考地覆盖不变。图和证据见r7 README/final-layout-review.json。

**仍不能制造。** 12网、音频回流与27个信号孔、传感寄生、工厂工艺、机械与大屏版本仍开放。R6音频减孔方案因真实参考地覆盖不足被否决，未作为当前设计。R3采购基线和R4/R5/R6源哈希保留。R4/R6旧CLI后台会话已正常关闭，不可直接重用历史会话。

C35改位使历史CPL该行过时；对照JSON不是原生CPL导出。217SMT+13通孔、板件型号及数量不变，采购工作簿仍记录保留R3基线。最终制造资料必须从完成布线后的同版工程导出核对。
''',encoding='utf-8')
assert sha(D/'硬件采购准备-r1.xlsx')=='59938d7887492c61e1b0c32ae14069d3dd1bbcf2c4da1ded779b480d0a9aee5b'
for name in ['CURRENT-PURCHASE-PREP.json','CURRENT-ASSEMBLY-PREP.json']:
 v=read(D/name);assert all(sha(D/rel)==h for rel,h in v['root_file_sha256'].items())
result=dict(utc=datetime.now(timezone.utc).isoformat(),current_candidate='r7',native_sources=protected,files_copied=len(files),delivery_file_hashes_verified=True,python_sources_compile=True,layout_comparison_visually_reviewed=True,native_drc=[0,0,62],legacy_CPL_C35_stale=True,workbook_unchanged=True,old_r4_r6_headless_cli_sessions_closed_normally=True,goal_status='active',automation_id='automation-2',manufacturing_release=False)
save(BASE/'round-final.json',result);shutil.copy2(BASE/'round-final.json',D/BASE.name/'round-final.json');print(json.dumps(result,ensure_ascii=True,indent=2),flush=True)
