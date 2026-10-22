from pathlib import Path
import hashlib,json,zipfile,datetime,shutil
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent
U=P/'experiments/sdram_stream_20261018';B83=P/'experiments/sdram_stream_board_20261018';R=P/'experiments/pitch_memory_20261018'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text(encoding='utf-8'))
u=read(U/'delivery.json');b=read(B83/'delivery.json')
for root,d in ((U,u),(B83,b)):
 for rel,h in d['files'].items():assert sha(root/rel)==h,(str(root),rel)
assert not R.exists()
paths=[U/rel for rel in u['files'] if Path(rel).parts[0] in ('engine','rtl')]+[U/'delivery.json',B83/'delivery.json',U/'synthesize.py']
paths += [next((P/'docs/02-技术方案').glob(k+'*.md')) for k in ('38-','39-','49-','83-')]
Z=N/('backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));Z.mkdir(parents=True);items={}
with zipfile.ZipFile(Z/'before.zip','w',zipfile.ZIP_DEFLATED) as z:
 for i,p in enumerate(paths):
  member='files/%04d/%s'%(i,p.name);z.write(p,member);items[str(p)]=dict(member=member,sha256=sha(p))
with zipfile.ZipFile(Z/'before.zip') as z:
 assert z.testzip() is None
 for v in items.values():assert hashlib.sha256(z.read(v['member'])).hexdigest()==v['sha256']
(Z/'manifest.json').write_text(json.dumps(items,indent=2));(N/'latest-backup.txt').write_text(str(Z))
for name in ('engine','rtl'):shutil.copytree(U/name,R/name)
for name in ('evidence','reference','project','tb'):(R/name).mkdir()
shutil.copyfile(U/'engine/src/pitch_mod.v',R/'reference/pitch_mod.v')
shutil.copyfile(U/'synthesize.py',R/'synthesize.py')
s=(R/'synthesize.py').read_text().replace("R/'reference/sdram_stream_probe.v' if p.name=='sdram_stream_probe.v'", "R/'reference/pitch_mod.v' if p.name=='pitch_mod.v'")
(R/'synthesize.py').write_text(s)
C=P/'experiments/register_memory_20261018'
s=(C/'common.py').read_text().replace("R/'src'","R/'engine/src'").replace("list((R/'rtl').glob('*.v'))","list((R/'engine/rtl').glob('*.v'))+list((R/'rtl').glob('*.v'))")
(R/'common.py').write_text(s)
for name in ('check_engine_compat.py','check_enabled_compat.py','check_phase_wrap.py','check_music.py','check_envelope.py'):
 s=(C/name).read_text().replace("R/'src'","R/'engine/src'");(R/name).write_text(s)
for p in C.glob('tb*.v'):shutil.copyfile(p,R/p.name)
for p in C.glob('*.hex'):shutil.copyfile(p,R/p.name)
(R/'upstream.json').write_text(json.dumps(dict(root=str(U),delivery_sha256=sha(U/'delivery.json'),files=u['files'],board_root=str(B83),board_delivery_sha256=sha(B83/'delivery.json'),board_files=b['files']),indent=2))
print('PASS backup',len(paths),'inputs; isolated pitch storage experiment')
