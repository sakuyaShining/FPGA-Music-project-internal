import json
from native_review import PROJECT

for pattern in ['sch/**/*.esch2','pcb/*.epcb2']:
    for p in PROJECT.glob(pattern):
        found=[]
        for line in p.read_text(encoding='utf-8').splitlines():
            if '||' not in line:continue
            h,body=line.split('||',1)
            if not h.startswith('{'):continue
            record=json.loads(h)
            if record.get('type')=='DOCHEAD':
                data=json.loads(body.rstrip('|'))
                if data.get('docType') not in ['SYMBOL','FOOTPRINT','DEVICE']:found.append(data)
            if record.get('type')=='META' and found and found[-1].get('docType') in ['SCH_PAGE','PCB']:
                found[-1]['meta']=json.loads(body.rstrip('|'))
        print(p.relative_to(PROJECT),found)
