"""Read public domestic product pages, validate MPN/C-code and retain stock.

No login/private API or access-control workaround. Prices not present in the
public page are left unknown. Whole-package reference price is NOT unit price.
"""
import argparse
import datetime
import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def fetch(mpn,code,url):
    result={'mpn':mpn,'lcsc':code,'url':url,'currency':'CNY','unit_price':None,
            'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        with urllib.request.urlopen(url,timeout=20) as response:
            raw=response.read()
            result['http_status']=response.status
        (ROOT/'evidence'/f'{code}-domestic.html').write_bytes(raw)
        result['html_sha256']=hashlib.sha256(raw).hexdigest()
        match=re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',raw.decode('utf-8'),re.S)
        if not match: raise ValueError('No public product payload')
        data=json.loads(match[1])['props']['pageProps']['webData']
        product=data['productRecord']
        if product.get('productModel')!=mpn or product.get('productCode')!=code:
            raise ValueError('MPN/C-code identity mismatch')
        result.update(status='identity_checked_public_page',stock=product.get('stockNumber'),
            valid_stock=product.get('validStockNumber'),total_stock=data.get('totalStockNumber'),
            assembly_stock=data.get('smtStockNumber'),minimum=product.get('minBuyNumber'),
            full_package_quantity=product.get('productMinEncapsulationNumber'),
            full_package_reference_price=product.get('encaptionPrice'),
            sales_unit=product.get('productUnit'),pieces_per_sales_unit=product.get('theRatio'),
            minimum_whole_number=product.get('minWholeNumber'),
            parameters=data.get('paramList'),package=product.get('encapsulationModel'))
        result['price_note']='Unit price/MOQ rounding/checkout shipping still require actual quotation; encaptionPrice is kept separately.'
    except Exception as exc:
        result.update(status='not_verified',error=f'{type(exc).__name__}: {exc}')
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('list',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    items=json.loads(args.list.read_text(encoding='utf-8'))
    results=[]
    for item in items:
        r=fetch(item['mpn'],item['lcsc'],item['url']);results.append(r)
        args.output.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:r.get(k) for k in ('mpn','lcsc','status','stock','valid_stock','error')},ensure_ascii=True),flush=True)
        time.sleep(0.5)


if __name__=='__main__':main()
