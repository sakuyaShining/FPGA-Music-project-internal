"""Read-only community JLC assembly availability snapshot; never a platform quote."""
import csv
import json
import time
from datetime import datetime,timezone
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from native_review import ROOT

data=json.loads((ROOT/'design.json').read_text(encoding='utf-8'))
bycode={}
for p in data['parts']:bycode.setdefault(p['code'],[]).append(p)
out=ROOT/'evidence/jlcsearch';out.mkdir(exist_ok=True)
rows=[]
for code,members in sorted(bycode.items()):
    url='https://jlcsearch.tscircuit.com/api/search?'+urlencode({'q':code,'limit':5})
    row={'code':code,'mpn':members[0]['mpn'],'quantity':len(members),'checked_utc':datetime.now(timezone.utc).isoformat(),
         'status':'unknown','jlc_mirror_stock':'','basic':'','preferred':'','mirror_mpn':'','mirror_unit_usd':'',
         'source':'jlcsearch community mirror; not live JLC matching/stock reservation'}
    try:
        cached=out/(code+'.json')
        raw=cached.read_bytes() if cached.exists() else urlopen(Request(url,headers={'User-Agent':'FPGA-hardware-review/1.0'}),timeout=20).read()
        if not cached.exists():cached.write_bytes(raw)
        hits=json.loads(raw).get('components',[])
        exact=next((p for p in hits if str(p.get('lcsc'))==code[1:]),None)
        if exact is None:
            time.sleep(.5)
            mpnurl='https://jlcsearch.tscircuit.com/api/search?'+urlencode({'q':row['mpn'],'limit':20})
            mpnraw=urlopen(Request(mpnurl,headers={'User-Agent':'FPGA-hardware-review/1.0'}),timeout=20).read()
            (out/(code+'-mpn.json')).write_bytes(mpnraw)
            alternatives=json.loads(mpnraw).get('components',[])
            exact=next((p for p in alternatives if str(p.get('lcsc'))==code[1:]),None)
            row['mpn_search_different_codes']=','.join('C'+str(p.get('lcsc')) for p in alternatives if p.get('mfr')==row['mpn'] and str(p.get('lcsc'))!=code[1:])
        if exact:
            row.update(status='exact_code_mirror_snapshot',jlc_mirror_stock=exact.get('stock'),basic=exact.get('is_basic'),
                       preferred=exact.get('is_preferred'),mirror_mpn=exact.get('mfr'),mirror_unit_usd=exact.get('price'))
        else:row['status']='not_in_mirror_not_proof_of_unavailability'
    except Exception as e:row.update(status='lookup_failed',error=str(e))
    rows.append(row);print(code,row['status'],row['jlc_mirror_stock'],flush=True);time.sleep(.5)
fields=sorted(set(k for r in rows for k in r))
with (ROOT/'assembly-availability-SNAPSHOT.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
result={'checked_parts':len(rows),'exact_code_matches':sum(r['status']=='exact_code_mirror_snapshot' for r in rows),
 'reported_shortage':[r['code'] for r in rows if isinstance(r['jlc_mirror_stock'],(int,float)) and r['jlc_mirror_stock']<r['quantity']],
 'unknown':[r['code'] for r in rows if r['status']!='exact_code_mirror_snapshot'],
 'jlc_platform_match_performed':False,'quote_or_reservation':False}
(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result),flush=True)
