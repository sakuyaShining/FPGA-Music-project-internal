"""Identity verification only; no simulation, hardware access or programming."""
from common import *
import zipfile
P=R.parents[1];d=json.loads((R/'delivery.json').read_text(encoding='utf-8'));n=0
for key,root in (('files',R),('documents',P),('stage_files',P)):
 for rel,h in d[key].items():assert sha(root/rel)==h,(key,rel);n+=1
for item in d['backups']:
 B=Path(item['root']);assert sha(B/'before.zip')==item['sha256']
 with zipfile.ZipFile(B/'before.zip') as z:assert z.testzip() is None
U=Path(d['upstream_root']);up=json.loads((R/'upstream.json').read_text(encoding='utf-8'))
assert sha(U/'delivery.json')==up['delivery_sha256']
for rel,h in up['files'].items():assert sha(U/rel)==h,('preserved upstream',rel)
print('PASS recorded identities',n,'version',d['version'])
print('Status:',d['status'])
print('Hardware:',d['hardware_scope'],'current board:',d['current_board'])
