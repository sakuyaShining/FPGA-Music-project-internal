"""Public LCSC quantity-price survey; exact identity, currency and tiers retained."""
import csv
import datetime
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.request

ROOT=Path(__file__).resolve().parent
E=ROOT/'evidence';E.mkdir(parents=True,exist_ok=True)
PROJECT=ROOT.parents[1]
rows=list(csv.DictReader((PROJECT/'hardware/system-candidate-20261015/system-bom-candidate.csv').open(encoding='utf-8-sig')))
items={r['lcsc']:r['mpn'] for r in rows if r['lcsc'] and r['full_26_example_qty'] not in ('','0')}
items.update({'C92004':'PT8211-S','C962071':'PCM5122PWR','C359951':'7inch HDMI LCD (C)'})
results=[]
for code,mpn in items.items():
 url='https://wmsc.lcsc.com/ftps/wm/product/detail?productCode='+code
 r=dict(lcsc=code,requested_mpn=mpn,url=url,retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
 try:
  with urllib.request.urlopen(url,timeout=20) as resp:raw=resp.read();r['http_status']=resp.status
  (E/(code+'-lcsc.json')).write_bytes(raw)
  data=json.loads(raw)
  d=data.get('result')
  if data.get('code')!=200 or not isinstance(d,dict):raise ValueError('No public product payload')
  actual=d.get('productCode') or d.get('productCodeEn')
  if d.get('productModel')!=mpn or actual!=code:raise ValueError('Exact MPN/C-code mismatch: '+str((d.get('productModel'),actual)))
  r.update(status='identity_checked',mpn=d['productModel'],brand=d.get('brandNameEn'),stock=d.get('stockNumber'),
   minimum=d.get('minBuyNumber'),minimum_increment=d.get('minWholeNumber'),
   prices=d.get('productPriceList'),product_id=d.get('productId'),package=d.get('encapStandard'),
   sha256=hashlib.sha256(raw).hexdigest())
 except Exception as e:r.update(status='unverified',error=str(e))
 results.append(r)
 (E/'lcsc-survey.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:r.get(k) for k in ('lcsc','mpn','status','stock','minimum','prices','error')},ensure_ascii=True),flush=True)
 if r.get('http_status') in (401,403) or 'HTTP Error 403' in r.get('error',''):
  print('Public endpoint refused request; stopping this source without retries.',flush=True)
  break
 time.sleep(.5)
