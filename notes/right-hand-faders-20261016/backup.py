"""Back up the protected product inputs before adding the isolated feature."""
from datetime import datetime
import hashlib, json, subprocess, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]
roots={'main':PROJECT,'engine':Path('C:/Users/Sakuya/.codex/worktrees/instrument-engine-safety/FPGA-Music-project'),'host':Path('C:/Users/Sakuya/.codex/worktrees/ca03/FPGA-Music-project')}
dst=ROOT/('backup-'+datetime.now().strftime('%Y%m%d-%H%M%S'));dst.mkdir(parents=True,exist_ok=False)
records={}
for label,repo in roots.items():
 files=[]
 for folder in ['src','tools/host','tools/scripts','project']:
  files.extend(p for p in (repo/folder).rglob('*') if p.is_file() and not any(s in ('__pycache__','impl','build','dist','.git') for s in p.relative_to(repo).parts))
 hashes={p.relative_to(repo).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
 archive=dst/(label+'.zip')
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for name in hashes:z.write(repo/name,name)
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  assert all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in hashes.items())
 records[label]=dict(root=str(repo),head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),files=hashes,zip=str(archive),zip_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
(dst/'manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'latest-backup.txt').write_text(str(dst),encoding='utf-8')
print(json.dumps(dict(backup=str(dst),verified=True,counts={k:len(v['files']) for k,v in records.items()})))
