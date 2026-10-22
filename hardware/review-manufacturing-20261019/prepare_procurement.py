"""Trace native candidate quantities to exact catalog stock; no purchase orders."""
import csv
import hashlib
import json
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'evidence/catalog'

def fetch(code):
    url='https://wmsc.lcsc.com/ftps/wm/product/detail?productCode='+code
    row={'code':code,'checked_utc':datetime.now(timezone.utc).isoformat(),'url':url}
    try:
        path=OUT/(code+'.json')
        if path.exists():
            raw=path.read_bytes()
            row['checked_utc']=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat()
        else:
            with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as r:
                raw=r.read()
            path.write_bytes(raw)
        data=json.loads(raw);p=data.get('result') or {}
        row.update(status='exact_detail' if p.get('productCode')==code else 'identity_not_confirmed',
            mpn=p.get('productModel'),manufacturer=p.get('brandNameEn'),stock_lcsc=p.get('stockNumber'),
            package=p.get('encapStandard'),datasheet=p.get('pdfUrl'),
            price_usd_tiers=[{'minimum':x.get('ladder'),'usd':x.get('usdPrice')} for x in p.get('productPriceList',[])])
    except Exception as e:row.update(status='unavailable',error=str(e))
    return row

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    design=json.loads((ROOT/'design.json').read_text(encoding='utf-8'))
    grouped=defaultdict(list)
    for p in design['parts']:grouped[p['code']].append(p)
    catalog=[]
    for code in sorted(grouped):
        catalog.append(fetch(code))
        time.sleep(0.5)
    (OUT/'summary.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    rows=[]
    for info in catalog:
        members=grouped[info['code']];p=members[0];used=len(members)
        identity=info.get('status')=='exact_detail' and info.get('mpn')==p['mpn']
        tiers=info.get('price_usd_tiers',[])
        minimum=int(tiers[0]['minimum']) if tiers else None
        qty=max(used,minimum or used)
        price=next((t['usd'] for t in reversed(tiers) if qty>=int(t['minimum'])),None)
        rows.append(dict(code=p['code'],mpn=p['mpn'],references=','.join(x['ref'] for x in members),
            footprint=p['footprint'],placed_quantity=used,minimum_purchase=minimum,sample_purchase_quantity=qty,
            stock_lcsc=info.get('stock_lcsc'),unit_usd=price,
            native_identity_matches_current_catalog=identity,
            domestic_cny_quote='',release_status='REVIEW_ONLY',
            assembly=('manual_through_hole' if p['ref'].startswith('J') or p['ref']=='SW1' else
                      'manual_SMD_button' if p['ref'].startswith('SW') else 'SMT_candidate'),
            notes=('Native review candidate only; no stock reservation or domestic delivered quote' if identity else
                'Exact C-code returned; localized connector MPN name differs, supplier mechanical drawing must be checked')))
    with (ROOT/'procurement-native-candidate.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    jlc=[{'Comment':r['mpn'],'Designator':r['references'],'Footprint':r['footprint'],'LCSC Part #':r['code']} for r in rows if r['assembly']=='SMT_candidate']
    with (ROOT/'jlc-bom-DRAFT-NOT-FOR-ORDER.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(jlc[0]));w.writeheader();w.writerows(jlc)
    summary={'native_components':len(design['parts']),'unique_parts':len(rows),
        'identities_matched':sum(r['native_identity_matches_current_catalog'] for r in rows),
        'shortage_or_unknown':[r['code'] for r in rows if not isinstance(r['stock_lcsc'],(int,float)) or r['stock_lcsc']<r['sample_purchase_quantity']],
        'not_in_native_bom':['Nano20K and existing 4ohm3W speaker','7inch RA8875+CTP module','ILI9341 small module',
            'two screen harnesses and mating cable','qualified regulated 5V adapter and mating JST housing/contacts',
            'external TRS jack/cable/ESD','electrode PCB geometry/cover film','enclosure/mechanical mounting',
            'shipping/PCB/SMT fees'],
        'prices':'USD public LCSC tiers; NOT a domestic RMB or landed quote',
        'fabrication_release':False,'pcb_evidence':'Separate native PCB / DRC / CPL review required'}
    (ROOT/'evidence/procurement-check.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
