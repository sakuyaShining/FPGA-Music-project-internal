from pathlib import Path
import datetime,hashlib,json,shutil,zipfile
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent;U=P/'experiments/board_audio_20261017';R=P/'experiments/instrument_config_20261017'
G=Path('C:/Users/Sakuya/.codex/worktrees/ca03/FPGA-Music-project/tools/host')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
d=json.loads((U/'delivery.json').read_text(encoding='utf-8'))
for group in ('source_files','evidence'):
    for rel,digest in d[group].items():assert sha(U/rel)==digest,rel
assert not R.exists() or {p.relative_to(R).as_posix() for p in R.rglob('*') if p.is_file()}<={'common.py'},'preserve existing experiment'
B=N/datetime.datetime.now().strftime('backup-%Y%m%d-%H%M%S');B.mkdir()
paths=list((U/'src').glob('*'))+list((U/'rtl').glob('*.v'))+list(U.glob('*.py'))+list(U.glob('tb_*.v'))+[U/'delivery.json',P/'experiments/resource_safety_20261016/delivery.json']
paths += [next((P/'docs/02-技术方案').glob(prefix+'*.md')) for prefix in ('38-','39-','49-','73-')]
paths += [G/name for name in ('instrument_config.py','device_config.py','test_instrument_config.py')]
manifest={}
with zipfile.ZipFile(B/'before.zip','w',zipfile.ZIP_DEFLATED) as z:
    for i,p in enumerate(paths):
        key='files/%04d/%s'%(i,p.name);z.write(p,key);manifest[str(p)]=dict(member=key,sha256=sha(p))
with zipfile.ZipFile(B/'before.zip') as z:
    assert z.testzip() is None
    for path,item in manifest.items():assert hashlib.sha256(z.read(item['member'])).hexdigest()==item['sha256']
(B/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');(N/'latest-backup.txt').write_text(str(B),encoding='utf-8')
for directory in ('src','rtl','host','evidence','project'): (R/directory).mkdir(parents=True,exist_ok=True)
for p in (U/'src').glob('*'):
    if p.is_file():shutil.copyfile(p,R/'src'/p.name)
shutil.copyfile(G/'instrument_config.py',R/'host/instrument_config.py')
shutil.copyfile(U/'check_engine_compat.py',R/'check_engine_compat.py')
up=dict(root=str(U),delivery_sha256=sha(U/'delivery.json'),files={p.relative_to(U).as_posix():sha(p) for p in (U/'src').glob('*') if p.is_file()},gui_source=str(G/'instrument_config.py'),gui_sha256=sha(G/'instrument_config.py'))
(R/'upstream.json').write_text(json.dumps(up,indent=2),encoding='utf-8')
print('PASS backup before implementation: %d files; sources copied into isolated experiment'%len(paths))
