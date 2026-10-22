"""Inspect public product page assets and structured offers, no account data."""
import json
from pathlib import Path
import re
import urllib.request

ROOT=Path(__file__).resolve().parent
E=ROOT/'evidence';E.mkdir(parents=True,exist_ok=True)
url='https://item.szlcsc.com/334768.html'
with urllib.request.urlopen(url,timeout=20) as resp:raw=resp.read()
(E/'C359951-domestic.html').write_bytes(raw)
s=raw.decode('utf-8')
scripts=re.findall(r'<script[^>]*src="([^"]+)"',s)
scripts=[x for x in scripts if '/_next/' in x]
(E/'public-script-urls.json').write_text(json.dumps(scripts,indent=2),encoding='utf-8')
for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',s,re.S):
 d=json.loads(m[1]);(E/'C359951-structured-offers.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(d,ensure_ascii=True)[:4500])
print(json.dumps(scripts,ensure_ascii=True))
