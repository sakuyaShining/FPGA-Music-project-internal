"""Back up the existing implementation before creating the integration candidate."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,zipfile
P=Path(__file__).resolve().parents[2]
E=Path('C:/Users/Sakuya/.codex/worktrees/instrument-engine-safety/FPGA-Music-project')
R=P/'experiments/system_integration_20261016'
N=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
b=N/('backup-'+datetime.now().strftime('%Y%m%d-%H%M%S'));b.mkdir(parents=True)
record={}
for label,root,folders in [('main',P,['src','tools/host','tools/scripts','project']),('engine',E,['src','tools/host','tools/scripts','project']),('prototypes',P,['experiments/right_hand_audio_20261016','experiments/right_hand_faders_20261016','experiments/music_visualizer_20261015'])]:
    files=[p for f in folders for p in (root/f).rglob('*') if p.is_file() and not any(x in ('__pycache__','impl','build','dist','synthesis','evidence','metrics','engine_probe') for x in p.relative_to(root).parts)]
    hashes={p.relative_to(root).as_posix():sha(p) for p in files}
    z=b/(label+'.zip')
    with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as a:
        for name in hashes:a.write(root/name,name)
    with zipfile.ZipFile(z) as a:
        assert a.testzip() is None
        assert all(hashlib.sha256(a.read(n)).hexdigest()==h for n,h in hashes.items())
    record[label]=dict(root=str(root),archive=str(z),sha256=sha(z),files=hashes)
(b/'manifest.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
(N/'latest-backup.txt').write_text(str(b),encoding='utf-8')
R.mkdir(parents=True,exist_ok=True)
src=P/'experiments/right_hand_audio_20261016'
for folder in ['engine','rtl']:
    dst=R/folder;dst.mkdir(exist_ok=True)
    for f in (src/folder).iterdir():
        if f.suffix in ('.v','.hex'):shutil.copyfile(f,dst/f.name)
for f in ['source-engine.json','fader_gain_q8.hex','audition-config.json']:
    shutil.copyfile(src/f,R/f)
for f in (P/'experiments/right_hand_faders_20261016/rtl').glob('*.v'):shutil.copyfile(f,R/'rtl'/f.name)
V=P/'experiments/music_visualizer_20261015'
for f in (V/'rtl').iterdir():
    if f.suffix in ('.v','.vh'):shutil.copyfile(f,R/'rtl'/f.name)
for f in V.glob('*1024.hex'):shutil.copyfile(f,R/'engine'/f.name)
(R/'upstream.json').write_text(json.dumps(dict(backup=str(b),inputs={p.relative_to(P).as_posix():sha(p) for p in list((src/'engine').glob('*.v'))+list((src/'rtl').glob('*.v'))+list((P/'experiments/right_hand_faders_20261016/rtl').glob('*.v'))+list((V/'rtl').glob('*')) if p.is_file()}),indent=2),encoding='utf-8')
print(json.dumps(dict(backup=str(b),protected={k:len(v['files']) for k,v in record.items()},verified=True)))
