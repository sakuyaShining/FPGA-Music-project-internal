"""Generate explicit planning arithmetic and a physical-size comparison artifact."""
import csv
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
OUT=REPO/'hardware/right-touch/selection-20261015'
OUT.mkdir(parents=True,exist_ok=True)
ev=ROOT/'evidence'

native=json.loads((ev/'native-touch-system-library.json').read_text(encoding='utf-8'))['value']
assert any(x['manufacturerId']=='SN74LVC14ADR' and x['supplierId']=='C133541'
           for x in native['queries']['SN74LVC14ADR'])
dom=json.loads((ev/'DFR0669-domestic-public-data.json').read_text(encoding='utf-8'))
assert dom['productRecord']['productModel']=='DFR0669'
assert dom['productRecord']['productCode']=='C17641738'
retail=(ev/'DFR0669-domestic-manufacturer.html').read_text(encoding='utf-8')
price=re.search(r'data-stock="([^"]+)" data-price="([\d.]+)"',retail)
assert price
rows=[
 dict(priority='larger-area-candidate',mpn='3.5inch RPi LCD (F)',vendor='Waveshare',identity='SKU30896',
      lcd='ST7796S',touch='GT911',width=480,height=320,points=5,area_w_mm=73.44,area_h_mm=48.96,
      price_cny='',price_usd_reference=19.99,availability='domestic quote unknown',native_exact_matches='',
      decision='candidate; report latency and domestic price pending',url='https://www.waveshare.com/product/displays/lcd-oled/3.5inch-rpi-lcd-f.htm'),
 dict(priority='domestic-priced-reference',mpn='DFR0669',vendor='DFRobot',identity='C17641738',
      lcd='ILI9488',touch='GT911',width=480,height=320,points=5,area_w_mm=73.44,area_h_mm=48.96,
      price_cny=float(price[2]),price_usd_reference='',availability=f'mall stock {dom["productRecord"]["stockNumber"]}; manufacturer page {price[1]}',
      native_exact_matches=len(native['queries']['DFR0669']),decision='candidate; SPI RGB666 cost; report latency pending',
      url='https://www.dfrobot.com.cn/goods-2877.html'),
 dict(priority='compact-candidate',mpn='2.8inch Capacitive Touch LCD',vendor='Waveshare',identity='SKU27579',
      lcd='ST7789T3',touch='CST328',width=320,height=240,points=5,area_w_mm=57.60,area_h_mm=43.20,
      price_cny='',price_usd_reference=16.99,availability='domestic quote unknown',native_exact_matches=0,
      decision='candidate; ergonomic and report latency pending',url='https://www.waveshare.com/product/displays/lcd-oled/2.8inch-capacitive-touch-lcd.htm'),
]
for r in rows:
    r['latency_qualified']=False
    r['purchased']=False
    r['native_footprint_qualified']=False
    r['eight_columns_pitch_mm']=r['area_w_mm']/8
    r['sixteen_columns_pitch_mm']=r['area_w_mm']/16
