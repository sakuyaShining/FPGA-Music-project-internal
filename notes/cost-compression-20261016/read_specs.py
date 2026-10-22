from concurrent.futures import ThreadPoolExecutor
import hashlib, json, urllib.request
from pathlib import Path
from pypdf import PdfReader
import pypdfium2 as pdfium

E=Path(__file__).resolve().parent/'evidence'
sources={
 'C2841426':'https://atta.szlcsc.com/upload/public/pdf/source/20210623/C2841426_3BD48A1F2533C69C8EEEB2CADAAA6EED.pdf',
 'C179326':'https://assets.nexperia.com/documents/data-sheet/74HC_HCT4067.pdf',
}
def run(item):
 code,url=item
 try:
  with urllib.request.urlopen(url,timeout=25) as response: raw=response.read()
  assert raw.startswith(b'%PDF'), 'Not PDF'
  path=E/(code+'.pdf');path.write_bytes(raw)
  reader=PdfReader(path)
  (E/(code+'-text.txt')).write_text('\n\n'.join('PAGE %d\n%s'%(i+1,p.extract_text()) for i,p in enumerate(reader.pages)),encoding='utf-8')
  if code=='C2841426':
   doc=pdfium.PdfDocument(str(path))
   for i in range(len(doc)):
    doc[i].render(scale=1.5).to_pil().save(E/('%s-page-%d.png'%(code,i+1)))
  return dict(code=code,url=url,pages=len(reader.pages),sha256=hashlib.sha256(raw).hexdigest(),status='downloaded_extracted')
 except Exception as exc:return dict(code=code,url=url,error=str(exc),status='unverified')
with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(run,sources.items()))
(E/'spec-sources.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results))
