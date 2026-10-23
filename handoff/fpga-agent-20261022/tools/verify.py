"""Read-only verification of every packaged file. No synthesis/programming."""
from pathlib import Path
import hashlib,json,sys

def verify(root):
    root=Path(root).resolve();manifest=json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
    failures=[]
    for rel,v in manifest['files'].items():
        p=root/rel
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=v['sha256']:failures.append(rel)
    if failures:raise RuntimeError('Package identity mismatch: '+repr(failures))
    return manifest

if __name__=='__main__':
    root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
    m=verify(root);print(json.dumps(dict(status='PASS package identities only',files=len(m['files']),package=str(root))))
