"""Inspect persisted schematic TEXT records, excluding embedded symbol libraries."""
import json
from collections import Counter
from native_review import PROJECT

for p in PROJECT.glob('sch/**/*.esch2'):
    active=False;records={};types=Counter();deletions=[]
    for line in p.read_text(encoding='utf-8').splitlines():
        if '||' not in line:continue
        h,b=line.split('||',1);head=json.loads(h);raw=b.rstrip('|');body=json.loads(raw) if raw.strip() else None
        if head.get('type')=='DOCHEAD':
            active=body.get('docType')=='SCH_PAGE'
        if active and head.get('type')=='TEXT':
            if body is None:records.pop(head.get('id'),None)
            else:records[head.get('id')]=body
        if active:
            types[head.get('type')]+=1
            if head.get('type') in ['DELETE','DEL','DELETE_RECORD'] or head.get('deleted') or head.get('delete'):deletions.append({'h':head,'b':body})
    print(p.name,len(records),'types',dict(types),'delete examples',str(deletions[:1])[:500])
