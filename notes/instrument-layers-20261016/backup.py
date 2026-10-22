from pathlib import Path
import hashlib,json,zipfile,datetime
R=Path(__file__).resolve().parents[2]
S=R/'experiments/left_hand_events_20261016'
D=Path(__file__).parent/('backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
D.mkdir(parents=True)
files=[p for p in S.rglob('*') if p.is_file() and not any(x in p.relative_to(S).parts for x in ('impl','evidence','__pycache__'))]
files += [R/'docs/02-技术方案'/n for n in ('38-代码盘点与实现基线-2026-10-09.md','39-最新设计构想与落地差距-2026-10-09.md','49-最终收敛设计总纲-2026-10-15.md','69-左手实例事件与真实音频接合-2026-10-16.md')]
files += [R/'src/gowin/tdm_synth'/p.name for p in (S/'engine').glob('*') if (R/'src/gowin/tdm_synth'/p.name).is_file()]
manifest={p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
with zipfile.ZipFile(D/'before.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in files:z.write(p,p.relative_to(R).as_posix())
with zipfile.ZipFile(D/'before.zip') as z:
    assert all(hashlib.sha256(z.read(k)).hexdigest()==v for k,v in manifest.items())
(D/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS verified before implementation',files=len(files),directory=str(D))))