with (OUT/'candidate-comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

plans=[]
for name,w,h,bpp in [('2.8_RGB565',320,240,2),('3.5_RGB565',480,320,2),('DFR0669_RGB666_3byte_planning',480,320,3)]:
    plans.append({'scenario':name,'pixels':w*h,'wire_bytes_per_pixel':bpp,'full_payload_bytes':w*h*bpp,
                  'ideal_full_transfer_ms_at_6_75MHz':w*h*bpp*8/6.75e6*1000,
                  'ideal_full_transfer_ms_at_10MHz':w*h*bpp*8/10e6*1000,
                  'scope':'payload arithmetic only; clocks/overhead/module timing not qualified'})
budget={'right_touch_display':170,'sensing_controls_eeprom_components':80,'prototype_and_final_pcbs':80,
        'assembly':35,'connectors_protection_passives_wires':35,'cover_and_mounting':20,
        'TF_card':30,'shipping':20,'reserve':30}
planning={'status':'discussion_not_quotation_or_release','budget_target_cny':500,'allocation_caps_cny':budget,
          'allocation_total_cny':sum(budget.values()),'DFR0669_manufacturer_list_price_cny':float(price[2]),
          'remaining_after_DFR0669_cny':500-float(price[2]),'display_payloads':plans,
          'GT911_read_model':{'bus_Hz':400000,'status_read_bytes_with_addresses':5,
             'five_point_read_bytes_with_addresses':44,'clear_status_write_bytes':4,
             'clock_count':(5+44+4)*9,'ideal_bus_ms':(5+44+4)*9/400000*1000,
             'exclusions':'START STOP bus free stretch arbitration sensor processing debounce audio output'},
          'GPIO_model':{'six_RC_lanes_one_touch_LCD_example':18,'second_LCD_independent_CS_DC_RST_extra':3,
                        'two_display_example_total':21,'scope':'logical budget only; not real Nano pin assignment'},
          'no_RTL_changes':True,'no_order':True}
assert sum(budget.values())==500
(OUT/'planning-calculations.json').write_text(json.dumps(planning,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# A4 canvas in millimeters. This illustrates physical geometry, not a frozen UI.
parts=['<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">',
 '<rect width="210" height="297" fill="white"/>',
 '<g font-family="Microsoft YaHei, sans-serif" fill="#14213d">',
 '<text x="12" y="15" font-size="5">右手泛音触控区：有效显示面积比较</text>',
 '<text x="12" y="24" font-size="3.2">A4按100%打印；示意8组，不冻结音乐映射或控件布局。</text>']
for y,title,w,h in [(39,'3.5英寸：73.44 × 48.96 mm',73.44,48.96),(110,'2.8英寸：57.60 × 43.20 mm',57.60,43.20),(177,'2.0英寸：40.8 × 30.6 mm（排查对照）',40.8,30.6)]:
    parts.append(f'<text x="12" y="{y}" font-size="4">{title}</text>')
    parts.append(f'<rect x="12" y="{y+5}" width="{w}" height="{h}" fill="#e9eef7" stroke="#14213d" stroke-width="0.3"/>')
    for i in range(8):
        bw=w/8
        x=12+i*bw
        parts.append(f'<line x1="{x}" y1="{y+5}" x2="{x}" y2="{y+5+h}" stroke="#9daac0" stroke-width="0.15"/>')
        bh=h*(0.25+(i%4)*0.13)
        parts.append(f'<rect x="{x+bw*.2}" y="{y+5+h-bh-3}" width="{bw*.6}" height="{bh}" rx="0.6" fill="#3878be"/>')
    parts.append(f'<text x="100" y="{y+15}" font-size="3.2">8等分：{w/8:.2f} mm/组</text>')
    parts.append(f'<text x="100" y="{y+23}" font-size="3.2">16等分：{w/16:.2f} mm/组</text>')
parts.extend(['<text x="12" y="236" font-size="3.2">多点数量不等于多指可舒适并排：需检查指腹遮挡、邻区误触和拖动。</text>',
 '<line x1="12" y1="252" x2="62" y2="252" stroke="#14213d" stroke-width="0.4"/>',
 '<line x1="12" y1="249" x2="12" y2="255" stroke="#14213d" stroke-width="0.4"/>',
 '<line x1="62" y1="249" x2="62" y2="255" stroke="#14213d" stroke-width="0.4"/>',
 '<text x="12" y="262" font-size="3.2">此线应为50mm，打印后用尺检查。</text>',
 '</g></svg>'])
(OUT/'touch-area-actual-size.svg').write_text('\n'.join(parts),encoding='utf-8')
manifest={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest()
          for p in list(OUT.iterdir())+list(ev.iterdir()) if p.is_file() and p.name!='evidence-manifest.json'}
(OUT/'evidence-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'candidate_count':len(rows),'budget_cap_total':sum(budget.values()),
                  'GT911_ideal_bus_ms':planning['GT911_read_model']['ideal_bus_ms'],
                  'output':str(OUT)},ensure_ascii=True))
