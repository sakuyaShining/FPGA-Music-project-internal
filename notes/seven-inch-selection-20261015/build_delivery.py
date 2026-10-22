"""Build seven-inch sourcing comparison and dimensioned concept, not fabrication data."""
import csv
import hashlib
import html
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PROJECT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=PROJECT/'hardware/seven-inch-selection-20261015'
OUT.mkdir(parents=True,exist_ok=True)

sources=[
 {'id':'mrb','url':'https://www.lcdwiki.com/zh/7.0inch_16BIT_Module_SSD1963','scope':'MRB7966, SSD1963, GT911, 16-bit 8080, 800x480, AA/PCB dimensions, 5V/3.3V, 2.03W'},
 {'id':'mrb-schematic','url':'https://www.lcdwiki.com/res/MRB7963/7inch_SSD1963_display_Schematic.pdf','scope':'Vendor schematic, 16-bit bus and separate touch I2C; actual supplied board revision still unknown'},
 {'id':'er','url':'https://www.buydisplay.com/chinese/7-inch-lcd-module-capacitive-touch-screen-panel-i2c-spi-serial','scope':'Indexed manufacturer base price CNY273.22; configurable interface/touch; NOT capacitive configuration quote; direct fetch 403'},
 {'id':'er-drawing','url':'https://www.buydisplay.com/download/manual/ER-TFTM070-5V4_Datasheet.pdf','scope':'Manufacturer mechanical/interface datasheet; direct web fetch error, indexed drawing used only as reference'},
 {'id':'surenoo','url':'https://www.surenoo.com/products/23163813','scope':'SSP0700A-800480: LT7686, FT5426 in detailed table, 185x105x7.98mm, 5V, SPI and I2C; header typo GT5426; availability/price not qualified'},
 {'id':'ronbo','url':'https://www.ronboe.com/shop/msp7001/','scope':'MSP7001: 7inch 800x480, 185x105mm, 5V/3.3V, SPI, USD30 public price; controller and touch part absent; 3/4-wire descriptions conflict'},
 {'id':'maclight','url':'https://www.szmaclight.com/product/7-inch-spi-tft-lcd-800480-i2c-ctp.html','scope':'7inch LT7680 SPI+I2C five-point module architecture, lacks exact MPN/dimensions/price'},
 {'id':'hdmi-domestic','url':'https://item.szlcsc.com/334768.html','scope':'Exact C359951 identity; public payload valid stock1; single-unit package reference CNY239.40, not checkout quote'},
 {'id':'hdmi-vendor','url':'https://www.waveshare.com/product/raspberry-pi/7inch-hdmi-lcd-c.htm','scope':'1024x600, HDMI display, five-point USB capacitive touch'},
 {'id':'lt-domestic','url':'https://item.szlcsc.com/5791065.html','scope':'LT7680A-R/C5156687 identity; discontinued at this distributor, stock0; do not freeze for purchase'},
 {'id':'lt-manual','url':'https://www.levetop.cn/uploadfiles/2023/05/LT7680x-R_DS_V30_CH.pdf','scope':'LT7680x-R family; A supports 1280x1024 while B only480x320; not interchangeable for800x480'},
 {'id':'pcm5122','url':'https://item.szlcsc.com/1043162.html','scope':'PCM5122PWR/C962071 exact identity stock456; small-quantity price/PLL qualification pending'},
 {'id':'pt8211','url':'https://item.szlcsc.com/93193.html','scope':'PT8211-S/C92004 exact identity stock1; price/justified format and analog circuit qualification pending'},
]

