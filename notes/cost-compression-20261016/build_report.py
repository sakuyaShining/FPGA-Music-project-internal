"""Generate conditional procurement examples; never an order or qualification."""
import csv, hashlib, json
from decimal import Decimal as D
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]
OUT=PROJECT/'hardware/cost-compression-20261016'
OUT.mkdir(parents=True,exist_ok=True)
old=list(csv.DictReader((PROJECT/'hardware/cost-survey-20261016/component-cost-examples.csv').open(encoding='utf-8-sig')))
refs=json.loads((ROOT/'evidence/domestic-candidates.json').read_text(encoding='utf-8'))
ref={r['code']:r for r in refs}
for c in ('C179326','C2841426'):
 assert ref[c]['status']=='identity_checked' and ref[c]['stock_pieces']>0
 assert ref[c]['offers'][0]['priceCurrency']=='CNY'
def csvwrite(name,rows):
 with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
rows=[];summary=[]
for variant in ('25-slot-example','26-slot-example'):
 base=[r for r in old if r['variant']==variant]
 before=sum(D(r['purchase_reference_cny']) for r in base)
 replaced=sum(D(r['purchase_reference_cny']) for r in base if r['lcsc'] in ('C496123','C779389'))
 for r in base:
  if r['lcsc'] in ('C496123','C779389'):continue
  rows.append(dict(variant=variant,role=r['role'],lcsc=r['lcsc'],mpn=r['mpn'],fitted_qty=r['fitted_qty'],purchase_qty=r['reference_purchase_qty'],reference_currency=r['source_currency'],reference_unit=r['source_reference_unit'],assumed_fx=r['assumed_fx_cny_per_usd'],purchase_reference_cny=r['purchase_reference_cny'],qualification='Prior candidate; original qualification remains pending',price_basis=r['basis'],url=r['url']))
 # Keep ESD channels local to each pitch row and octave area:
 # 25 slots: 12*3 + 13*3 + 5 => ceil/4 sums 9+10+2=21 arrays.
 # 26 slots: 13*3 + 13*3 + 5 => 10+10+2=22 arrays.
 # Both buy25 due to sales increment5. No final endpoint/node-count freeze.
 arrays=21 if variant.startswith('25') else 22
 for code,role,fitted,buy in [('C179326','16:1 RC sensing multiplexer',6,6),('C2841426','4-channel electrode ESD; local row grouping',arrays,25)]:
  r=ref[code];price=D(str(r['offers'][0]['price']))
  assert buy%int(r['sale_increment'])==0
  rows.append(dict(variant=variant,role=role,lcsc=code,mpn=r['mpn'],fitted_qty=fitted,purchase_qty=buy,reference_currency='CNY',reference_unit=str(price),assumed_fx='',purchase_reference_cny=str(price*buy),qualification='讨论中; footprint/RC/leakage/crosstalk/ESD validation pending',price_basis='Domestic public JSON-LD Offer; applicable quantity tier/checkout unconfirmed',url=r['url']))
 after=sum(D(r['purchase_reference_cny']) for r in rows if r['variant']==variant)
 assert before-replaced+D('1.49')*6+D('.3392')*25==after
 summary.append(dict(variant=variant,old_partial_purchase_cny=str(before),new_conditional_partial_purchase_cny=str(after),potential_reference_reduction_cny=str(before-after),esd_fitted_arrays=arrays,esd_purchase_arrays=25))
csvwrite('conditional-component-bom.csv',rows)
scenarios=[]
for screen in (180,216,D('273.22')):
 for bridge in (0,20):
  value=D(summary[1]['new_conditional_partial_purchase_cny'])+D('315')+D(str(screen))+D(str(bridge))
  scenarios.append(dict(screen_reference_cny=str(screen),additional_interface_allowance_cny=str(bridge),conditional_total_cny=str(value),remaining_reduction_to_500_cny=str(value-D('500')),basis='Not a landed quote; unchanged315 unquoted reserves; screen USD conversions use assumed7.2; interface20 is sensitivity only'))
csvwrite('budget-sensitivity.csv',scenarios)
result=dict(date='2026-10-16',status='讨论中',product_code_changed=False,old_bom_changed=False,qualification_passed=False,order_placed=False,source_head='fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12',public_prices_are_quantity_confirmed=False,assumed_fx_cny_per_usd='7.2',fx_is_live=False,examples=summary,unchanged_unquoted_reserves_cny='315',scenarios=scenarios,assembly_user_decision='User can solder headers/buttons/ordinary SMD; small packages factory assembled',power_user_reports_available=True,power_reuse_confirmed=False,power_qualification='User reports available5V3A source; model/nameplate pending; do not deduct entire45 power/cable/path allowance')
(OUT/'calculation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ('domestic-candidates.json','spec-sources.json'):
 (OUT/name).write_bytes((ROOT/'evidence'/name).read_bytes())
print(json.dumps(dict(examples=summary,lowest_scenario=scenarios[0]),ensure_ascii=True))
