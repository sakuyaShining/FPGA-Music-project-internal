"""Deliver the current verified checkpoint; exclude dependency junctions/runs."""
import hashlib,json,os,shutil,sys
from datetime import datetime,timezone
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,str(ROOT))
from current_state import current_checkpoint
DEST=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
save=lambda p,o:p.write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8')
cp_path,cp,capture=current_checkpoint(ROOT)
PROJECT=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019')
assert all(sha(PROJECT/p)==h for p,h in cp['files'].items())
assert sha(Path(cp['native_zip']))==cp['native_zip_sha256']
book=ROOT/'purchase-preparation-20261021-r1/outputs/01a158ca-15fe-7ea2-8a60-ba5ae6a61281/硬件采购准备-r1.xlsx'
assert read(ROOT/'purchase-preparation-20261021-r1/final-verification.json')['current_pcb_sha256']==cp['pcb_sha256']
assert read(ROOT/'purchase-preparation-20261021-r1/placement-reconciliation.json')['current_pcb_sha256']==cp['pcb_sha256']
assert read(ROOT/'bringup-acceptance-20261021-r2/static-contract-results.json')['native_files_unchanged']['pcb/PCB1.epcb2']
old_book=DEST/book.name;old_archive=None
if old_book.exists() and sha(old_book)!=sha(book):
    folder=DEST/'purchase-revisions'/('before-r3-'+sha(old_book)[:12]);folder.mkdir(parents=True,exist_ok=True)
    archived=folder/old_book.name
    if archived.exists():assert sha(archived)==sha(old_book)
    else:shutil.copy2(old_book,archived)
    old_archive=dict(path=str(archived),sha256=sha(archived))
packages=['hardware-contract-20261021-r1','purchase-preparation-20261021-r1',
    'connector-qualification-20261021-r2','bringup-acceptance-20261021-r2',
    'joint-routing-20261021-r3','visual-local-power-bus-r3-20261021']
copied={}
for name in packages:
    src=ROOT/name;dest=DEST/name;count=0
    for current,dirs,files in os.walk(src,followlinks=False):
        dirs[:]=[d for d in dirs if d not in ['node_modules','__pycache__','runs'] and not (Path(current)/d).is_symlink()]
        for f in files:
            if f=='delivery-sha256.json' or f.endswith('.pyc'):continue
            a=Path(current)/f;b=dest/a.relative_to(src);b.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(a,b);assert sha(a)==sha(b);count+=1
    index={}
    for current,dirs,files in os.walk(dest,followlinks=False):
        dirs[:]=[d for d in dirs if d not in ['node_modules','__pycache__','runs']]
        for f in files:
            b=Path(current)/f
            if f!='delivery-sha256.json' and not f.endswith('.pyc'):index[b.relative_to(dest).as_posix()]=sha(b)
    save(dest/'delivery-sha256.json',index)
    copied[name]=dict(copied=count,indexed=len(index))
root_names=['CURRENT-STATE.json','LATEST.md','AUTONOMOUS-CURRENT.md','release-open-items.csv',
    'harness-contract.csv','remaining-networks-74open-r3.csv','装配与分阶段验收-r2.md',
    '装配与首次上电-v2.md',cp_path.name,'drc-stage-local-power-bus-r3.json','drc-stage-local-power-bus-r3.meta.json']
root_hashes={}
for name in root_names:
    shutil.copy2(ROOT/name,DEST/name);assert sha(ROOT/name)==sha(DEST/name);root_hashes[name]=sha(DEST/name)
shutil.copy2(book,old_book);assert sha(book)==sha(old_book)
summary=dict(updated_utc=datetime.now(timezone.utc).isoformat(),phase='local-power-bus-r3',
    pcb_sha256=cp['pcb_sha256'],current_checkpoint=cp_path.name,current_checkpoint_sha256=sha(cp_path),
    native_zip=cp['native_zip'],native_zip_sha256=cp['native_zip_sha256'],
    workbook=str(old_book),workbook_sha256=sha(old_book),previous_workbook_archive=old_archive,
    counts={'board_part_types':36,'placed_per_board':230,'factory_smt_per_board':217,
        'manual_through_hole_per_board':13,'external_scope_rows':32},
    native_drc={'clearance':0,'physical':0,'connections':74,'pending_nets':16},
    current_api_lines=3262,current_native_microtracks=28,current_vias=533,
    purchasing_and_acceptance_use_current_state_pointer=True,physical_tests_executed=False,
    goal_status_observed='active',automation_id='automation-2',manufacturing_release=False,purchases_made=False,
    delivered_packages=copied,root_file_sha256=root_hashes)
save(OUT/'delivery-checkpoint.json',summary)
save(DEST/'joint-routing-20261021-r3/delivery-checkpoint.json',summary)
save(DEST/'CURRENT-PURCHASE-PREP.json',summary);save(DEST/'CURRENT-ASSEMBLY-PREP.json',summary)
package=DEST/'joint-routing-20261021-r3'
index={}
for current,dirs,files in os.walk(package):
    dirs[:]=[d for d in dirs if d!='__pycache__']
    for f in files:
        p=Path(current)/f
        if f!='delivery-sha256.json' and not f.endswith('.pyc'):index[p.relative_to(package).as_posix()]=sha(p)
save(package/'delivery-sha256.json',index)
assert all(sha(package/p)==h for p,h in index.items())
print(json.dumps({k:summary[k] for k in ['phase','pcb_sha256','native_drc','workbook_sha256','delivered_packages','manufacturing_release']},indent=2))
