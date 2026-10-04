import io
import os
import re
import sys
import zipfile

base = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(base, 'pdfs', 'template_general_2025.zip')
dst = os.path.join(base, 'txt', 'template_general_2025.txt')

z = zipfile.ZipFile(src)
xml = z.read('word/document.xml').decode('utf-8', 'ignore')

# paragraph split
paras = re.split(r'</w:p>', xml)
out = []
for p in paras:
    # keep text runs
    texts = re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, re.S)
    line = ''.join(texts)
    line = (line.replace('&amp;', '&').replace('&lt;', '<')
                .replace('&gt;', '>').replace('&quot;', '"').replace('&apos;', "'"))
    line = re.sub(r'\s+', ' ', line).strip()
    # detect heading style
    style = re.search(r'<w:pStyle w:val="([^"]+)"', p)
    if line:
        tag = '[%s] ' % style.group(1) if style else ''
        out.append(tag + line)

with io.open(dst, 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))

print('lines:', len(out))
print('saved:', dst)
