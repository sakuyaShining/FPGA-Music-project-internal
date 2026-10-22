from pathlib import Path
import shutil,json,hashlib
P=Path(__file__).resolve().parents[2];U=P/'experiments/instrument_layers_20261016';R=P/'experiments/resource_safety_20261016'
R.mkdir(exist_ok=True)
for folder in ('engine','rtl','candidate'):
    (R/folder).mkdir(exist_ok=True)
    for p in (U/folder).iterdir():
        if p.suffix in ('.v','.vh','.hex'):shutil.copyfile(p,R/folder/p.name)
(R/'optimization').mkdir(exist_ok=True)
for name in ('pitch_mod.v','note_map_owned.v'):shutil.copyfile(U/'optimization'/name,R/'optimization'/name)
for p in U.iterdir():
    if p.name.startswith('tb_') and p.suffix=='.v' or p.name in ('sustain.hex','strike.hex','sustain.json','strike.json'):shutil.copyfile(p,R/p.name)
inputs={p.relative_to(U).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in U.rglob('*') if p.is_file() and not any(x in p.relative_to(U).parts for x in ('impl','evidence','__pycache__')) and not p.relative_to(U).parts[0].startswith('synthesis')}
(R/'upstream.json').write_text(json.dumps(dict(root=str(U),delivery_sha256=hashlib.sha256((U/'delivery.json').read_bytes()).hexdigest(),files=inputs),indent=2),encoding='utf-8')
print(R)
