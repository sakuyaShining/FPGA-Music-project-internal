"""Build traceable reference costs; allocations and currency assumptions stay explicit."""
import csv
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1]
OUT=PROJECT/'hardware/cost-survey-20261016';OUT.mkdir(parents=True,exist_ok=True)
E=ROOT/'evidence'
D=Decimal
FX=D('7.2') # Planning parameter only; not a live exchange rate or domestic quote.
domestic=json.loads((E/'domestic-normalized.json').read_text(encoding='utf-8'))
bom=list(csv.DictReader((PROJECT/'hardware/system-candidate-20261015/system-bom-candidate.csv').open(encoding='utf-8-sig')))
by_code={r['lcsc']:r for r in domestic}

global_prices=[
 dict(code='C496123',mpn='CD74HC4067M96',minimum=1,multiple=1,tiers=[(1,'0.6635'),(10,'0.5617'),(30,'0.4895')],url='https://www.lcsc.com/product-detail/C496123.html'),
 dict(code='C133541',mpn='SN74LVC14ADR',minimum=5,multiple=5,tiers=[(5,'0.2514'),(50,'0.1951')],url='https://www.lcsc.com/product-detail/C133541.html'),
 dict(code='C205940',mpn='SN74LV595ADR',minimum=1,multiple=1,tiers=[(1,'0.519'),(10,'0.4106')],url='https://www.lcsc.com/product-detail/C205940.html'),
 dict(code='C273656',mpn='SN74LV165ADR',minimum=5,multiple=5,tiers=[(5,'0.3486'),(50,'0.271')],url='https://www.lcsc.com/product-detail/Shift-Registers_Texas-Instruments-SN74LV165ADR_C273656.html'),
 dict(code='C779389',mpn='TPD1E01B04DPYR',minimum=5,multiple=5,tiers=[(5,'0.1039'),(50,'0.0814'),(150,'0.0701')],url='https://www.lcsc.com/product-detail/C779389.html'),
 dict(code='C411625',mpn='24LC256-I/SN',minimum=1,multiple=1,tiers=[(1,'0.768'),(10,'0.6269')],url='https://www.lcsc.com/product-detail/C411625.html'),
 dict(code='C470754',mpn='EC11E15244B2',minimum=1,multiple=1,tiers=[(1,'2.398'),(10,'2.0613')],url='https://www.lcsc.com/product-detail/C470754.html'),
 dict(code='C92004',mpn='PT8211-S',minimum=1,multiple=1,tiers=[(1,'0.6865'),(10,'0.5518')],url='https://www.lcsc.com/product-detail/C92004.html'),
 dict(code='C962071',mpn='PCM5122PWR',minimum=1,multiple=1,tiers=[(1,'3.2564'),(10,'2.7762')],url='https://www.lcsc.com/product-detail/C962071.html'),
]
global_map={x['code']:x for x in global_prices}
for x in global_prices:x.update(currency='USD',checked_date='2026-10-16',basis='Public distributor webpage quantity ladder; NOT domestic CNY price',checkout_verified=False)
(OUT/'international-price-ladders.json').write_text(json.dumps(global_prices,ensure_ascii=False,indent=2),encoding='utf-8')

def write_csv(name,rows):
 with (OUT/name).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def money(x):return float(x.quantize(D('.0001')))

price_rows=[]
for r in domestic:
 if r['status']!='identity_checked':continue
 offer=r['structured_offers'][0];s=r['sales_fields']
 price_rows.append(dict(lcsc=r['lcsc'],mpn=r['mpn'],currency='CNY',public_offer_per_piece=offer['price'],
   pieces_per_sales_increment=s['theRatio'],min_sales_units=s['minBuyNumber'],
   piece_stock=s['stockNumber'],complete_sales_units_stock=s['validStockNumber'],
   package_quantity=r['package_qty'],package_reference_total=r['package_ref_cny'],
   price_basis='Public JSON-LD Offer; applicable quantity tier/checkout unknown; not package total',
   qualified_for_purchase='NO, selection and checkout pending',url=r['url']))
