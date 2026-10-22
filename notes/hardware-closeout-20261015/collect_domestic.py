"""Fetch public domestic catalog pages into new, non-overwriting evidence scope."""
import json
from pathlib import Path
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,str(REPO/'notes/hardware-selection-resume-20261015'))
import fetch_domestic
fetch_domestic.ROOT=ROOT

pages=[]
for filename in ['domestic-pages.json','manual-domestic-pages.json','passive-pages.json']:
    for row in json.loads((REPO/'notes/hardware-selection-resume-20261015'/filename).read_text(encoding='utf-8')):
        if row['lcsc'] not in {p['lcsc'] for p in pages}:pages.append(row)
pages.extend([
 {'mpn':'TPD1E01B04DPYR-TP','lcsc':'C2858691','url':'https://item.szlcsc.com/3062164.html'},
 {'mpn':'PESD3V3U1UL,315(ES)','lcsc':'C52994086','url':'https://item.szlcsc.com/55929080.html'},
])
results=[]
for row in pages:
    result=fetch_domestic.fetch(row['mpn'],row['lcsc'],row['url']);results.append(result)
    (ROOT/'evidence/domestic-refresh.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result.get(k) for k in ['mpn','lcsc','status','stock','error']},ensure_ascii=True),flush=True)
    time.sleep(0.5)

# Download exactly the datasheet exposed by this public product page.
for code in ['C2858691','C52994086']:
    path=ROOT/'evidence'/f'{code}-domestic.html'
    import re
    match=re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',path.read_text(encoding='utf-8'),re.S)
    data=json.loads(match[1])['props']['pageProps']['webData']
    detail=data.get('pdfFileDetailVO',{})
    if detail.get('fileUrl'):
        url='https://atta.szlcsc.com'+detail['fileUrl']
        with urllib.request.urlopen(url,timeout=25) as response:raw=response.read()
        if not raw.startswith(b'%PDF-'):raise ValueError('Not PDF '+code)
        (ROOT/'evidence'/f'{code}-manufacturer.pdf').write_bytes(raw)
        (ROOT/'evidence'/f'{code}-manufacturer-source.json').write_text(json.dumps({'url':url,'detail':detail},ensure_ascii=False,indent=2),encoding='utf-8')
