from pathlib import Path
import hashlib,json,zipfile,datetime,shutil
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent
U=P/'experiments/sdram_controller_20261018';T=P/'experiments/sdram_timing_20261018';R=P/'experiments/sdram_stream_20261018'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
up=read(U/'delivery.json');timing=read(T/'delivery.json')
for root,d in ((U,up),(T,timing)):
 for rel,h in d['files'].items():assert sha(root/rel)==h,(str(root),rel)
assert not R.exists()
paths=[U/rel for rel in up['files'] if Path(rel).parts[0] in ('engine','rtl')]+[U/'common.py',U/'synthesize.py',U/'delivery.json',T/'rtl/sdram_word_controller.v',T/'delivery.json']
paths += [next((P/'docs/02-技术方案').glob(k+'*.md')) for k in ('38-','39-','49-','81-')]
B=N/('backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));B.mkdir(parents=True);items={}
with zipfile.ZipFile(B/'before.zip','w',zipfile.ZIP_DEFLATED) as z:
 for i,p in enumerate(paths):
  member='files/%04d/%s'%(i,p.name);z.write(p,member);items[str(p)]=dict(member=member,sha256=sha(p))
with zipfile.ZipFile(B/'before.zip') as z:
 assert z.testzip() is None
 for v in items.values():assert hashlib.sha256(z.read(v['member'])).hexdigest()==v['sha256']
(B/'manifest.json').write_text(json.dumps(items,indent=2),encoding='utf-8');(N/'latest-backup.txt').write_text(str(B),encoding='utf-8')
for name in ('engine','rtl'):shutil.copytree(U/name,R/name)
for name in ('evidence','tb','reference','project'):(R/name).mkdir()
for name in ('common.py','synthesize.py'):shutil.copyfile(U/name,R/name)
shutil.copyfile(T/'rtl/sdram_word_controller.v',R/'rtl/sdram_word_controller.v')
shutil.copyfile(T/'tb/sdram_timing_model.v',R/'tb/sdram_timing_model.v')
(R/'upstream.json').write_text(json.dumps(dict(controller_root=str(U),controller_delivery_sha256=sha(U/'delivery.json'),controller_files=up['files'],timing_root=str(T),timing_delivery_sha256=sha(T/'delivery.json'),timing_files=timing['files']),indent=2),encoding='utf-8')
print('PASS backed up',len(paths),'inputs; stage82 isolated; stage81 and original engine preserved')
