import json
from pathlib import Path
from PIL import Image, ImageDraw
from pypdf import PdfReader

DEST=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261019')
r=PdfReader(DEST/'dual-screen-review.pdf')
print('PDF pages',len(r.pages),'boxes',[(float(p.mediabox.width),float(p.mediabox.height)) for p in r.pages])
assert len(r.pages)==12
paths=sorted((DEST/'schematic-png').glob('*.png'))
assert len(paths)==12,len(paths)
canvas=Image.new('RGB',(2200,1800),'#e5e7eb');d=ImageDraw.Draw(canvas)
for i,p in enumerate(paths):
    im=Image.open(p).convert('RGB');im.thumbnail((530,550))
    x=(i%4)*550+(550-im.width)//2;y=(i//4)*600+30
    canvas.paste(im,(x,y));d.text(((i%4)*550+10,(i//4)*600+7),p.stem,fill='black')
canvas.save(DEST/'schematic-contact-sheet.png')
rendered=sorted(DEST.glob('pdf-page-*.png'))
assert len(rendered)==12
canvas=Image.new('RGB',(2200,1800),'#e5e7eb');d=ImageDraw.Draw(canvas)
for i,p in enumerate(rendered):
    im=Image.open(p).convert('RGB');im.thumbnail((530,550))
    x=(i%4)*550+(550-im.width)//2;y=(i//4)*600+30
    canvas.paste(im,(x,y));d.text(((i%4)*550+10,(i//4)*600+7),p.stem,fill='black')
canvas.save(DEST/'pdf-contact-sheet.png')
(DEST/'export-inspection.json').write_text(json.dumps({'pdf_pages':len(r.pages),'png_pages':len(paths),'visual_inspection':'pending'},indent=2)+'\n',encoding='utf-8')
