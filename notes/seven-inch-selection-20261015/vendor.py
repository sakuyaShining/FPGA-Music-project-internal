"""Retain public vendor product pages for module configuration verification."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import urllib.request

ROOT=Path(__file__).resolve().parent/'evidence'
URLS={
 'buydisplay-cn':'https://www.buydisplay.com/chinese/7-inch-lcd-module-capacitive-touch-screen-panel-i2c-spi-serial',
 'buydisplay-en':'https://www.buydisplay.com/7-inch-lcd-module-capacitive-touch-screen-panel-i2c-spi-serial',
 'ronbo-msp7001':'https://www.ronboe.com/shop/msp7001/',
 'surenoo':'https://www.surenoo.com/products/23163813',
}
def fetch(item):
 name,url=item
 try:
  with urllib.request.urlopen(url,timeout=20) as response:
   raw=response.read();code=response.status
  (ROOT/(name+'.html')).write_bytes(raw)
  return dict(name=name,url=url,status=code,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 except Exception as e:return dict(name=name,url=url,error=str(e))
with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(fetch,URLS.items()))
(ROOT/'vendors.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=True))
