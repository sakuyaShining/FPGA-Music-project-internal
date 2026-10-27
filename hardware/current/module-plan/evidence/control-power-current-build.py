from pathlib import Path
import json, datetime, hashlib
from decimal import Decimal

B=Path(r'D:\FPGA-Project\codex-deliverables\dual-screen-review-20261020-v2')
E=B/'module-plan-current-evidence'
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
now=datetime.datetime.now().astimezone().isoformat()
mapping_path=B/'purchase-preparation-20261021-r1/227件功能分块与混合方案映射-current.json'
m=read(mapping_path)
assert len(m['records'])==227 and all(r['function_retained'] for r in m['records'])
selected=[r for r in m['records'] if r['functional_block'] not in ['84路传感前端','PCM5122立体声音频','Nano20K插接']]
assert len(selected)==56

parts=[
 dict(reference='U10 alternative',MPN='24LC256-I/P',LCSC='C411624',url='https://item.szlcsc.com/403161.html',package='PDIP-8',needed=1,buy=1,MOQ=1,CNY_each='11.81',stock=52,availability_proof='Normal browser actual product price sidebar and screenshot, not just SMT-stock label'),
 dict(reference='U15 alternative',MPN='SN74LVC244AN',LCSC='C1548565',url='https://item.szlcsc.com/1639371.html',package='PDIP-20',needed=1,buy=1,MOQ=1,CNY_each='9.33',stock=77,availability_proof='Normal browser actual product price sidebar and screenshot'),
 dict(reference='Local decoupling candidate; allocate per original C10 and retained rail locations',MPN='CCT104KC6X7RF5FH5A0',LCSC='C2896145',url='https://item.szlcsc.com/3138694.html',package='TH P5mm;100nF±10%,50V,X7R',needed_for_two_IC_minimum=2,buy=10,MOQ=10,CNY_each='0.4142',stock=1830,PCBA_label_stock_separately=1880,availability_proof='Normal browser actual sidebar; PCBA1880 and retail1830 kept separate'),
 dict(reference='U10 socket candidate',MPN='DS1009-08AT1NX-0A2',LCSC='C72124',url='https://item.szlcsc.com/73233.html',package='DIP8,2.54mm pitch,7.62mm row',needed=1,buy=20,MOQ=20,CNY_each='0.2075',stock=10860,PCBA_label_stock_separately='14K+',availability_proof='Actual domestic search and product screenshot; minimum20 verified'),
 dict(reference='U15 socket candidate',MPN='DS1009-20AT1NX-0A2',LCSC='C72118',url='https://item.szlcsc.com/73227.html',package='DIP20,2.54mm pitch,7.62mm row',needed=1,buy=12,MOQ=12,CNY_each='0.356',stock=4428,PCBA_label_stock_separately=4694,availability_proof='Actual domestic search and product screenshot; minimum12 verified')
]
subtotal=Decimal(0)
for r in parts:
 r['line_CNY_exact']=str(Decimal(r['CNY_each'])*r['buy'])
 subtotal+=Decimal(r['line_CNY_exact'])
 r['prewelded_module']=False
 r['standalone_purchase_release']=False
