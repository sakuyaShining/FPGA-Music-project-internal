"""Verify recorded identities, not a substitute for functionality/board tests."""
from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parent;P=R.parents[1];d=json.loads((R/'delivery.json').read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
n=0
for group,root in [('source_files',R),('evidence',R),('inherited_76_artifacts',R),('documents',P),('stage_scripts',P)]:
 for rel,h in d[group].items():assert sha(root/rel)==h,(group,rel);n+=1
assert sha(Path(d['backup']['root'])/'before.zip')==d['backup']['sha256']
print('PASS recorded file identities',n)
print('Product status:',d['status'])
print('Joint synthesis:',d['resource'])
print('New RAM hardware tested:',d['hardware_tested'],'programmed:',d['fpga_programmed'],'media/Flash accessed:',d['storage_media_accessed'],d['flash_read_or_written'])