write_csv('domestic-price-references.csv',price_rows)

# Keep the 80- and 83-electrode examples as two quantities, without choosing endpoints.
cost_rows=[];summaries=[]
for variant,column in [('25-slot-example','full_25_example_qty'),('26-slot-example','full_26_example_qty')]:
 subtotal=D(0);fitted=D(0)
 for b in bom:
  code=b['lcsc'];n=int(b[column] or 0)
  if not n or not code or code=='C2858691':continue # mutually exclusive and unqualified cheaper ESD
  if code in by_code and by_code[code]['status']=='identity_checked':
   d=by_code[code];s=d['sales_fields'];increment=int(s['theRatio'] or 1)
   min_n=int(s['minBuyNumber'] or 1)*increment
   q=max(min_n,((n+increment-1)//increment)*increment)
   p=D(str(d['structured_offers'][0]['price']));currency='CNY';unit_est=p
   basis='Domestic public Offer reference; quantity tier unconfirmed';url=d['url']
  elif code in global_map:
   g=global_map[code];increment=g['multiple'];q=max(g['minimum'],((n+increment-1)//increment)*increment)
   # Pick highest applicable ladder quantity, even for non-monotone future data.
   p=D(max(((tier,price) for tier,price in g['tiers'] if tier<=q),key=lambda t:t[0])[1])
   currency='USD';unit_est=p*FX;basis='International ladder converted at ASSUMED 7.2 CNY/USD; NOT domestic quote';url=g['url']
  else:continue
  purchase=q*unit_est;fitted_line=n*unit_est;subtotal+=purchase;fitted+=fitted_line
  cost_rows.append(dict(variant=variant,role=b['role'],lcsc=code,mpn=b['mpn'],fitted_qty=n,
   reference_purchase_qty=q,source_currency=currency,source_reference_unit=money(p),
   assumed_fx_cny_per_usd=7.2 if currency=='USD' else '',
   fitted_reference_cny=money(fitted_line),purchase_reference_cny=money(purchase),basis=basis,url=url))
 summaries.append(dict(variant=variant,fitted_reference_cny=money(fitted),purchase_reference_cny=money(subtotal),
  note='Partial electronics only: front-end/protection/EEPROM/encoder/buttons; no PCB/assembly/connectors/screens/audio/TF/power/structure/shipping. Mixed public references; not a quote.'))
write_csv('component-cost-examples.csv',cost_rows)

# Explicit unquoted reserves. These are scenario choices, not purported market ranges.
reserves=[
 ('headers, jacks except AUX, interconnects, knob/button caps',20),
 ('AUX complete branch incl DAC, jack, filtering/decoupling',30),
 ('16/32GB SDHC card',25),
 ('5V power source/cable/power path',45),
 ('PCB batches + selective assembly',100),
 ('simple panel/support/film/fasteners',40),
 ('shipping',30),
 ('contingency',25),
]
write_csv('unquoted-reserves.csv',[dict(item=k,reserve_cny=v,basis='Unquoted planning reserve; not supplier price',status='讨论中') for k,v in reserves])
non_screen=D(str(summaries[1]['purchase_reference_cny']))+sum(D(v) for _,v in reserves)
screens=[
 dict(mpn='MRB7966 capacitive',currency='USD',public_price=25,url='https://ronboelectronics.en.made-in-china.com/product/EGsYBOzMESWH/China-7-0-Inch-800X480-MCU-Parallel-Port-Capacitive-Touch-LCD-Display-with-SSD1963-Driver-Board.html',basis='Manufacturer sample EXW; freight/tax/serial-parallel adaptation not included',screen_scenario_cny=180),
 dict(mpn='MSP7001 capacitive',currency='USD',public_price=30,url='https://www.ronboe.com/shop/msp7001/',basis='Public vendor price; no domestic landed quote; controller/points qualification pending',screen_scenario_cny=216),
 dict(mpn='ER-TFTM070-5V4 BASE',currency='CNY',public_price=273.22,url='https://www.buydisplay.com/chinese/7-inch-lcd-module-capacitive-touch-screen-panel-i2c-spi-serial',basis='Indexed BASE only; CTP selected add-on unquoted; do not count as complete capacitive module',screen_scenario_cny=273.22),
 dict(mpn='7inch HDMI LCD (C) / C359951',currency='CNY',public_price=239.4,url='https://item.szlcsc.com/334768.html',basis='Domestic public Offer; USB host/HDMI integration unbudgeted; not preferred',screen_scenario_cny=239.4),
]
for x in screens:
 x['total_scenario_cny']=money(non_screen+D(str(x['screen_scenario_cny'])))
 x['fx_note']='USD entries use assumed7.2, not actual domestic quotation'
write_csv('screen-cost-scenarios.csv',screens)

output=dict(date='2026-10-16',status='讨论中; read-only cost investigation',assumed_fx=7.2,
 fx_is_live=False,domestic_references=len(price_rows),international_ladders=len(global_prices),
 component_summaries=summaries,unquoted_reserves_total=sum(v for _,v in reserves),
 non_screen_scenario_cny=money(non_screen),screen_ceiling_to_meet_500_in_this_scenario_cny=money(D(500)-non_screen),
 screen_scenarios=screens,
 pcb_material_arithmetic_only=dict(rate_reference_cny_per_m2=410,rate_notice_date='2026-09-21',
  left_example_mm=[234,108],left_example_batch_qty=5,left_area_charge_only=51.8076,
  carrier_example_mm=[100,80],carrier_example_batch_qty=5,carrier_area_charge_only=16.4,
  note='NOT PCB quote: engineering/minimum/SMT/shipping/tax/special process excluded; final board dimensions not frozen'),
 esd_reference=dict(fitted_80_buy_80_usd=6.512,fitted_83_buy_85_usd=6.919,
   cny_80_at_assumed_fx=46.8864,cny_85_at_assumed_fx=49.8168,
   cheaper_TP_reference_unit_cny=.1692,cheaper_TP_90_reference_cny=15.228,
   cheaper_TP_qualified=False,note='TP package/electrical/quantity-tier still unresolved; NOT approved replacement'))
(OUT/'cost-summary.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'README.md').write_text('''# 成本调查 · 2026-10-16

状态：**讨论中**。价格记录范围内已核对，非整机已报价或可制造签收。

- domestic-price-references.csv：18条国内公开报价参考；JSON-LD Offer是每颗参考，整包价另列，所需数量档位/结算未确认。
- international-price-ladders.json：9条LCSC国际站公开USD阶梯价；不得直接当人民币商城价。
- component-cost-examples.csv：两种端点数量例的装机用料/最小包装采购分别计算。USD统一以**假设7.2**作成本情景，非实时汇率；保留来源币种。
- unquoted-reserves.csv：未报价项目的预留金额。只是情景，不称市场调查所得区间。
- screen-cost-scenarios.csv / cost-summary.json：屏幕参考价、接口代价和可追溯算式。保留7英寸，未因成本裁定交互或采购替代。

原始公开HTML/JSON-LD、数量单位、时间与访问失败保留在notes/cost-survey-20261016/evidence/。API原始尝试403，没有取得价格；未绕过登录/验证码，改用可公开读取商品页与网页检索。国际站和国内库存分开。

重要：theRatio=100表示一个最小销售增量100颗；validStockNumber按销售增量计，stockNumber/结构化库存按颗计，不能混用。价格来源公开但不是结算报价；最终还需数量阶梯、SMT最小数/损耗、实际屏幕版本和制造文件。

没有改引擎、原理图、旧BOM或旧快照，没有下单。完整结论见63号文档。
''',encoding='utf-8')
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'}
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(component_summaries=summaries,non_screen=money(non_screen),scenario_totals=[(x['mpn'],x['total_scenario_cny']) for x in screens]),ensure_ascii=False,indent=2))
