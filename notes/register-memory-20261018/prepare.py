from pathlib import Path
import json, hashlib, zipfile, datetime, shutil
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent
U=P/'experiments/fx_memory_20261017';R=P/'experiments/register_memory_20261018'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
d=json.loads((U/'delivery.json').read_text(encoding='utf-8'))
for group in ('source_files','evidence','inherited_76_artifacts'):
 for rel,h in d[group].items():assert sha(U/rel)==h,(group,rel)
assert not R.exists(),'Never replace a previous experiment'
B=N/('backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));B.mkdir(parents=True)
paths=[U/rel for rel in d['source_files']]+[U/'delivery.json']+[next((P/'docs/02-技术方案').glob(k+'*.md')) for k in ('38-','39-','49-','77-')]
manifest={}
with zipfile.ZipFile(B/'before.zip','w',zipfile.ZIP_DEFLATED) as z:
 for i,p in enumerate(paths):
  member='files/%04d/%s'%(i,p.name);z.write(p,member);manifest[str(p)]=dict(member=member,sha256=sha(p))
with zipfile.ZipFile(B/'before.zip') as z:
 assert z.testzip() is None
 for item in manifest.values():assert hashlib.sha256(z.read(item['member'])).hexdigest()==item['sha256']
(B/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(N/'latest-backup.txt').write_text(str(B),encoding='utf-8')
for rel in d['source_files']:
 target=R/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(U/rel,target)
for rel in d['inherited_76_artifacts']:
 target=R/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(U/rel,target)
(R/'evidence').mkdir(exist_ok=True)
for name in ('reg_bank','tdm_top','tdm_top_owned'):shutil.copyfile(U/('src/'+name+'.v'),R/('reference/'+name+'_original.v'))
(R/'upstream.json').write_text(json.dumps(dict(root=str(U),delivery_sha256=sha(U/'delivery.json'),source_files=d['source_files'],inherited_76_artifacts=d['inherited_76_artifacts']),indent=2),encoding='utf-8')
print('PASS verified pre-edit backup',len(paths),'inputs;',R)