assert subtotal==Decimal('33.7040')
power={
 'original_refs':['J13','F1','Q1','R66','U17','R67','R68','R69','R70','C37','C38','C32','C30','R73'],
 'original_topology':'5V_IN -> F1 PTC -> Q1 reverse-polarity protection -> TPS2553 active-high limiter ->5V_PERIPH; EN=3V3_IO. AP2112K U18 derives3V3_PERIPH separately. Preserve independent rail identities and off-state discharge/isolators.',
 'U17':'TPS2553DBVR C55266, NOT a regulator and NOT a generic3A supply',
 'R67_ohm':23700,'R67_tolerance_fraction':0.01,
 'source':'TI-TPS2553-SLVS841F.pdf','url':'https://www.ti.com/lit/ds/symlink/tps2553.pdf',
 'pdf_sha256':sha(E/'TI-TPS2553-SLVS841F.pdf'),
 'pages_visually_reviewed':[15,18],
 'equations_R_in_kohm_I_in_mA':{'min':'25230/R^1.016','nominal':'23950/R^0.977','max':'22980/R^0.94'},
 'current_limit_mA_including_R_tolerance':{'minimum':25230/(23.7*1.01)**1.016,'nominal':23950/23.7**0.977,'maximum':22980/(23.7*0.99)**0.94},
 'design_interpretation':'About1.00A minimum threshold, not1.5A or3A guaranteed for the original resistor setting. PTC, thermal, input droop and connector limits are additional constraints, not removed by this calculation.',
 'amplifier_power_case':'If R12U delivers its labelled2x2W total4W, even ideal5V conversion needs>=0.8A before speaker-amplifier losses and all other loads. Full screen/DAC/logic peak currents remain unknown; no actual overload claim or complete load budget accepted.',
 'proposal_only':'Do not silently add speaker-amplifier current to the original peripheral branch or enlarge R67/F1 thresholds. Compare a separately protected5V speaker branch or externally powered active speaker; exact supply/protection/harness/price and power-off behaviour must close first.',
 'physical_tests':'UNMEASURED','native_values_changed':False
}
exclusions=[
 {'candidate':'DFRobot DFR0565','url':'https://www.dfrobot.com.cn/goods-1826.html','listed_CNY':99,'actual_stock_and_Qingyuan_quote_verified':False,'primary_limit':'5V isolated supply output max150mA; manufacturer requires controller and module sides not shorted','decision':'Not a drop-in TCA9517/shared-common-ground peripheral replacement. Do not use its150mA output to power the screen/DAC branch.'},
 {'candidate':'Adafruit5159 TCA4307','url':'https://www.adafruit.com/product/5159','listed_USD':4.95,'domestic_landed_quote_verified':False,'primary_warning':'Manufacturer says power passes through the breakout; it is a bus buffer, not a power isolator. QT cables not included.','decision':'Do not connect the two original independent3.3V rails to the board as-is. Pullup/EN/supply-off analysis and actual pin/schematic evidence still required; no replacement accepted.'},
 {'candidate':'SN74AHC595N C2872436','url':'https://www.lcsc.com/product-detail/C2872436.html','visible_catalog_state':'Out of stock; reference price only','decision':'PDIP existence confirmed previously, but not ready procurement or accepted LV595A substitution.'}
]
rejected_searches=[
 {'query':'RDER71H104K0K1H03B','method':'lcsc skill search','actual_result':'C2746 KM476M450K25RR0VH2FP0 450V47uF electrolytic','decision':'Unrelated MPN and capacitor type; rejected, not priced as100nF X7R.'},
 {'query':'DIP-8 socket','method':'lcsc skill search','actual_result':'Digital transistor and inductors, no matching socket among4 shown','decision':'Rejected. Exact C72124/C72118 normal domestic page searches used instead; do not repeat these ineffective broad queries.'}
]
allocation=[]
for r in selected:
 ref=r['reference']
 route='Original function retained; exact preassembled realization/price/assembly still open'
 if ref=='U10': route='Same-device PDIP candidate C411624, original8pin map retained; physical assembly and full plan pending'
 elif ref=='U15': route='Same-family PDIP candidate C1548565, original20pin map retained; 3V3_PERIPH/isolation and full plan pending'
 elif ref=='C10': route='100nF X7R through-hole candidate C2896145 locally across EEPROM8/4, placement and assembly pending'
 elif r['functional_block']=='电源入口稳压与保护': route='Keep exact original protection function and threshold; no complete preassembled equivalent accepted'
 elif ref in ['U8','U9','U11','U14','U16','U18']: route='Existing SMT function has no qualified prewelded purchase item in bounded search; do not present barechip as module'
 allocation.append(dict(reference=ref,original_MPN=r['original_MPN'],original_LCSC=r['original_LCSC'],functional_block=r['functional_block'],role=r['role'],original_pin_nets=r['original_nets'],candidate_disposition=route,function_retained=True,fully_verified_module_coverage=False))
proof=read(E/'through-hole-same-device-interface-proof.json')
checkpoint=read(E/'audio-contract-checkpoint-current.json')
checks=[{'file':x['file'],'expected':x['actual'],'actual':sha(Path(x['file']))} for x in checkpoint['native_file_checks']]
assert all(x['expected']==x['actual'] for x in checks)
data=dict(at=now,status='56_FUNCTIONS_RETAINED_PARTIAL_PRICED_DIRECT_INSERT_CANDIDATE_NOT_FULL_PURCHASE_PLAN',scope_original_count=56,parts_with_domestic_current_price=parts,priced_subset_exact_CNY=str(subtotal),priced_subset_display_CNY='33.70',price_scope='All5lines including MOQ extras; excludes carrier/protoboard, local assembly, wires/headers, pullups, power/protection, all other subsystems and freight. A9CNY shipping-coupon label is not actual Qingyuan freight.',assembly_scope='These are loose through-hole parts, not preassembled modules. No user SMT soldering. A mechanical carrier and socket/cap assembly or actual vendor preweld service still required; do not silently expand user ability beyond headers/wires.',pin_maps=proof['original_nets'],same_device_electrical_proof='through-hole-same-device-interface-proof.json',EEPROM_contract=proof['EEPROM'],power_contract=power,not_accepted_modules=exclusions,rejected_keyword_results=rejected_searches,original56_allocation=allocation,native_file_checks=checks,all227functions_retained=True,complete_purchase_ready=False,whole_budget_CNY=None,orders_payments_messages=False,RTL_build_flash_changed=False,physical_tests='UNMEASURED')
save(E/'control-power-current-plan.json',data)
for r in m['records']:
 if r['reference'] in ['U10','U15','C10']:
  r['control_power_candidate_evidence']='module-plan-current-evidence/control-power-current-plan.json'
  r['exact_replacement_candidate']={'U10':'24LC256-I/P C411624 + exact8pin socket and local100nF','U15':'SN74LVC244AN C1548565 + exact20pin socket and local100nF; existing isolation retained','C10':'CCT104KC6X7RF5FH5A0 C2896145 TH100nF X7R'}[r['reference']]
  r['verification_status']='Same-device electrical/pin or100nF subfunction candidate + domestic price verified; not a complete preassembled purchasing release'
