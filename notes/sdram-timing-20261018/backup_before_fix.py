from pathlib import Path
import hashlib,json,zipfile,datetime,shutil
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent;R=P/'experiments/sdram_timing_20261018'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
B=N/('prefixed-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));B.mkdir()
paths=[p for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.vvp'];items={}
with zipfile.ZipFile(B/'before.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in paths:
  rel=p.relative_to(R).as_posix();z.write(p,rel);items[rel]=sha(p)
with zipfile.ZipFile(B/'before.zip') as z:
 assert z.testzip() is None
 for rel,h in items.items():assert hashlib.sha256(z.read(rel)).hexdigest()==h
(B/'manifest.json').write_text(json.dumps(items,indent=2))
(N/'prefixed-backup.txt').write_text(str(B))
shutil.copyfile(R/'rtl/sdram_word_controller.v',R/'reference/sdram_word_controller_unregistered.v')
print('PASS pre-fix backup',len(items),'files')
