from pathlib import Path
import json,hashlib,datetime,zipfile,shutil
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent;U=P/'experiments/instrument_config_20261017';R=P/'experiments/config_transport_20261017'
G=Path('C:/Users/Sakuya/.codex/worktrees/ca03/FPGA-Music-project/tools')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
d=json.loads((U/'delivery.json').read_text(encoding='utf-8'))
for group in ('source_files','evidence'):
    for rel,digest in d[group].items():assert sha(U/rel)==digest,rel
assert not R.exists()
B=N/datetime.datetime.now().strftime('backup-%Y%m%d-%H%M%S');B.mkdir()
paths=list((U/'src').glob('*'))+list((U/'host').glob('*.py'))+list(U.glob('*.py'))+list(U.glob('tb_*.v'))+list((G/'host').glob('*.py'))+[G/'scripts/dsp_host.py',U/'delivery.json']
paths += [next((P/'docs/02-技术方案').glob(prefix+'*.md')) for prefix in ('38-','39-','49-','74-')]
manifest={}
with zipfile.ZipFile(B/'before.zip','w',zipfile.ZIP_DEFLATED) as z:
    for i,p in enumerate(paths):
        member='files/%04d/%s'%(i,p.name);z.write(p,member);manifest[str(p)]=dict(member=member,sha256=sha(p))
with zipfile.ZipFile(B/'before.zip') as z:
    assert z.testzip() is None
    for p,item in manifest.items():assert hashlib.sha256(z.read(item['member'])).hexdigest()==item['sha256']
(B/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');(N/'latest-backup.txt').write_text(str(B),encoding='utf-8')
for folder in ('src','rtl','host','evidence','project','gui','scripts'):(R/folder).mkdir(parents=True,exist_ok=True)
for directory in ('src','host'):
    for p in (U/directory).iterdir():
        if p.is_file():shutil.copyfile(p,R/directory/p.name)
for p in (G/'host').glob('*.py'):shutil.copyfile(p,R/'gui'/p.name)
shutil.copyfile(G/'scripts/dsp_host.py',R/'scripts/dsp_host.py')
for p in U.glob('*.py'):shutil.copyfile(p,R/p.name)
for pattern in ('*.hex','*.json','tb_*.v'):
    for p in U.glob(pattern):
        if p.name!='delivery.json':shutil.copyfile(p,R/p.name)
up=dict(root=str(U),delivery_sha256=sha(U/'delivery.json'),files={p.relative_to(U).as_posix():sha(p) for p in (U/'src').glob('*') if p.is_file()},gui_root=str(G/'host'),gui_files={p.name:sha(p) for p in (G/'host').glob('*.py')})
(R/'upstream.json').write_text(json.dumps(up,indent=2),encoding='utf-8');print('PASS protected backup/copy',len(paths))
