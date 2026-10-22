"""Protect prior sources before deriving owned-contact candidates."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,zipfile
N=Path(__file__).resolve().parent;P=N.parents[1];U=P/'experiments/system_integration_20261016';R=P/'experiments/left_hand_events_20261016'
E=Path('C:/Users/Sakuya/.codex/worktrees/instrument-engine-safety/FPGA-Music-project')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
b=N/('backup-'+datetime.now().strftime('%Y%m%d-%H%M%S'));b.mkdir(parents=True)
records={}
for label,root,folders in [('main',P,['src','tools/host','tools/scripts','project']),('engine',E,['src','tools/host','tools/scripts','project']),('integration',U,['.'])]:
    files=[p for folder in folders for p in (root/folder).rglob('*') if p.is_file() and not any(x in ('impl','synthesis','evidence','__pycache__','build','dist') for x in p.relative_to(root).parts)]
    hashes={p.relative_to(root).as_posix():sha(p) for p in files}
    archive=b/(label+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for name in hashes:z.write(root/name,name)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(n)).hexdigest()==v for n,v in hashes.items())
    records[label]=dict(root=str(root),archive=str(archive),sha256=sha(archive),files=hashes)
(b/'manifest.json').write_text(json.dumps(records,indent=2),encoding='utf-8');(N/'latest-backup.txt').write_text(str(b),encoding='utf-8')
for name in ['engine','rtl','optimization','project']:
    d=R/name;d.mkdir(parents=True,exist_ok=True)
    for f in (U/name).iterdir():
        if f.is_file():shutil.copyfile(f,d/f.name)
for name in ['source-engine.json','audition-config.json','fader_gain_q8.hex']:shutil.copyfile(U/name,R/name)
(R/'upstream.json').write_text(json.dumps(dict(root=str(U),delivery_sha256=sha(U/'delivery.json'),backup=str(b),files={p.relative_to(U).as_posix():sha(p) for folder in ['engine','rtl','optimization','project'] for p in (U/folder).iterdir() if p.is_file()}),indent=2),encoding='utf-8')
print(json.dumps(dict(verified=True,backup=str(b),protected={k:len(v['files']) for k,v in records.items()})))
