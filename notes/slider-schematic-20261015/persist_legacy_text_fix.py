"""Fallback for native deletes not persisted to an offline eprj3 file.

Only two known obsolete TEXT values are blanked, using the documented V3
record format and higher tickets. All electrical primitives are untouched.
"""
import hashlib
import json
import time
from phase import ROOT,PROJECT,call

sid=json.loads((ROOT/'evidence/open.json').read_text(encoding='utf-8'))['value']['sessionId']
print(call('close-before-text-file-fix',['session','close','--session',sid,'--destroy']))
path=PROJECT/'sch/Schematic1/P1.esch2'
assert PROJECT.resolve() in path.resolve().parents
before=path.read_bytes()
backup=ROOT/'evidence/before-text-persistence-fix.esch2'
assert not backup.exists()
backup.write_bytes(before)
lines=before.decode('utf-8').splitlines()
records=[(line.split('||',1)[0],line.split('||',1)[1]) for line in lines]
ticket=max(json.loads(a).get('ticket',0) for a,b in records)
ids={'adff1b6371d40af6','7b4104cc1ec9c1bc'}
found=[];out=[]
for a,b in records:
    h=json.loads(a)
    if h.get('type')=='TEXT' and h.get('id') in ids:
        body=json.loads(b.rstrip('|'))
        assert 'NOT WIRED' in body['value']
        found.append({'id':h['id'],'old':body['value']})
        body['value']='';ticket+=1;h['ticket']=ticket
        a=json.dumps(h,separators=(',',':'));b=json.dumps(body,ensure_ascii=False,separators=(',',':'))+'|'
    out.append(a+'||'+b)
assert len(found)==2
path.write_text('\n'.join(out)+'\n',encoding='utf-8')
result={'changed_only':'Two obsolete TEXT values and their logical tickets',
        'before_sha256':hashlib.sha256(before).hexdigest(),'after_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'changed':found}
(ROOT/'evidence/text-persistence-fix.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(result['changed_only'])
print(call('open',['open','--path',str(PROJECT/(PROJECT.name+'.eprj3')),'--headless','true'],90))
