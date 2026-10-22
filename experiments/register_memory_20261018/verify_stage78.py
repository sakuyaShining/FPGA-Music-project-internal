"""Check delivery identities only; this is not a functional or hardware test."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent;P=R.parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
d=json.loads((R/'delivery.json').read_text(encoding='utf-8'));n=0
for group,root in [('source_files',R),('evidence',R),('inherited_76_artifacts',R),('documents',P),('stage_scripts',P)]:
 for rel,h in d[group].items():assert sha(root/rel)==h,(group,rel);n+=1
assert sha(Path(d['backup']['root'])/'before.zip')==d['backup']['sha256']
print('PASS recorded identities',n)
print('Version:',d['version'],'Product status:',d['status'])
print('Resources:',d['resource'])
print('Hardware tested:',d['hardware_tested'],'Programmed:',d['fpga_programmed'],'Current board:',d['current_hardware'])
