"""Read new exact domestic candidates and original manufacturer PDFs."""
from concurrent.futures import ThreadPoolExecutor
import datetime
import hashlib
import json
from pathlib import Path
import re
import urllib.request

ROOT=Path(__file__).resolve().parent;E=ROOT/'evidence';E.mkdir(parents=True,exist_ok=True)
items=[
 ('C179326','74HC4067PW,118','https://item.szlcsc.com/190720.html'),
 ('C2841426','TPD4E02B04DQAR-TP','https://item.szlcsc.com/3023524.html'),
 ('C2992617','CD4067','https://item.szlcsc.com/3457702.html'),
]
def fetch(item):
 code,mpn,url=item;r=dict(code=code,mpn=mpn,url=url,checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
 try:
  with urllib.request.urlopen(url,timeout=20) as response:raw=response.read()
  (E/(code+'.html')).write_bytes(raw);s=raw.decode('utf-8')
  m=re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',s,re.S)
  d=json.loads(m[1])['props']['pageProps']['webData'];p=d['productRecord']
  if p['productCode']!=code or p['productModel']!=mpn:raise ValueError('Exact identity mismatch')
  offers=[]
  for match in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',s,re.S):
   for x in json.loads(match[1]).get('@graph',[]):
    if x.get('sku')==code:offers.append(x.get('offers'))
  r.update(status='identity_checked',stock_pieces=p.get('stockNumber'),sale_increment=p.get('theRatio'),
   min_sale_units=p.get('minBuyNumber'),offers=offers,package=p.get('encapsulationModel'),
   pdf=d.get('pdfFileDetailVO'),sha256=hashlib.sha256(raw).hexdigest())
 except Exception as e:r.update(status='unverified',error=str(e))
 return r
with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(fetch,items))
(E/'domestic-candidates.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
for r in results:print(json.dumps({k:v for k,v in r.items() if k!='pdf'},ensure_ascii=True))
