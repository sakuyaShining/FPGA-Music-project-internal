"""Validate cost artifact identity/arithmetic, not product functionality."""
import csv
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT.parents[1]/'hardware/cost-survey-20261016'
manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((OUT/k).read_bytes()).hexdigest()==v for k,v in manifest.items())
rows=list(csv.DictReader((OUT/'component-cost-examples.csv').open(encoding='utf-8-sig')))
s=json.loads((OUT/'cost-summary.json').read_text(encoding='utf-8'))
for summary in s['component_summaries']:
 lines=[r for r in rows if r['variant']==summary['variant']]
 assert all(int(r['reference_purchase_qty'])>=int(r['fitted_qty']) for r in lines)
 assert len({r['lcsc'] for r in lines})==len(lines)
 assert not any(r['lcsc']=='C2858691' for r in lines)
 assert sum(D(r['purchase_reference_cny']) for r in lines)==D(str(summary['purchase_reference_cny']))
 assert any(r['lcsc']=='C779389' for r in lines)
 assert all(r['assumed_fx_cny_per_usd']=='7.2' for r in lines if r['source_currency']=='USD')
refs=list(csv.DictReader((OUT/'domestic-price-references.csv').open(encoding='utf-8-sig')))
assert len(refs)==18
assert all(r['currency']=='CNY' for r in refs)
assert next(r for r in refs if r['lcsc']=='C21190')['pieces_per_sales_increment']=='100'
assert next(r for r in rows if r['variant']=='26-slot-example' and r['lcsc']=='C779389')['reference_purchase_qty']=='85'
result=dict(status='PASS within artifact identity/arithmetic only',domestic_references=len(refs),
 manifest_files=len(manifest),cost_rows=len(rows),source_code_changed=False,product_validation=False)
(ROOT/'evidence/artifact-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
