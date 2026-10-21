"""Make a durable, verified pre-refactor snapshot outside mutable delivery paths."""
import datetime,hashlib,json,shutil,zipfile
from native_review import ROOT,PROJECT

manifest=json.loads((ROOT/'route-checkpoint-0clear-78open.json').read_text())
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert digest(PROJECT/'pcb/PCB1.epcb2')==manifest['pcb_sha256']
package=__import__('pathlib').Path(manifest['native_zip'])
assert digest(package)==manifest['native_zip_sha256']
with zipfile.ZipFile(package) as archive:
    assert archive.testzip() is None
    for name,sha in manifest['files'].items():
        candidates=[n for n in archive.namelist() if n==name or n.endswith('/'+name)]
        assert len(candidates)==1 and hashlib.sha256(archive.read(candidates[0])).hexdigest()==sha
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
target=__import__('pathlib').Path('D:/FPGA-Project/snapshots')/('before-routing-quality-refactor-78open-'+stamp)
target.mkdir(parents=True,exist_ok=False)
shutil.copy2(package,target/package.name)
for name in ['route-checkpoint-0clear-78open.json','controls-final-source-78.json','remaining-networks-78open.csv','drc-stage-controls-power-final-reopened.json','drc-stage-controls-power-final-reopened.meta.json','LATEST.md']:
    shutil.copy2(ROOT/name,target/name)
shutil.copytree(ROOT/'visual-review-78open',target/'visual-review-78open')
for name in ['2026-10-20-PCB布线质量审查.md','2026-10-20-控制显示与外围供电布线推进.md']:
    shutil.copy2(ROOT.parent.parent/'notes'/name,target/name)
(target/'README.txt').write_text('Pre-refactor baseline, 78 open objects; not released for manufacturing.\nThe native project ZIP contains all 19 project files. Restore by extracting into a NEW project directory, then open its eprj3 descriptor. Do not overlay an active project.\nPCB SHA256: '+manifest['pcb_sha256']+'\nZIP SHA256: '+manifest['native_zip_sha256']+'\n',encoding='utf-8')
checks={p.relative_to(target).as_posix():digest(p) for p in target.rglob('*') if p.is_file()}
(target/'SHA256SUMS.json').write_text(json.dumps(checks,indent=2,ensure_ascii=False),encoding='utf-8')
assert digest(target/package.name)==manifest['native_zip_sha256']
(ROOT/'quality-baseline-archive.json').write_text(json.dumps({'path':str(target),'pcb_sha256':manifest['pcb_sha256'],'zip_sha256':manifest['native_zip_sha256'],'verified_project_files':len(manifest['files'])},indent=2),encoding='utf-8')
print(target,flush=True)
