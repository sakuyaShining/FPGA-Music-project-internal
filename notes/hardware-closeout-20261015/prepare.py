"""Download primary references and render schematic pages for read-only review."""
import datetime
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parent
EVIDENCE=ROOT/'evidence'
EVIDENCE.mkdir(exist_ok=True)
targets={
 'nano20k-3921-rev130':'https://dl.sipeed.com/fileList/TANG/Nano_20K/2_Schematic/Tang_Nano_20K_3921_Schematics.pdf',
 'waveshare-30896-schematic':'https://files.waveshare.com/wiki/3.5inch%20RPi%20LCD%20%28F%29/3.5inch_RPi_LCD_%28F%29.pdf',
 'nexperia-esd':'https://assets.nexperia.com/documents/data-sheet/PESD3V3U1UA_UB_UL.pdf',
}
rows=[]
for label,url in targets.items():
    row={'label':label,'url':url,'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        with urllib.request.urlopen(url,timeout=25) as response:raw=response.read();row['status_code']=response.status
        if not raw.startswith(b'%PDF-'):raise ValueError('Not PDF')
        (EVIDENCE/(label+'.pdf')).write_bytes(raw)
        row.update(status='downloaded',sha256=hashlib.sha256(raw).hexdigest())
    except Exception as exc:row.update(status='failed',error=str(exc))
    rows.append(row)
    print(json.dumps(row),flush=True)
(EVIDENCE/'primary-references.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')

from pypdf import PdfReader
import pypdfium2
for label,pages in [('nano20k-3921-rev130',[1,4]),('waveshare-30896-schematic',[0])]:
    path=EVIDENCE/(label+'.pdf')
    if not path.exists():continue
    reader=PdfReader(path)
    (EVIDENCE/(label+'.txt')).write_text('\n'.join(p.extract_text(extraction_mode='layout') or '' for p in reader.pages),encoding='utf-8')
    doc=pypdfium2.PdfDocument(path)
    for num in pages:
        doc[num].render(scale=2.5).to_pil().save(EVIDENCE/(label+f'-p{num+1}.png'))
print('Primary schematic pages rendered; interpretation/qualification still pending.')
