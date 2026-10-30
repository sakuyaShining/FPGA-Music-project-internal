from pathlib import Path
import hashlib,json,sys
root=Path(__file__).resolve().parent
m=json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
errors=[]
for n,v in m['files'].items():
 p=root/n
 if not p.is_file() or p.stat().st_size!=v['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=v['sha256']: errors.append(n)
actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p!=root/'MANIFEST.json' and '__pycache__' not in p.parts}
errors += sorted(actual-set(m['files']))
print(json.dumps({'status':'FAIL' if errors else 'PASS_INTEGRITY_ONLY_NOT_MANUFACTURING_RELEASE','checked_files':len(m['files']),'errors':errors},ensure_ascii=False))
sys.exit(bool(errors))
