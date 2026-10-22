from common import *
d=json.loads((R/'delivery.json').read_text(encoding='utf-8'));P=R.parents[1];count=0
for key,root in [('files',R),('documents',P),('stage_scripts',P)]:
 for rel,h in d[key].items():assert sha(root/rel)==h,(key,rel);count+=1
assert sha(Path(d['backup']['root'])/'before.zip')==d['backup']['sha256']
print('PASS recorded delivery identities',count,'version',d['version'])
print('Status:',d['status']);print('Resources:',d['resource'])
print('Hardware tested:',d['hardware_tested'],'SDRAM/TF backend implemented:',d['media_backend_implemented'])