candidates=[
 dict(candidate='MSP7001',maker='RONBO',size_in=7,resolution='800x480',display='SPI, description conflicts 3/4-wire',touch='capacitive; exact IC/points not specified',controller='not specified',pcb_mm='185x105',lcsc='',price_cny='',price_reference='USD30 public vendor; not domestic landed quote',status='priority low-cost inquiry lead, not qualified',gap='controller model/registers/GRAM/geometry, exact CTP IC/points, pinout, 3.3V signals, CNY quote'),
 dict(candidate='MRB7966',maker='LCDWIKI',size_in=7,resolution='800x480',display='16-bit 8080',touch='GT911, I2C',controller='SSD1963',pcb_mm='181x108',lcsc='',price_cny='',price_reference='unknown',status='cost comparison candidate, interface redesign needed',gap='domestic quote; serial-parallel bridge or pin replan; touch latency; installed board revision'),
 dict(candidate='ER-TFTM070-5V4, capacitive+4-wire SPI configuration',maker='EastRising',size_in=7,resolution='800x480',display='configurable, select 4-wire SPI',touch='optional FT5316 capacitive',controller='RA8875',pcb_mm='180x104 product table; revision drawing varies',lcsc='',price_cny='',price_reference='CNY273.22 BASE indexed; capacitive add-on not included/confirmed',status='documented SPI technical fallback, cost warning',gap='complete configuration CNY quote/stock, exact revision drawing, signal/FIFO timing and touch qualification'),
 dict(candidate='SSP0700A-800480 CTP',maker='Surenoo',size_in=7,resolution='800x480',display='SPI, module names 3-wire yet separate MOSI/MISO',touch='FT5426 I2C detailed table; header GT5426 typo',controller='LT7686',pcb_mm='185x105x7.98',lcsc='',price_cny='',price_reference='foreign indexed USD54.99 not exact-variant domestic quote',status='technical reference, not cost-qualified',gap='exact CTP bill, points/report timing, stock, CNY quote, signaling details'),
 dict(candidate='7inch HDMI LCD (C)',maker='Waveshare',size_in=7,resolution='1024x600',display='HDMI',touch='USB five-point capacitive',controller='HDMI bridge, not direct SPI',pcb_mm='verify exact revision',lcsc='C359951',price_cny='',price_reference='CNY239.40 single-item PACKAGE reference, stock1; no checkout quote',status='not preferred due USB host/graphics resource cost',gap='USB host hardware/HID, HDMI resource/PnR, complete power/layout'),
 dict(candidate='7inch SPI/I2C CTP LT7680 module',maker='MACLIGHT',size_in=7,resolution='800x480',display='SPI',touch='I2C five-point capacitive',controller='LT7680 unspecified suffix',pcb_mm='not specified',lcsc='',price_cny='',price_reference='quote only',status='architecture lead only',gap='exact MPN/suffix, dimension/interface drawing, CNY small-quantity quote'),
]
budget=[
 ('7inch screen + CTP + controller + supplied cable',200),
 ('left sensor front-end / logic / qualified protection / passives',60),
 ('electrode PCB and carrier prototype manufacture / assembly',65),
 ('AUX DAC / jack / analog passives',25),
 ('microSDHC card',25),
 ('preset / Edit / encoder / headers / connectors',30),
 ('power supply / power path / cables',25),
 ('panel / cover film / fasteners / simple supports',35),
 ('freight / contingency',35),
]
assert sum(v for _,v in budget)==500

def csv_write(name,rows):
 with (OUT/name).open('w',newline='',encoding='utf-8-sig') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
csv_write('screen-candidates.csv',candidates)
csv_write('budget-targets.csv',[dict(item=k,target_cny=v,basis='allocation only, NOT verified price',status='讨论中') for k,v in budget])

native=[]
for p in sorted((HERE/'evidence').glob('native-*.json')):
 if p.name.endswith('.request.json'):continue
 d=json.loads(p.read_text(encoding='utf-8'))
 for q,items in d['value']['queries'].items():
  for x in items:
   if x.get('manufacturerId') in {'LT7680A-R','LT7683','LT7381','RA8875L3N','SSD1963QL9','SN74LV595APWR','PCM5122PWR','PCM5102APWR','PT8211-S','TM8211','CS4344-CZZR','MS4344','AT070TN92'}:
    native.append(dict(query=q,**{k:x.get(k) for k in ('manufacturer','manufacturerId','supplierId','uuid','libraryUuid','footprintName')}))
