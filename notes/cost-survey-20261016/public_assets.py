"""Read publicly linked storefront code solely to identify public price display semantics."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import urllib.request
E=Path(__file__).resolve().parent/'evidence'
urls=json.loads((E/'public-script-urls.json').read_text(encoding='utf-8'))
urls=[x for x in urls if any(k in x for k in ('/pages/item/','/652-','/5421-','/8484-'))]
def run(url):
 try:
  with urllib.request.urlopen(url,timeout=20) as resp:raw=resp.read()
  name=url.rsplit('/',1)[1];(E/name).write_bytes(raw)
  s=raw.decode('utf-8')
  hits=[m.group(0) for m in re.finditer(r'.{0,100}(?:productPrice|priceList|ladder|[Pp]rice[A-Za-z]*:|getPrice|PriceUrl|theRatio|productUnit).{0,160}',s)]
  return dict(url=url,bytes=len(raw),hits=hits[:60])
 except Exception as e:return dict(url=url,error=str(e))
with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(run,urls))
(E/'asset-price-hints.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=True))
