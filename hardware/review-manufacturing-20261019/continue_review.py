"""Open our owned review candidate for a new documented revision."""
import json
import zipfile
from native_review import ROOT, PROJECT, call

e=ROOT/'evidence/v2';e.mkdir(exist_ok=True)
backup=e/'before-v2-native.zip'
if backup.exists():raise RuntimeError('Do not overwrite v2 pre-edit backup')
with zipfile.ZipFile(backup,'w',zipfile.ZIP_DEFLATED) as z:
    for p in PROJECT.rglob('*'):
        if p.is_file() and 'exports' not in p.as_posix():z.write(p,p.relative_to(PROJECT))
print(call('v2-sessions',['session','list']))
v=call('v2-open',['open','--path',(PROJECT/(PROJECT.name+'.eprj3')).as_posix(),'--headless','true'],120)
# Existing helpers consume this file. The v1 envelope is preserved.
prior=ROOT/'evidence/open.json'
if not (e/'v1-open.json').exists():(e/'v1-open.json').write_bytes(prior.read_bytes())
prior.write_text(json.dumps({'ok':True,'value':v},indent=2)+'\n',encoding='utf-8')
print(v)
