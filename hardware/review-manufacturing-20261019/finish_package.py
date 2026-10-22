import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from native_review import ROOT, call

DEST=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261019')
qa={'pdf_pages':12,'png_pages':12,'visual_inspection':'12-page rendered overview plus detailed checks of core, DAC and representative scan sheet; no observed clipping/label overlap',
    'native_connectivity':'827 connected + 137 NC, zero mismatch; 202 native BOM refs / exact C-codes / footprint names match',
    'fabrication_release':False}
(DEST/'export-inspection.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(ROOT/'evidence/export-inspection.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
session=json.loads((ROOT/'evidence/open.json').read_text(encoding='utf-8'))['value']['sessionId']
print('close native session',call('session-closed',['session','close','--session',session,'--destroy']))
with zipfile.ZipFile(DEST/'review-evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in (ROOT/'evidence').rglob('*'):
        if p.is_file():z.write(p,p.relative_to(ROOT))
for name in ['README.md','采购与制造询价稿.md','共享总线与上电审查.md','procurement-native-candidate.csv','release-open-items.csv','harness-contract.csv','connectivity-audit.json']:
    shutil.copy2(ROOT/name,DEST/name)
manifest={p.relative_to(DEST).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in DEST.rglob('*') if p.is_file() and p.name!='SHA256.json'}
(DEST/'SHA256.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
assert all(hashlib.sha256((DEST/p).read_bytes()).hexdigest()==h for p,h in manifest.items())
print('hashes verified',len(manifest),'files')
