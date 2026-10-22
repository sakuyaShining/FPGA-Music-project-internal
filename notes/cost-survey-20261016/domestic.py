"""Public domestic JSON-LD offers and NEXT payload; never confuse pack/unit prices."""
from concurrent.futures import ThreadPoolExecutor
import datetime
import hashlib
import json
from pathlib import Path
import re
import urllib.request

ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1]
E=ROOT/'evidence';E.mkdir(parents=True,exist_ok=True)
old=json.loads((PROJECT/'notes/hardware-closeout-20261015/evidence/domestic-refresh.json').read_text(encoding='utf-8'))
old+=json.loads((PROJECT/'notes/seven-inch-selection-20261015/evidence/domestic.json').read_text(encoding='utf-8'))
old=[x for x in old if x['lcsc'] not in ('C5156687','C359950','C52994086')]
def fetch(item):
 code,mpn,url=item['lcsc'],item['mpn'],item['url']
 result=dict(lcsc=code,mpn=mpn,url=url,retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),unit_price_cny=None)
 try:
  with urllib.request.urlopen(url,timeout=20) as response:raw=response.read()
  s=raw.decode('utf-8');(E/(code+'-domestic.html')).write_bytes(raw)
  d=json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',s,re.S)[1])['props']['pageProps']['webData']
  p=d['productRecord']
  if p['productModel']!=mpn or p['productCode']!=code:raise ValueError('Identity mismatch')
  offers=[]
  for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',s,re.S):
   ld=json.loads(m[1])
   for x in ld.get('@graph',[ld]):
    if x.get('@type')=='Product' and x.get('sku')==code:offers.append(x.get('offers'))
  result.update(status='identity_checked',stock=p.get('validStockNumber'),minimum=p.get('minBuyNumber'),
   package_qty=p.get('productMinEncapsulationNumber'),package_ref_cny=p.get('encaptionPrice'),
   structured_offers=offers,sha256=hashlib.sha256(raw).hexdigest())
 except Exception as e:result.update(status='unverified',error=str(e))
 return result
with ThreadPoolExecutor(max_workers=3) as pool:
 results=[]
 for r in pool.map(fetch,old):
  results.append(r)
  (E/'domestic-survey.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps(r,ensure_ascii=True),flush=True)
