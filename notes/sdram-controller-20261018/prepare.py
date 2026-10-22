# -*- coding: utf-8 -*-
from pathlib import Path
import json,hashlib,zipfile,datetime,shutil
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent
U=P/'experiments/pcm_buffer_20261018';R=P/'experiments/sdram_controller_20261018'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
d=json.loads((U/'delivery.json').read_text(encoding='utf-8'))
for rel,h in d['files'].items():assert sha(U/rel)==h,rel
assert not R.exists()
B=N/('backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));B.mkdir(parents=True)
paths=[U/rel for rel in d['files'] if Path(rel).parts[0] not in ('evidence','synthesis_reference','synthesis_buffered','synthesis_reference_retry')]+[U/'delivery.json']+[next((P/'docs/02-技术方案').glob(k+'*.md')) for k in ('38-','39-','49-','79-')]
manifest={}
with zipfile.ZipFile(B/'before.zip','w',zipfile.ZIP_DEFLATED) as z:
 for i,p in enumerate(paths):
  member='files/%04d/%s'%(i,p.name);z.write(p,member);manifest[str(p)]=dict(member=member,sha256=sha(p))
with zipfile.ZipFile(B/'before.zip') as z:
 assert z.testzip() is None
 for v in manifest.values():assert hashlib.sha256(z.read(v['member'])).hexdigest()==v['sha256']
(B/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(N/'latest-backup.txt').write_text(str(B),encoding='utf-8')
for rel,h in d['files'].items():
 if Path(rel).parts[0] in ('engine','rtl'):
  target=R/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(U/rel,target)
for name in ('reference','evidence','project','tb'):(R/name).mkdir(parents=True,exist_ok=True)
for name in ('common.py','synthesize.py'):shutil.copyfile(U/name,R/name)
(R/'upstream.json').write_text(json.dumps(dict(root=str(U),delivery_sha256=sha(U/'delivery.json'),files=d['files']),indent=2),encoding='utf-8')
print('PASS verified pre-edit backup',len(paths),'inputs; stage79 source copied unchanged')
