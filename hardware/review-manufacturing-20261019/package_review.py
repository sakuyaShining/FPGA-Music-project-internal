"""Keep large review exports on D:, retaining the original native project on C:."""
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path
from native_review import ROOT, PROJECT

DEST=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261019')
DEST.mkdir(parents=True,exist_ok=True)
for name in ['dual-screen-review.pdf','dual-screen-review.zip']:
    shutil.copy2(PROJECT/'review-exports'/name,DEST/name)
with zipfile.ZipFile(DEST/'dual-screen-review.zip') as z:
    assert z.testzip() is None
    print('PNG export entries:',z.namelist())
    pngdir=DEST/'schematic-png';pngdir.mkdir(exist_ok=True)
    pages=json.loads((ROOT/'design.json').read_text(encoding='utf-8'))['pages']
    wanted={p+'.png' for p in pages}
    for p in pngdir.glob('*.png'):
        if p.name not in wanted:
            historical=DEST/'historical-png';historical.mkdir(exist_ok=True)
            shutil.move(str(p),str(historical/p.name))
    for n in z.namelist():
        if n.lower().endswith('.png'):
            number=int(re.search(r'SCH_Schematic1_(\d+)-',n).group(1))
            (pngdir/(pages[number-1]+'.png')).write_bytes(z.read(n))
with zipfile.ZipFile(DEST/'native-project-REVIEW-ONLY.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in PROJECT.rglob('*'):
        if p.is_file() and 'exports' not in p.as_posix():z.write(p,p.relative_to(PROJECT))
with zipfile.ZipFile(DEST/'native-project-REVIEW-ONLY.zip') as z:assert z.testzip() is None
for p in ROOT.iterdir():
    if p.is_file() and p.suffix in ['.csv','.tsv','.net','.json','.md']:
        shutil.copy2(p,DEST/p.name)
manifest={p.relative_to(DEST).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in DEST.rglob('*') if p.is_file() and p.name!='SHA256.json'}
(DEST/'SHA256.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
(ROOT/'evidence/package.json').write_text(json.dumps({'path':str(DEST),'files':len(manifest),'bytes':sum(p.stat().st_size for p in DEST.rglob('*') if p.is_file()),'fabrication_release':False},indent=2)+'\n',encoding='utf-8')
print('package',DEST)