m['time']=now;m['control_power_reconciliation']=dict(evidence='module-plan-current-evidence/control-power-current-plan.json',original_scope=56,all_functions_retained=True,priced_subset_CNY='33.70',fully_verified_coverage_unchanged=True)
assert m['module_fully_verified_covered']==0 and not m['module_mapping_complete']
save(mapping_path,m)
lines=['# 控制、存储与电源保护当前核对','', '这是采购准备与接线核对，尚不是“购买后直接组装”的完整清单。保留原227功能；本文件展开其中56项控制/存储/接口/供电功能，不替代84路前端与音频文件。','', '## 本轮核到实际人民币价的直插候选','', '|器件|准确料号|所需/需买数量|网页单价|本行采购额|','|---|---|---:|---:|---:|']
for r in parts:
 lines.append(f"|{r['reference']}|[{r['MPN']} / {r['LCSC']}]({r['url']})|{r.get('needed',r.get('needed_for_two_IC_minimum'))}/{r['buy']}|{r['CNY_each']}元|{r['line_CNY_exact']}元|")
lines+=['','五行合计33.704元，按33.70元展示，已经计入插座/电容起订多买部分。尚缺载体、实际组装、导线/排针、上拉、电源隔离保护与运费；网页“9元运费券”不是本项目实际运费。全部是直插件，不能称预焊模块。插座/电容的固定与焊接方案仍需落实，不把用户只能焊排针/导线自动扩大为贴片或整板焊接。','', '## 接线保持原功能','', 'EEPROM使用原0x50地址：1/2/3/4/7接GND，8接3V3_IO，5接NanoJ6.10/SDA，6接NanoJ6.11/SCL；100nF靠近8/4。共享总线总上拉与负载核算后再落线，不盲目每块模块再加上拉。64字节页边界、双字节地址、ACK轮询和断电回读要求不变。','', '屏缓冲器以PDIP20替换同族封装，完整20针见JSON和此前同器件针号证明。20接3V3_PERIPH、10/1/19接GND；2/4/6/8/15分别接BUS_SCK/BUS_MOSI/LCD_RESET_N/HARM_CS_N/TP_RESET_N，18/16/14/12/5分别输出DISP_SCK/DISP_MOSI/DISP_RESET_N/DISP_HARM_CS_N/TP_RESET_MOD_N；11/13接GND、17接3V3_IO，3/7/9是未用输出保持NC。原J10逻辑针号不能当屏厂家40针编号；屏复位物理定义待完整配置冻结。','', '## 电源保护的实际容量约束','', '原R67=23.7kΩ±1%，结合TPS2553原厂公式得到限流约1.002A下界、1.184A上界，标称约1.09A。它不是接上5V3A适配器就能提供3A的通道。原PTC、反接管、限流、断电使能/泄放和3.3V隔离功能全部保留，未调整任何阈值。','', '若成品立体声音箱输出其标称共4W，理想5V供电也至少需0.8A，还未计损耗、屏和DAC。当前缺各模块峰值/启动电流，不能声称一定过载或已经有足够余量。应比较单独受保护的音箱5V分支或自带供电音箱；这只是待落实的供电候选，不默认删保护或放宽原限流。','', '## 排除误用与仍需实现','', 'DFR0565虽然有预焊隔离模块和99元标价，但原厂限定隔离侧最大150mA，且要求两侧不可短接。不能当作原共同地整机的TCA9517直接替代，也不能给屏/声卡整路供电。Adafruit5159/TCA4307原厂明确电源直接贯通，不能把3V3_IO与3V3_PERIPH按默认线缆接到同一模块两侧。其供电/上拉/使能断电行为和国内交付尚未核实，不列入接受替代。','', '原U8/U9的LV595/LV165、U11读回选择、U14 I2C隔离、U16触摸中断整形、U17限流、U18外围3.3V仍没有已核价、预焊且满足原功能的完整采购实现。本轮检索没有找到合格项，不等于市场不存在；不重跑已知无关社区搜索结果。56项原器件的具体网络和保留去向见JSON。','', '## 下一步','', '先收口仍需代焊的最小功能集合与实际可交付服务/报价，完成前端整组通道方案后才能获得小板有效制造报价；同时等待屏完整报价，核成品立体声发声链与受保护电源分支。所有载体、配线、材料、运费和代焊计入700元。到货前做兼容性和采购证据闭合；实物验收仍UNMEASURED。','', '资料：原厂[限流器数据手册](https://www.ti.com/lit/ds/symlink/tps2553.pdf)第15/18页；当前文件全部本地保存，原生40文件哈希核对未变，没有改RTL、烧录、外发消息或下单。','']
(E/'control-power-current-plan.md').write_text('\n'.join(lines),encoding='utf-8')
files=['control-power-current-build.py','control-power-current-plan.json','control-power-current-plan.md','TI-TPS2553-SLVS841F.pdf','TPS2553-ILIM-page15-current.png','TPS2553-ILIM-page18-current.png']
save(E/'control-power-current-stage-file-map.json',dict(at=now,evidence_files=files,mapping_source=str(mapping_path)))
event=dict(at=now,state='CONTROL_POWER56_FUNCTIONS_EXPANDED_AND5LINES_PRICED_NOT_COMPLETE_PLAN',plan=str(E/'control-power-current-plan.md'),evidence=str(E/'control-power-current-plan.json'),priced_subset_CNY='33.70',priced_items=5,original_functions=56,all227retained=True,native40_unchanged=True,RTL_unchanged=True,current_limit_minmax_A=[power['current_limit_mA_including_R_tolerance']['minimum']/1000,power['current_limit_mA_including_R_tolerance']['maximum']/1000],whole700budget_closed=False,physical_tests='UNMEASURED')
ev=read(B/'模块方案-当前证据.json');ev['updated_at']=now;ev['control_power_current_stage']=event
for name in files+['control-power-current-stage-file-map.json']:ev['evidence_sha256']['module-plan-current-evidence/'+name]=sha(E/name)
ev['evidence_sha256']['purchase-preparation-20261021-r1/227件功能分块与混合方案映射-current.json']=sha(mapping_path)
save(B/'模块方案-当前证据.json',ev)
next_action='Read control-power-current-plan.md/JSON:56control/storage/interface/power functions retained;5exact domestic through-hole lines includingMOQ33.70CNY before carrier/assembly/wires/freight. Original23.7k TPS2553 threshold approx1.002..1.184A; no default amplifier load or increased threshold. Need actual preweld realization of LV595/LV165, return selector/I2C isolation/TP_INT, limiter/regulator; no false ready module. Continue whole84sensor/front-end quote and whole-group electrode plan, screen complete quote and stereo playback/power/cables within700. ExistingPCB2 SHA83b238df21nets56items unchanged. Do not replay completed CAD/geometry jobs or modify RTL.'
for name in ['PCB-CURRENT-CAPACITY-RECOVERY-20261024.json','PCB-ACTIVE-WORK.json','实体交付当前入口.json']:
 d=read(B/name);d.update(updated_at=now,control_power_current_stage=event,next_action=next_action,latest_followup=str(B/'模块方案-当前证据.json'))
 for p in [E/'control-power-current-plan.md',E/'control-power-current-plan.json']:
  if str(p) not in d.setdefault('read_first',[]):d['read_first'].append(str(p))
 save(B/name,d)
