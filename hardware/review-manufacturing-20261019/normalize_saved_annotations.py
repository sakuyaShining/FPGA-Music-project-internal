"""Repair persisted review TEXT duplication without changing electrical records.

Native TEXT.delete changed the live canvas but old TEXT records survived folder
save/reopen in this client. Work only on our owned candidate with the session
closed; retain the latest native-created record for each current note.
"""
import hashlib
import json
import time
import zipfile
from pathlib import Path
from native_review import ROOT,PROJECT,call

design=json.loads((ROOT/'design.json').read_text(encoding='utf-8'))
ids=json.loads((ROOT/'pages.json').read_text())
names={v:k for k,v in ids.items()}
changes=[]
def digest(lines):return hashlib.sha256('\n'.join(lines).encode()).hexdigest()
for path in PROJECT.glob('sch/**/*.esch2'):
    lines=path.read_text(encoding='utf-8').splitlines();active=False;pageid=None;electrical=[];texts=[]
    for i,line in enumerate(lines):
        h,b=line.split('||',1);head=json.loads(h);raw=b.rstrip('|');body=json.loads(raw) if raw.strip() else None
        if head['type']=='DOCHEAD':
            active=body.get('docType')=='SCH_PAGE'
            if active:pageid=body['uuid']
        if active:
            if head['type']=='TEXT':texts.append((i,head,body))
            elif head['type'] not in ['DOCHEAD','META']:electrical.append(line)
    assert pageid in names,(path,pageid)
    name=names[pageid];wanted=[name+' - REVIEW CANDIDATE / NOT FOR FABRICATION',*design['notes'][name]]
    keep=set()
    for value in wanted:
        matches=[r for r in texts if isinstance(r[2],dict) and r[2].get('value')==value]
        assert matches,('Missing current note',name,value)
        keep.add(max(matches,key=lambda r:r[1].get('ticket',0))[0])
    remove={r[0] for r in texts}-keep
    changes.append(dict(path=path,lines=lines,pageid=pageid,name=name,keep=keep,remove=remove,
                        before_hash=digest(electrical),before_texts=len(texts),after_texts=len(keep)))

sid=json.loads((ROOT/'evidence/open.json').read_text())['value']['sessionId']
print(call('v2-close-normalize-text',['session','close','--session',sid,'--destroy']),flush=True)
dest=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')
backup=dest/'before-saved-text-normalization.zip'
if backup.exists():raise RuntimeError('Do not overwrite normalization backup')
with zipfile.ZipFile(backup,'w',zipfile.ZIP_DEFLATED) as z:
    for p in PROJECT.rglob('*'):
        if p.is_file() and 'exports' not in p.as_posix():z.write(p,p.relative_to(PROJECT))
descriptor=PROJECT/(PROJECT.name+'.eprj3');meta=json.loads(descriptor.read_text(encoding='utf-8'))
stamp=int(time.time()*1000);report=[]
for item in changes:
    out=[];active=False;electrical=[]
    for i,line in enumerate(item['lines']):
        h,b=line.split('||',1);head=json.loads(h);raw=b.rstrip('|');body=json.loads(raw) if raw.strip() else None
        if head['type']=='DOCHEAD':
            active=body.get('docType')=='SCH_PAGE'
            if active:
                body.update(updateTime=stamp,version=str(stamp))
                line=json.dumps(head,separators=(',',':'))+'||'+json.dumps(body,ensure_ascii=False,separators=(',',':'))+'|'
        if active and head['type']=='META':
            body['title']=item['name']
            line=json.dumps(head,separators=(',',':'))+'||'+json.dumps(body,ensure_ascii=False,separators=(',',':'))+'|'
        if i in item['remove']:continue
        out.append(line)
        if active and head['type'] not in ['DOCHEAD','META','TEXT']:electrical.append(line)
    assert digest(electrical)==item['before_hash'],'Electrical record changed'
    target=item['path'].with_name(item['name']+'.esch2')
    if target!=item['path'] and target.exists():raise RuntimeError('Rename target exists')
    item['path'].write_text('\n'.join(out)+'\n',encoding='utf-8')
    if target!=item['path']:item['path'].rename(target)
    sheet=meta['profile']['sheets'][item['pageid']]
    sheet.update(title=item['name'],version=str(stamp),updateTime=stamp)
    report.append({'page':item['name'],'removed':len(item['remove']),'current_texts':item['after_texts'],
                   'electrical_records_sha256_before':item['before_hash'],'electrical_records_sha256_after':digest(electrical)})
meta['default_sheet']=ids[design['pages'][0]]
descriptor.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(ROOT/'annotation-persistence-repair.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('Removed stale saved TEXT only:',sum(r['removed'] for r in report),'records; all 14 electrical hashes unchanged',flush=True)
v=call('v2-open-after-text-normalization',['open','--path',descriptor.as_posix(),'--headless','true'],120)
(ROOT/'evidence/open.json').write_text(json.dumps({'ok':True,'value':v}),encoding='utf-8')
print(v,flush=True)
