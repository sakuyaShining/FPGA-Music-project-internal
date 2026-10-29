from pathlib import Path
import json
def documents(path):
    docs = []
    current = None
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        h, v = line.split('||', 1)
        h = json.loads(h)
        v = v[:-1] if v.endswith('|') else v
        if not v.strip():
            continue
        v = json.loads(v)
        if h['type'] == 'DOCHEAD':
            current = {'head': v, 'records': []}
            docs.append(current)
        if current is None:
            raise ValueError('Record before DOCHEAD on line ' + str(number))
        current['records'].append((h, v))
    return docs
