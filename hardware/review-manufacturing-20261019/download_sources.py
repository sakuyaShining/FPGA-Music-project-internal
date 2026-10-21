"""Download public original manufacturer documents to D: for review traceability."""
import hashlib
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from native_review import ROOT

DEST=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261019/datasheets')
SOURCES={
 'Nexperia-74HC4067.pdf':'https://assets.nexperia.com/documents/data-sheet/74HC_HCT4067.pdf',
 'Nexperia-74LVC1G157.pdf':'https://assets.nexperia.com/documents/data-sheet/74LVC1G157.pdf',
 'TI-TPD4E02B04.pdf':'https://www.ti.com/lit/ds/symlink/tpd4e02b04.pdf',
 'TI-PCM5122.pdf':'https://www.ti.com/lit/ds/symlink/pcm5122.pdf',
 'TI-SN74LV595A.pdf':'https://www.ti.com/lit/ds/symlink/sn74lv595a.pdf',
 'TI-SN74LV165A.pdf':'https://www.ti.com/lit/ds/symlink/sn74lv165a.pdf',
 'TI-SN74LVC14A.pdf':'https://www.ti.com/lit/ds/symlink/sn74lvc14a.pdf',
 'DIODES-AP2112.pdf':'https://www.diodes.com/datasheet/download/AP2112.pdf',
 'RAIO-RA8875-v12.pdf':'https://cdn-shop.adafruit.com/datasheets/RA8875_DS_V12_Eng.pdf',
 'ALPS-encoder-catalog.pdf':'https://tech.alpsalpine.com/assets/catalog/product-catalog-ec-all.en.pdf',
}
DEST.mkdir(parents=True,exist_ok=True)
for code in ['C50984','C247920','C49257','C22465876','C370986','C318884']:
    raw=json.loads((ROOT/f'evidence/catalog/{code}.json').read_text(encoding='utf-8'))
    SOURCES[code+'-supplier.pdf']=raw['result']['pdfUrl']
rows=[]
for name,url in SOURCES.items():
    target=DEST/name
    row={'file':name,'url':url}
    try:
        if target.exists():raw=target.read_bytes()
        else:
            with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as r:raw=r.read()
            assert raw.startswith(b'%PDF'),'Not a PDF response'
            target.write_bytes(raw)
        row.update(status='downloaded',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    except Exception as e:row.update(status='unavailable',error=str(e))
    rows.append(row);print(name,row['status'],flush=True);time.sleep(0.5)
(ROOT/'evidence/datasheet-manifest.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
