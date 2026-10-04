import os
import sys
import glob
import io

from pypdf import PdfReader

base = os.path.dirname(os.path.abspath(__file__))
pdfdir = os.path.join(base, 'pdfs')
outdir = os.path.join(base, 'txt')
os.makedirs(outdir, exist_ok=True)

for pdf in sorted(glob.glob(os.path.join(pdfdir, '*.pdf'))):
    name = os.path.splitext(os.path.basename(pdf))[0]
    try:
        reader = PdfReader(pdf)
        chunks = []
        for i, page in enumerate(reader.pages):
            try:
                t = page.extract_text() or ''
            except Exception as e:
                t = '[[extract error: %s]]' % e
            chunks.append('\n===== page %d =====\n%s' % (i + 1, t.strip()))
        text = '\n'.join(chunks)
        dest = os.path.join(outdir, name + '.txt')
        with io.open(dest, 'w', encoding='utf-8') as f:
            f.write(text)
        print('%-10s pages=%-4d chars=%d' % (name, len(reader.pages), len(text)))
    except Exception as e:
        print('%-10s FAILED: %s' % (name, e))
