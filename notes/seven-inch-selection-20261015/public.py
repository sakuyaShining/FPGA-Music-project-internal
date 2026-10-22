"""Read public catalog pages only; preserve identity and price evidence."""
import concurrent.futures
import json
from pathlib import Path
import re
import sys
import urllib.request

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'hardware-selection-resume-20261015'))
import fetch_domestic
fetch_domestic.ROOT=ROOT

ITEMS=[
 ('LT7680A-R','C5156687','https://item.szlcsc.com/5791065.html'),
 ('PCM5122PWR','C962071','https://item.szlcsc.com/1043162.html'),
 ('PT8211-S','C92004','https://item.szlcsc.com/93193.html'),
 ('7inch HDMI LCD (C)','C359951','https://item.szlcsc.com/334768.html'),
 ('7inch HDMI LCD (B)','C359950','https://item.szlcsc.com/334767.html'),
]

def run(item):
 r=fetch_domestic.fetch(*item)
 p=ROOT/'evidence'/f'{item[1]}-domestic.html'
 if r['status']=='identity_checked_public_page':
  html=p.read_text(encoding='utf-8')
  m=re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',html,re.S)
  data=json.loads(m[1])['props']['pageProps']['webData']
  (ROOT/'evidence'/f'{item[1]}-public-data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
  r['commercial_fields']={k:v for k,v in data['productRecord'].items() if any(x in k.lower() for x in ('price','status','sale','stock','sell','buy','discount'))}
  r['public_price_fields']={k:v for k,v in data.items() if 'price' in k.lower()}
 return r

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 results=list(pool.map(run,ITEMS))
(ROOT/'evidence/domestic.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
for r in results:
 print(json.dumps({k:r.get(k) for k in ('mpn','lcsc','status','stock','valid_stock','minimum','commercial_fields','public_price_fields','error')},ensure_ascii=True))
