"""Backup protected sources and copy a hash-checked engine for isolated edits."""
import hashlib,json,subprocess,zipfile,shutil
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parent;P=ROOT.parents[1]
ENGINE=Path('C:/Users/Sakuya/.codex/worktrees/instrument-engine-safety/FPGA-Music-project')
FEATURE=P/'experiments/right_hand_audio_20261016'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
version=json.loads((ENGINE/'project/versions/engine-safety-20261014-01.json').read_text(encoding='utf-8'))
assert all(sha(ENGINE/name)==value for name,value in version['files'].items())
backup=ROOT/('backup-'+datetime.now().strftime('%Y%m%d-%H%M%S'));backup.mkdir(parents=True,exist_ok=False)
records={}
for label,repo,folders in [('main',P,['src','tools/host','tools/scripts','project']),('engine',ENGINE,['src','tools/host','tools/scripts','project']),('faders',P/'experiments/right_hand_faders_20261016',['.'])]:
 files=[]
 for folder in folders:
  files.extend(p for p in (repo/folder).rglob('*') if p.is_file() and not any(s in ('__pycache__','impl','build','dist','synthesis') for s in p.relative_to(repo).parts))
 hashes={p.relative_to(repo).as_posix():sha(p) for p in files}
 zpath=backup/(label+'.zip')
 with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED) as z:
  for n in hashes:z.write(repo/n,n)
 with zipfile.ZipFile(zpath) as z:
  assert z.testzip() is None
  assert all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in hashes.items())
 records[label]=dict(root=str(repo),files=hashes,archive=str(zpath),archive_sha256=sha(zpath))
(backup/'manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'latest-backup.txt').write_text(str(backup),encoding='utf-8')
dst=FEATURE/'engine';dst.mkdir(parents=True,exist_ok=True)
files=list((ENGINE/'src/rtl').glob('*.v'))+list((ENGINE/'src/gowin/tdm_synth').glob('*.hex'))
for p in files:shutil.copyfile(p,dst/p.name)
(FEATURE/'source-engine.json').write_text(json.dumps(dict(root=str(ENGINE),head=subprocess.check_output(['git','-C',str(ENGINE),'rev-parse','HEAD'],text=True).strip(),manifest='project/versions/engine-safety-20261014-01.json',files={p.relative_to(ENGINE).as_posix():sha(p) for p in files}),indent=2),encoding='utf-8')
print(json.dumps(dict(backup=str(backup),verified=True,protected_counts={k:len(v['files']) for k,v in records.items()},copied_engine_files=len(files))))
