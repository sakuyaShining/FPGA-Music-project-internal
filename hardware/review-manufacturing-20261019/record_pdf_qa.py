"""Record visual inspection of the saved checkpoint drawing derivatives."""
import hashlib
import json
import shutil
from native_review import ROOT
from pathlib import Path

out=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')
path=ROOT/'checkpoint149-pdf-qa.json'
audit=json.loads(path.read_text(encoding='utf-8'))
assert hashlib.sha256(Path(audit['review_pdf']).read_bytes()).hexdigest()==audit['review_pdf_sha256']
audit['visual_qa']='Drawing-only derivative: all four pages rendered at 1800 px and visually inspected; readable, no drawing clipping observed. Routing incomplete; this is not fabrication approval.'
audit['pad_review_pdf']={
    'path':str(out/'pcb-pad-placement-review.pdf'),
    'sha256':hashlib.sha256((out/'pcb-pad-placement-review.pdf').read_bytes()).hexdigest(),
    'pages':2,
    'visual_qa':'Both pages rendered and visually inspected, including enlarged page-2 footer. Counts and disclaimer readable. Pad extent boxes are not component bodies; ground pours omitted in this supplementary view.'}
audit['raw_native_pdf_qa']='Rejected for direct handover: flat BOM pages contain text encoding and column overflow defects. Original retained; native BOM CSV delivered separately.'
path.write_text(json.dumps(audit,indent=2),encoding='utf-8')
shutil.copy2(path,out/path.name)
print(json.dumps(audit,indent=2))
