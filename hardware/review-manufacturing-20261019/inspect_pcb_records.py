"""Read saved native PCB records after the PCB document header, excluding libraries."""
import json
from collections import Counter
from native_review import ROOT,PROJECT

records=[];active=False
for line in (PROJECT/'pcb/PCB1.epcb2').read_text(encoding='utf-8').splitlines():
    if '||' not in line:continue
    h,b=line.split('||',1)
    if not h.startswith('{'):continue
    head=json.loads(h);raw=b.rstrip('|');body=json.loads(raw) if raw.strip() else None
    if head.get('type')=='DOCHEAD':active=body.get('docType')=='PCB'
    if active:records.append({'header':head,'body':body})
print(Counter(x['header']['type'] for x in records))
for typ in ['LINE','TRACK','VIA','PAD']:
    ps=[x for x in records if x['header']['type']==typ]
    print(typ,len(ps),str(ps[:1])[:1400])
(ROOT/'pcb-native-saved-records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