csv_write('native-identities.csv',native)
(OUT/'sources.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'domestic-snapshot.json').write_text((HERE/'evidence/domestic.json').read_text(encoding='utf-8'),encoding='utf-8')
calc=dict(status='讨论中; arithmetic only',screen=dict(width=800,height=480,bpp=16,aa_mm=[154.08,85.92],frame_bytes=800*480*2,
 ideal_full_frame_s_at_6_75MHz=800*480*16/6750000,ideal_raw_bit_s_20fps=800*480*16*20,
 eight_groups_example_pitch_mm=154.08/8,eight_groups_example_width_with_2mm_gaps=(154.08-7*2)/8),
 layout=dict(panel_mm=[470,220],left_example_slots_per_row=13,left_example_pitch_mm=18,left_example_strip_mm=[12,48],
 left_active_width_mm=12*18+12,left_two_row_active_height_mm=48*2+12,right_module_envelope_mm=[185,108],status='proposal, not endpoint count decision or drilling drawing'),
 budget=dict(total_target_cny=500,display_target_cny=200,other_allocations_cny=300,
 hdmi_reference_plus_other_allocations_cny=239.4+300,er_BASE_reference_plus_other_allocations_cny=273.22+300,
 note='These sums use allocations, not complete quotations; ER excludes unconfirmed capacitive add-on.'))
(OUT/'calculations.json').write_text(json.dumps(calc,ensure_ascii=False,indent=2),encoding='utf-8')

# Dimensioned, to-scale concept PNG. One panel millimetre equals three pixels.
S=3;W,H=1530,1000
im=Image.new('RGB',(W,H),'#f4f1e9');draw=ImageDraw.Draw(im)
font_path='C:/Windows/Fonts/msyh.ttc'
def f(size):return ImageFont.truetype(font_path,size)
def txt(x,y,t,size=21,color='#26343c'):draw.text((x,y),t,font=f(size),fill=color)
def box(x,y,w,h,fill,outline='#a9b4b5',radius=7):
 draw.rectangle((60+x*S,160+y*S,60+(x+w)*S,160+(y+h)*S),fill=fill,outline=outline)
txt(60,28,'7英寸泛音触控区 · 整机布局提案',34)
txt(60,84,'尺寸评估图｜约470×220 mm｜手指朝向图上方｜未冻结孔位、端点数与外壳',21)
box(0,0,470,220,'#e5e3db','#44515a',20)
box(15,10,84,57,'#bdcbd1')
box(22,16,64,48,'#1a303d')
txt(60+25*S,160+24*S,'已有可视化屏',19,'#edf7fa')
txt(60+27*S,160+40*S,'位置/边框示意',16,'#edf7fa')
for i in range(4):
 box(111+i*26,17,21,22,'#f7e4b0')
 txt(60+(117+i*26)*S,160+23*S,str(i+1),21)
box(218,17,26,22,'#f1d7c9');txt(60+221*S,160+23*S,'编辑',17)
draw.ellipse((60+261*S,160+17*S,60+283*S,160+39*S),fill='#e1b79a',outline='#946b52',width=2)
txt(60+259*S,160+43*S,'按压旋钮',17)
txt(60+310*S,160+20*S,'AUX / 电源 / USB / TF',19)
txt(60+310*S,160+34*S,'接口留在背缘；板卡置于下层',17)
box(15,70,234,121,'#eaf0ed')
for row in range(2):
 for col in range(13):
  box(18+col*18,76+row*60,12,48,'#74a89d' if col%3 else '#426e69')
txt(60+18*S,160+195*S,'两排逐音滑条：13格仅为空间容量示例',17)
box(111,52,138,11,'#cc9772')
txt(60+115*S,160+52*S,'八度选择条：仅选档，不测力',17)
box(267,76,185,108,'#bbc9ce')
ax=267+(185-154.08)/2;ay=76+(108-85.92)/2
box(ax,ay,154.08,85.92,'#112b38')
for i,bh in enumerate([32,18,42,26,51,38,22,33]):
 bx=ax+4+i*18.3
 box(bx,ay+10,14.8,61,'#1c414f',outline='#345f6b',radius=2)
 box(bx,ay+71-bh,14.8,bh,'#64b6a1',outline='#64b6a1',radius=2)
txt(60+300*S,160+80*S,'7英寸 · 泛音图形直接触控',18,'#fff5d5')
txt(60+285*S,160+187*S,'屏模组包络约185×108 mm',18)
txt(60+285*S,160+199*S,'8组仅作图示，交互分组尚未冻结',16)
draw.line((60,850,1470,850),fill='#4b646c',width=2)
draw.line((60,840,60,860),fill='#4b646c',width=2);draw.line((1470,840,1470,860),fill='#4b646c',width=2)
txt(700,860,'470 mm',21)
txt(60,913,'屏有效区约154×86 mm；左右演奏区预留隔离带。模组、排线、支撑高度须按最终版本复核。',20)
im.save(OUT/'layout.png')

readme='''# 七英寸选型增量（2026-10-15）

状态：**讨论中**，不是最终采购BOM/可制造PCB。用户新偏好为右手约7英寸，不再以2.8/3.5英寸为主方案。

- `screen-candidates.csv`：具体模组、接口、价格口径与未资格确认项。
- `native-identities.csv`：实际嘉立创EDA系统库搜索命中。库命中不等于商城库存/可购买。
- `budget-targets.csv`：合计500元的设计分配，所有行均非实际报价；保护、PCB和装配如超额必须重核整机。
- `calculations.json`：帧带宽、操作尺寸与预算算式，非性能实测。
- `layout.png`：470×220mm布局空间提案；不冻结13音位或8组泛音，不用于开孔/布板。小屏模组框仅留位。
- `sources.json`：商城和厂家来源。原始CLI请求/响应、公开HTML、失败原因在`notes/seven-inch-selection-20261015/evidence/`。
- `domestic-snapshot.json`：精确MPN/C号核对后的国内公开库存及整包参考价；`unit_price`保持空白。整包数量为1的C359951参考值可说明单件包装水平，仍非结算报价。

优先架构：7英寸800×480、直接I²C多点触摸、屏侧显存与图形命令、低引脚SPI连接。MSP7001是低成本追查线索，驱动IC/触摸规格缺失；ER-TFTM070-5V4电容＋SPI配置是资料较清楚的技术备选，273.22元仅基础配置价。MRB7966为并口比较路线，不能按SPI模组接线。未取得所有条件满足的500元完整报价，未购买。

LT7680A-R/C5156687国内已停售且库存0，不能因为原生库存在就写入已选采购件。C359951库存1/单件包装参考239.40元，但USB触摸需要主机支持，因此不作为当前首选。原设计17GPIO表不直接沿用到新屏。

源码/原理图未修改，现有工程前后哈希见evidence/after.json。主目录192输入身份检查不代表7英寸、触摸延迟、双屏或录放已验证。
'''
(OUT/'README.md').write_text(readme,encoding='utf-8')
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'}
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(out=str(OUT),candidates=len(candidates),native_matches=len(native),budget_target=sum(v for _,v in budget),files=len(manifest)),ensure_ascii=True))
