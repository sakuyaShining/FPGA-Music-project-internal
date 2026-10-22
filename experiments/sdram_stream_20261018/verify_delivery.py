"""Identity verification only. No simulation, JTAG, serial or media access."""
from common import *
import zipfile
P=R.parents[1];d=json.loads((R/'delivery.json').read_text(encoding='utf-8'));n=0
for key,root in (('files',R),('documents',P),('stage_files',P)):
 for rel,h in d[key].items():assert sha(root/rel)==h,(key,rel);n+=1
B=Path(d['backup']['root']);assert sha(B/'before.zip')==d['backup']['sha256']
with zipfile.ZipFile(B/'before.zip') as z:assert z.testzip() is None
up=json.loads((R/'upstream.json').read_text(encoding='utf-8'))
for key in ('controller','timing'):
 U=Path(up[key+'_root']);assert sha(U/'delivery.json')==up[key+'_delivery_sha256']
 for rel,h in up[key+'_files'].items():assert sha(U/rel)==h,(key,rel)
print('PASS recorded identities',n,'version',d['version'])
print('Status:',d['status'],'joint resource:',d['resource'])
print('This stage hardware:',d['hardware_tested'],'final mixer:',d['final_mixer_connected'],'current board:',d['current_board'])
