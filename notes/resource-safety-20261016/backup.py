from pathlib import Path
import json,hashlib,zipfile,datetime
P=Path(__file__).resolve().parents[2];U=P/'experiments/instrument_layers_20261016'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
delivery=json.loads((U/'delivery.json').read_text(encoding='utf-8'))
for group in ('source_files','evidence'):
    for name,digest in delivery[group].items():assert sha(U/name)==digest,(group,name)
for name,digest in delivery['design_documents'].items():assert sha(P/name)==digest,name
D=Path(__file__).parent/('backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));D.mkdir(parents=True)
files={U/name for group in ('source_files','evidence') for name in delivery[group]}
files.add(U/'delivery.json');files.update(P/name for name in delivery['design_documents'])
manifest={p.relative_to(P).as_posix():sha(p) for p in sorted(files)}
with zipfile.ZipFile(D/'before.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in manifest:z.write(P/name,name)
with zipfile.ZipFile(D/'before.zip') as z:
    assert z.testzip() is None
    assert all(hashlib.sha256(z.read(k)).hexdigest()==v for k,v in manifest.items())
(D/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(D.parent/'latest-backup.txt').write_text(str(D),encoding='utf-8')
print(json.dumps(dict(status='PASS prior delivery and backup verified before edits',files=len(manifest),directory=str(D))))
