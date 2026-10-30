from pathlib import Path
import sys,csv,io,json,zipfile,hashlib
D=Path(__file__).resolve().parent;R=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else D.parents[2]
v=json.loads((D/'QUOTE-OPTION-CONTRACT.json').read_text(encoding='utf-8'));p=R/v['frozen_archive_relative_to_repo'];assert hashlib.sha256(p.read_bytes()).hexdigest()==v['frozen_archive_sha256']
with zipfile.ZipFile(p) as z:b=z.read('control88-frozen-r2-20261029/manufacturing/Control88-R2-BOM.csv')
assert hashlib.sha256(b).hexdigest()==v['frozen_BOM_sha256']
old={r['Designator']:r for r in csv.DictReader(io.StringIO(b.decode('utf-8-sig')))}
raw=(D/'Control88-R2-ALT-C1591-QUOTE-ONLY.csv').read_bytes();assert hashlib.sha256(raw).hexdigest()==v['quote_BOM_sha256']
new={r['Designator']:r for r in csv.DictReader(io.StringIO(raw.decode('utf-8')))};assert old.keys()==new.keys() and len(old)==88
changed=[]
for ref,a in old.items():
 c=new[ref]
 if a==c:continue
 assert ref in v['changed_designators'] and a['LCSC']=='C14663' and a['MPN']=='CC0603KRX7R9BB104'
 assert c['LCSC']=='C1591' and c['MPN']=='CL10B104KB8NNNC'
 assert {k for k in a if a[k]!=c[k]}=={'LCSC','MPN'};changed.append(ref)
assert len(changed)==13 and set(changed)==set(v['changed_designators'])
assert not v['native_source_changed'] and not v['actual_substitution_performed'] and not v['manufacturing_release'] and not v['supplier_quote_received']
print(json.dumps({'status':'PASS_EXACT_13_ROW_QUOTE_OPTION','rows':88,'changed':13,'unchanged':75,'frozen_source_changed':False,'manufacturing_release':False}))
