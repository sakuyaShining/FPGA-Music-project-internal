"""Make a readable drawing-only derivative of the native default PDF.

The raw eight-page export is retained. Its flat BOM pages have encoding/column
overflow defects; the authoritative BOM remains the native CSV. No PCB geometry
is changed in this derivative, and content streams are checked byte for byte.
"""
import hashlib
import json
from pathlib import Path
from pypdf import PdfReader,PdfWriter
from native_review import ROOT

out=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')
source=out/'qa-0clear-149open/native-default-8pages-RAW.pdf';reader=PdfReader(source)
assert len(reader.pages)==8
pages=[0,5,6,7];writer=PdfWriter()
for i in pages:writer.add_page(reader.pages[i])
writer.add_metadata({'/Title':'PCB review candidate - 0 clearance errors, 149 open objects - NOT FOR ORDER',
                     '/Subject':'Native drawing pages only. Raw export and BOM CSV retained separately.'})
target=out/'pcb-reviewed-pages-0clear-149open-CANDIDATE.pdf'
with target.open('wb') as f:writer.write(f)
derived=PdfReader(target)
assert all(reader.pages[i].get_contents().get_data()==derived.pages[j].get_contents().get_data() for j,i in enumerate(pages))
audit={'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
       'review_pdf':str(target),'review_pdf_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
       'source_pages_1based':[i+1 for i in pages],'drawing_content_streams_unchanged':True,
       'omitted':'Blank bottom assembly and native flat BOM table with encoding/overflow defects; native BOM CSV is separate',
       'visual_qa':'pending_derivative_render','manufacturing_release':False}
(ROOT/'checkpoint149-pdf-qa.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print(json.dumps(audit,indent=2),flush=True)
