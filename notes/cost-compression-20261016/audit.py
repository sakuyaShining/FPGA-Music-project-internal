"""Artifact-only verification. No product or electrical qualification."""
import csv, json, hashlib
from decimal import Decimal as D
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT.parents[1]/'hardware/cost-compression-20261016'
data=json.loads((OUT/'calculation.json').read_text(encoding='utf-8'))
rows=list(csv.DictReader((OUT/'conditional-component-bom.csv').open(encoding='utf-8-sig')))
refs=json.loads((OUT/'domestic-candidates.json').read_text(encoding='utf-8'))
for ref in refs:
 assert hashlib.sha256((ROOT/'evidence'/(ref['code']+'.html')).read_bytes()).hexdigest()==ref['sha256']
 assert ref['mpn'] in (ROOT/'evidence'/(ref['code']+'.html')).read_text(encoding='utf-8')
assert next(r for r in refs if r['code']=='C2992617')['stock_pieces']==0
for summary in data['examples']:
 parts=[r for r in rows if r['variant']==summary['variant']]
 assert sum(D(r['purchase_reference_cny']) for r in parts)==D(summary['new_conditional_partial_purchase_cny'])
 assert D(summary['old_partial_purchase_cny'])-D(summary['new_conditional_partial_purchase_cny'])==D(summary['potential_reference_reduction_cny'])
 assert not any(r['lcsc'] in ('C496123','C779389','C2992617') for r in parts)
 esd=next(r for r in parts if r['lcsc']=='C2841426')
 assert int(esd['purchase_qty'])==25 and int(esd['fitted_qty']) in (21,22)
 assert D(esd['reference_unit'])*D(esd['purchase_qty'])==D('8.4800')
for s in data['scenarios']:
 assert D('62.9049')+D('315')+D(s['screen_reference_cny'])+D(s['additional_interface_allowance_cny'])==D(s['conditional_total_cny'])
 assert D(s['conditional_total_cny'])-D('500')==D(s['remaining_reduction_to_500_cny'])
assert data['power_reuse_confirmed'] is False and data['qualification_passed'] is False
spec=json.loads((ROOT/'evidence/spec-sources.json').read_text(encoding='utf-8'))[0]
assert hashlib.sha256((ROOT/'evidence/C2841426.pdf').read_bytes()).hexdigest()==spec['sha256']
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
result=dict(status='PASS within artifact identity/arithmetic only',public_candidates=3,cost_rows=len(rows),qualification_passed=False,product_verified=False)
(ROOT/'evidence/artifact-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
