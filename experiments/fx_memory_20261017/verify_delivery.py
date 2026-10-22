"""Identity verification only. Functional evidence has its own stated scope."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent;P=R.parents[1]
d=json.loads((R/'delivery.json').read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
n=0
for group,root in [('source_files',R),('evidence',R),('documents',P),('stage_scripts',P),('hardware_evidence',P)]:
 for rel,h in d[group].items():assert sha(root/rel)==h,(group,rel);n+=1
assert sha(Path(d['backup']['root'])/'before.zip')==d['backup']['sha256']
print('PASS recorded file identities',n)
print('Product status:',d['status'])
print('Joint synthesis:',d['resource'])
print('Diagnostic internal slack:',d['board_slack_ns'],'hardware_tested:',d['hardware_tested'],'Flash read/written:',d['flash_read_or_written'])
