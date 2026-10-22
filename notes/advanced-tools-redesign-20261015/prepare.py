import hashlib
import json
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path('C:/Users/Sakuya/.codex/worktrees/ca03/FPGA-Music-project')
OUT = Path(__file__).parent
BACKUP = OUT / ('backup-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
BACKUP.mkdir(parents=True, exist_ok=False)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

files = []
for folder in ('tools/host', 'tools/scripts', 'src', 'project', 'docs/05-上位机'):
    for path in (ROOT / folder).rglob('*'):
        if path.is_file() and not any(p in ('__pycache__', 'build', 'dist', 'impl') for p in path.relative_to(ROOT).parts):
            files.append(path)
hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in files}
archive = BACKUP / 'before.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
    for path in files:
        z.write(path, path.relative_to(ROOT).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert all(hashlib.sha256(z.read(name)).hexdigest() == digest for name, digest in hashes.items())
identity = json.loads((ROOT / 'tools/host/host_version.json').read_text(encoding='utf-8'))
drift = {p: {'expected': h, 'actual': sha(ROOT / p) if (ROOT / p).exists() else None}
         for p, h in identity['inputs'].items() if not (ROOT / p).exists() or sha(ROOT / p) != h}
record = dict(root=str(ROOT), head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              status=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True, encoding='utf-8'),
              release=identity['version'], release_drift=drift, files=hashes,
              archive=str(archive), archive_sha256=sha(archive), verified=True)
(BACKUP / 'manifest.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT / 'latest-backup.txt').write_text(str(BACKUP), encoding='utf-8')
print(json.dumps(dict(backup=str(BACKUP), files=len(files), release=identity['version'], drift=drift, verified=True), ensure_ascii=False))