doc=B/'模块方案-当前工作单.md';text=doc.read_text(encoding='utf-8-sig');marker='\n## 当前控制、存储和电源保护核对'
text=text.split(marker)[0]+marker+'\n\n'
text+='原56项控制/存储/接口/供电功能逐项网络和保留去向已整理到 `module-plan-current-evidence/control-power-current-plan.md` 及JSON。实际立创商品价：24LC256-I/P C411624 11.81元/1只；SN74LVC244AN C1548565 9.33元/1只；100nF X7R直插C2896145 0.4142元×起订10只；DIP8座C72124 0.2075元×起订20只；DIP20座C72118 0.356元×起订12只。五行含起订余量33.704元，不含载体/组装/导线/保护/运费，不冒充预焊完整模块。\n\n'
text+='原TPS2553 R67=23.7kΩ±1%经原厂公式核为限流约1.002—1.184A，不能把3A电源铭牌当原保护通道容量。全音箱/屏/DAC峰值仍未核，音箱独立受保护供电分支只是候选，未改阈值或电路。DFR0565的150mA隔离输出及Adafruit5159默认电源贯通均不作为原TCA9517直接替代。原227功能、主板和小板本轮保持；完整700元方案/交期仍未闭合。\n'
doc.write_text(text,encoding='utf-8')
print(json.dumps(event,ensure_ascii=False))
