"""Fingerprint actual saved copper-fill geometry, accounting for tombstones."""
import hashlib
import json
import sys
from native_review import ROOT,PROJECT

board=False;values={}
for line in (PROJECT/'pcb/PCB1.epcb2').read_text(encoding='utf-8').splitlines():
    if '||' not in line:continue
    a,b=line.split('||',1);header=json.loads(a);raw=b.rstrip('|');body=json.loads(raw) if raw else None
    if header['type']=='DOCHEAD':board=body['docType']=='PCB'
    if board and header['type']=='POURED':
        old=values.get(header['id'])
        if not old or header['ticket']>=old['ticket']:values[header['id']]={'ticket':header['ticket'],'body':body}
result={k:{'ticket':v['ticket'],'sha256':hashlib.sha256(json.dumps(v['body'],sort_keys=True).encode()).hexdigest()} for k,v in values.items() if v['body']}
(ROOT/('poured-fingerprint-'+sys.argv[1]+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2),flush=True)
