"""Fresh public catalog retrieval. Never reserves stock or submits an order."""
import csv,hashlib,json
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parent
RAW=ROOT/'catalog';RAW.mkdir(exist_ok=True)
parts=list(csv.DictReader((ROOT.parent/'procurement-native-candidate.csv').open(encoding='utf-8-sig')))
def fetch(part):
    code=part['code'];url='https://wmsc.lcsc.com/ftps/wm/product/detail?productCode='+code
    r={'code':code,'expected_mpn':part['mpn'],'checked_utc':datetime.now(timezone.utc).isoformat(),'url':url,
       'domestic_cny_unit':None,'jlc_assembly_stock_verified':False}
    try:
        with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=15) as response:
            raw=response.read();r['http_status']=response.status
        (RAW/(code+'.json')).write_bytes(raw)
        r['raw_sha256']=hashlib.sha256(raw).hexdigest()
        p=json.loads(raw).get('result') or {}
        assert p.get('productCode')==code,'Exact C-code mismatch'
        r.update(status='fresh_exact_code',actual_mpn=p.get('productModel'),manufacturer=p.get('brandNameEn'),
             mpn_text_matches=p.get('productModel')==part['mpn'],stock_lcsc=p.get('stockNumber'),
             minimum=p.get('minBuyNumber'),multiple=p.get('split'),full_package=p.get('minPacketNumber'),package=p.get('encapStandard'),datasheet=p.get('pdfUrl'),
             tiers=[{'minimum':t.get('ladder'),'usd':t.get('usdPrice')} for t in p.get('productPriceList',[])])
    except Exception as error:r.update(status='unavailable',error=str(error))
    return r

rows=[]
with ThreadPoolExecutor(max_workers=3) as pool:
    for future in as_completed([pool.submit(fetch,p) for p in parts]):
        rows.append(future.result())
        (ROOT/'fresh-catalog.json').write_text(json.dumps(sorted(rows,key=lambda x:x['code']),ensure_ascii=False,indent=2),encoding='utf-8')
        print(rows[-1]['code'],rows[-1]['status'],flush=True)
print('Completed fresh catalog attempts',len(rows),'; no reservation or manufacturing release.')
