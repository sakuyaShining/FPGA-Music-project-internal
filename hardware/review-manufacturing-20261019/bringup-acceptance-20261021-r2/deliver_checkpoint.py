"""Copy owned deliverables without traversing bundled dependency junctions."""
import hashlib
import json
import os
import shutil
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
if (ROOT/'CURRENT-STATE.json').exists():
    current=json.loads((ROOT/'CURRENT-STATE.json').read_text(encoding='utf-8'))
    if current['pcb_sha256']!='be576cabac058fc0754fbc87a07565e69531e59c7d249a6f6d267c5f93c5fc3e':
        raise RuntimeError('Historical r2 delivery helper: use joint-routing-20261021-r3/deliver_current.py for the current PCB')
DEST=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
save=lambda p,o:p.write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8')
folders=['hardware-contract-20261021-r1','purchase-preparation-20261021-r1',
         'connector-qualification-20261021-r2','bringup-acceptance-20261021-r2']
workbook=ROOT/'purchase-preparation-20261021-r1/outputs/01a158ca-15fe-7ea2-8a60-ba5ae6a61281/硬件采购准备-r1.xlsx'
old=DEST/workbook.name
old_archive=None
previous_pointer=DEST/'CURRENT-ASSEMBLY-PREP.json'
if previous_pointer.exists():
    old_archive=json.loads(previous_pointer.read_text(encoding='utf-8')).get('previous_workbook_archive')
if old.exists() and sha(old)!=sha(workbook):
    archive=DEST/'purchase-revisions'/('before-r2-'+sha(old)[:12])
    archive.mkdir(parents=True,exist_ok=True)
    target=archive/old.name
    if target.exists():assert sha(target)==sha(old)
    else:shutil.copy2(old,target)
    old_archive={'path':str(target),'sha256':sha(target)}
results={}
for name in folders:
    src=ROOT/name;dst=DEST/name;count=0
    for current,dirs,files in os.walk(src,followlinks=False):
        dirs[:]=[d for d in dirs if d not in ['node_modules','__pycache__','runs'] and not (Path(current)/d).is_symlink()]
        for f in files:
            if f=='delivery-sha256.json' or f.endswith('.pyc'):continue
            a=Path(current)/f;b=dst/a.relative_to(src);b.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(a,b);assert sha(a)==sha(b);count+=1
    # Index all present package files, including later-added permission evidence.
    index={}
    for current,dirs,files in os.walk(dst,followlinks=False):
        dirs[:]=[d for d in dirs if d not in ['node_modules','__pycache__','runs']]
        for f in files:
            p=Path(current)/f
            if f!='delivery-sha256.json' and not f.endswith('.pyc'):index[p.relative_to(dst).as_posix()]=sha(p)
    save(dst/'delivery-sha256.json',index)
    results[name]={'source_files_copied_and_verified':count,'delivery_files_indexed':len(index)}
for name in ['AUTONOMOUS-CURRENT.md','LATEST.md','release-open-items.csv','harness-contract.csv',
             '装配与首次上电-v2.md','装配与分阶段验收-r2.md']:
    shutil.copy2(ROOT/name,DEST/name);assert sha(ROOT/name)==sha(DEST/name)
shutil.copy2(workbook,old);assert sha(workbook)==sha(old)
checkpoint=dict(utc=datetime.now(timezone.utc).isoformat(),phase='connector-and-acceptance-r2',
    workbook=str(old),workbook_sha256=sha(old),previous_workbook_archive=old_archive,
    assembly_counts={'per_board_total':230,'factory_smt':217,'through_hole':13},
    nominal_connector_geometries_verified=7,static_testpoints_verified=21,
    static_harness_pins_verified=165,pending_bench_stages=22,pending_power_voltage_slots=32,
    copied_packages=results,goal_state_observed_at_turn_start='blocked',
    goal_resume_not_changed_by_agent=True,physical_tests_executed=False,
    pcb_sha256='be576cabac058fc0754fbc87a07565e69531e59c7d249a6f6d267c5f93c5fc3e',
    last_native_drc_unconnected=78,new_native_drc_executed=False,
    native_permission='Previous external-interaction permission refusal; no new retry or recovery evidence this turn',
    automation_id='automation-2',manufacturing_release=False,purchases_made=False,
    open_items_sha256=sha(ROOT/'release-open-items.csv'),
    guide_sha256=sha(ROOT/'装配与分阶段验收-r2.md'))
save(ROOT/'bringup-acceptance-20261021-r2/checkpoint.json',checkpoint)
save(DEST/'bringup-acceptance-20261021-r2/checkpoint.json',checkpoint)
save(DEST/'CURRENT-ASSEMBLY-PREP.json',checkpoint)
save(DEST/'CURRENT-PURCHASE-PREP.json',dict(checkpoint,
    counts={'board_part_types':36,'placed_per_board':230,'factory_smt_per_board':217,
            'manual_through_hole_per_board':13,'external_scope_rows':32}))
package=DEST/'bringup-acceptance-20261021-r2'
save(package/'delivery-sha256.json',{p.relative_to(package).as_posix():sha(p) for p in package.iterdir() if p.is_file() and p.name!='delivery-sha256.json'})
print(json.dumps(checkpoint,ensure_ascii=False,indent=2))
