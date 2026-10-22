"""Read-only identity audit; never treats routing failure as timing PASS."""
from common import *
import zipfile
P=R.parents[1];d=json.loads((R/'delivery.json').read_text(encoding='utf-8'));n=0
for key,root in (('files',R),('documents',P),('stage_files',P)):
    for rel,h in d[key].items():assert sha(root/rel)==h,(key,rel);n+=1
for b in d['backups']:
    B=Path(b['root']);assert sha(B/'before.zip')==b['sha256'] and sha(B/'manifest.json')==b['manifest_sha256']
    with zipfile.ZipFile(B/'before.zip') as z:
        assert z.testzip() is None
        for v in json.loads((B/'manifest.json').read_text(encoding='utf-8')).values():
            assert __import__('hashlib').sha256(z.read(v['member'])).hexdigest()==v['sha256']
up=json.loads((R/'upstream.json').read_text(encoding='utf-8'))
for prefix in ('','board_'):
    U=Path(up[prefix+'root']);assert sha(U/'delivery.json')==up[prefix+'delivery_sha256']
    for rel,h in up[prefix+'files'].items():assert sha(U/rel)==h,(prefix,rel)
assert not d['bench_gate'] and not d['new_hardware_tested']
print('PASS recorded identities',n,'version',d['version'])
print('PLACEMENT:',d['joint_placement_status'],'ROUTING:',d['joint_routing_status'],'TIMING:',d['joint_timing_status'])
print('Hardware programmed:',d['new_hardware_tested'],'current board:',d['current_board'])
