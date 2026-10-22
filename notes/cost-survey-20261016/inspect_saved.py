"""Normalize saved public sales units without new requests."""
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parent
E=ROOT/'evidence'
data=json.loads((E/'domestic-survey.json').read_text(encoding='utf-8'))
fields=['theRatio','convesionRatio','productUnit','productMinEncapsulationUnit','productMinEncapsulationNumber','minBuyNumber','productUnsealVendition','saleRuleGroupId','stockNumber','validStockNumber']
for r in data:
 if r['status']!='identity_checked':continue
 s=(E/(r['lcsc']+'-domestic.html')).read_text(encoding='utf-8')
 m=re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',s,re.S)
 p=json.loads(m[1])['props']['pageProps']['webData']['productRecord']
 r['sales_fields']={k:p.get(k) for k in fields}
 print(json.dumps(dict(code=r['lcsc'],price=r['structured_offers'],sales_fields=r['sales_fields']),ensure_ascii=True))
(E/'domestic-normalized.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
