"""Complete scope ledger for one instrument; no order or release is implied."""
import csv,hashlib,json,math,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parent;HW=ROOT.parent
sys.path.insert(0,str(HW))
from current_state import current_checkpoint
checkpoint_path,checkpoint,capture_path=current_checkpoint(HW)
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
native=list(csv.DictReader((HW/'procurement-native-candidate.csv').open(encoding='utf-8-sig')))
fresh={p['code']:p for p in json.loads((ROOT/'fresh-catalog.json').read_text(encoding='utf-8'))}
design=json.loads((HW/'design.json').read_text(encoding='utf-8'))
domestic={p['lcsc']:p for p in json.loads((ROOT/'domestic-critical-checks.json').read_text(encoding='utf-8'))} if (ROOT/'domestic-critical-checks.json').exists() else {}
assert len(native)==36 and len(design['parts'])==230
assert Counter(p['ref'] for p in design['parts'])==Counter(ref for p in native for ref in p['references'].split(','))
board=[]
for p in native:
    f=fresh[p['code']]
    assembly={'SMT_candidate':'工厂SMT供料','manual_through_hole':'手焊通孔','manual_SMD_button':'手焊按键'}[p['assembly']]
    if p['code']=='C318884':
        assert domestic[p['code']]['status']=='identity_checked_public_page' and domestic[p['code']]['assembly_stock']>0
        assembly='工厂SMT供料' # same MPN/footprint; avoid unavailable loose stock
    board.append(dict(code=p['code'],mpn=p['mpn'],per_board=int(p['placed_quantity']),assembly=assembly,
        minimum=f.get('minimum'),multiple=f.get('multiple'),stock=f.get('stock_lcsc'),
        first_tier_usd=(f.get('tiers') or [{}])[0].get('usd'),refs=p['references'],
        repair_spares=1 if assembly!='工厂SMT供料' else 0,
        status='散买0；国内页面有SMT库存，改工厂匹配' if p['code']=='C318884' else '散买缺货，需替料或确认SMT库存' if not f.get('stock_lcsc') else '本地化MPN需核机械图' if not f.get('mpn_text_matches') else '目录身份已核，待制造匹配',
        url='https://www.lcsc.com/product-detail/'+p['code']+'.html',checked_utc=f['checked_utc'],footprint=p['footprint']))
assert sum(x['per_board'] for x in board if x['assembly']=='工厂SMT供料')==217
assert sum(x['per_board'] for x in board if x['assembly']=='手焊通孔')==13
assert sum(x['per_board'] for x in board if x['assembly']=='手焊按键')==0

items=[]
def add(id,category,name,spec,qty,unit,stage,action,url=''):
    items.append(dict(id=id,category=category,item=name,spec=spec,quantity=qty,unit=unit,stage=stage,action=action,url=url))
add('E01','已有','Tang Nano20K','已有主计算板；不另购MCU',1,'块','已有，不重复买','核实实板版号、排针公母、USB下载通道','https://wiki.sipeed.com/hardware/en/tang/tang-nano-20k/nano-20k.html')
add('E02','已有','4Ω / 3W 喇叭','只接Nano板载BTL扬声器输出',1,'只','已有，不重复买','核插头与板上座；两端不接AUX或地')
add('D01','显示','LCDWIKI MSP2401','2.4英寸ILI9341、无触摸、4线SPI；5V VCC、3.3V IO',1,'套','采购型号已选，商品版本待核','确认商品对应厂家MSP2401；J1稳压旁路断开，带排针；按已生成转接表接线','https://www.lcdwiki.com/2.4inch_SPI_Module_ILI9341_SKU:MSP2402')
add('D02','显示','ER-TFTM070-5V4','7英寸800×480、RA8875、4线SPI含读回、5V、电容触摸FT5316、内置背光控制',1,'套','暂缓，出货配置和整价未闭合','需供方确认同一SKU的引脚/CTP触点/复位/线缆及人民币含税运价；不买Arduino盾板/字体/额外TF选配','https://www.buydisplay.com/chinese/7-inch-lcd-module-capacitive-touch-screen-panel-i2c-spi-serial')
add('C01','线束','小屏转接线束','载板1×12母端→MSP2401模块端；至少8根有效信号，逐线错位映射',1,'套','电气接线表已明确，长度待机械','按“小屏接线”页制作并逐线测通断；按实际模块排针配公母')
add('C02','线束','大屏转接线束','载板1×12母端→确切大屏接口',1,'套','暂缓，厂家针脚未签核','大屏资料确定后生成，禁止先买所谓通用12针转40针线')
add('C03','线束','Nano短线束','2组1×20，载板端匹配排母；Nano端按实板排针，保留未用脚NC',2,'条','暂缓，实板配对待核','长度尽可能短并按实际支架量取；不要购买2×10 IDC冒充1×20')
add('C04','线束','电极线束','6组1×16；载板端母座配PZ254V-11-16P，每组14电极+2地',6,'条','板端针距/孔径已核，长度和配对待定','原厂0.64mm方针、配合长6.1mm；线端须核适配，试样先短线并记录寄生，不冻结统一长线')
add('C05','供电配套','JST XHP-2 配套电源线','XH 2.5mm 2P；XHP-2壳体、SXH-001T-P0.6普通型端子、AWG22，绝缘外径0.9–1.9mm',1,'套','线端型号已选，成品线供方待核','优先成品压接线；不是低插入力N型或AWG30–26的002型；按J13.1正5V/J13.2地检验','https://www.jst-mfg.com/product/pdf/eng/eXH.pdf')
add('C06','供电配套','JST XHP-2 备用壳体','同C05，不是2.54mm杜邦壳',2,'只','按规格通用件','为重做极性和维修备份；不计成额外电源线','https://www.jst-mfg.com/product/pdf/eng/eXH.pdf')
add('C07','供电配套','JST SXH 配套端子','SXH-001T-P0.6普通型；AWG22、绝缘外径0.9–1.9mm，配XHP-2',6,'只','型号已选，随压接方案购备件','成品线已含端子时可不单购；无匹配压接工具时不裸买端子','https://www.jst-mfg.com/product/pdf/eng/eXH.pdf')
add('P01','供电','稳压5V电源','现有5V3A历史记录；具体铭牌、插头、线长、压降未核实',1,'套','先核已有，暂不重复买','实测双屏启动和压降后定型号；不能因适配器3A就提高板上1.1A附近限流')
add('P02','供电','Nano USB供电/下载线','匹配Nano实际USB接口，数据线需支持下载',1,'条','先核已有','与载板外部5V保持现有隔离；Nano J5.1 NC')
add('A01','音频','3.5mm立体声TRS面板母座','焊片式Tip=L、Ring=R、Sleeve=GND；独立绝缘固定',1,'只','规格已列，机械型号待定','当前载板J12是3针接口，不是3.5mm插座封装；插座外形配面板')
add('A02','音频','AUX屏蔽连接线','J12端1×3母接头到TRS焊片，L/R及屏蔽地',1,'条','规格已列，长度待机械','J12.1=L、.2=R、.3=GND；只接有源输入')
add('A03','音频','3.5mm立体声AUX成品线','双端TRS公头，接有源音箱/音响',1,'条','先核已有','不把无源喇叭或耳机当线路负载；上电静音完成后连接')
add('S01','存储','microSDHC 32GB C10/U1','复用Nano板载TF座；FAT32目标',1,'张','规格已选，当前在售具体型号待核','旧Kingston SDCS2/32GB已停产，不作为新购首选；替代卡需SPI初始化/长停顿测试','https://www.kingston.com/en/memory/search/discontinuedmodels?partId=SDCS2%2F32GB')
add('S02','存储','USB读卡器','支持microSDHC 32GB',1,'只','先核已有','用于格式化/文件验读；不另购TF座模块')
add('T01','电极小样','导电背胶铜箔','20mm宽×2m；用于少量三电极小样，不是最终尺寸板',1,'卷','按规格小样材料','确认背胶导电方式；避免把材料小样当最终完整电极结构')
for i,th in enumerate(['0.125','0.25','0.5']):
    add('T0'+str(i+2),'电极小样','PET覆盖片 '+th+'mm','A4或更大、绝缘薄片，记录厚度/胶层',1,'张','按规格小样材料','比较触摸增量、手感和漂移后选择；三种不同时叠加')
add('T05','电极','最终三电极面板/PCB','84通道能力保留；25/26端点均可容纳',1,'套','暂缓，几何与材料待标定','不要按尺寸草案直接加工；按实际节点表和最终覆盖层制作')
add('M01','结构','载板支撑及螺钉','4个临时安装孔；规格/高度/绝缘距离待装配图',1,'套','暂缓，孔位与高度未审签','不购买固定高度整套金属柱后反向迁就布局')
add('M02','结构','双屏支架/螺钉/间隔柱','按各模块实际孔位、玻璃边缘、排针高度配套',2,'套','暂缓，模块机械图待配准','小屏MSP2401图可用；大屏出货版图缺失')
add('M03','结构','按压旋钮帽','匹配EC11E15244B2直径6mm平轴、20mm轴长与实际面板高度',1,'只','轴规格已核，帽孔/高度待核','平轴内孔和按压行程留量须对应；不能按外观选帽','https://tech.alpsalpine.com/e/products/detail/EC11E15244B2/')
add('M04','结构','外壳/操作面板','470×220mm为空间提案；厚度/孔位未冻结',1,'套','暂缓，不能据草图生产','先纸样/模块/手姿核对，再生成机械施工图')
add('F01','制造','主载板裸PCB','当前暂定140×100mm、2层、1oz、1.6mm FR-4',5,'块','暂缓，数量为报价假设',f"当前{checkpoint['unconnected_errors']}未连通；5板仅询价假设，实际国内工艺/最小量待最终文件确认")
add('F02','制造','选择性SMT装配','每板217个SMT候选（含5个按键），按实际装配表匹配',2,'块','暂缓，数量为报价假设','按键国内页面有贴片库存，需最终匹配；国际JLC原型MOQ2，国内政策和费用另核','https://jlcpcb.com/solutions/pcb-prototype-assembly')
add('F03','制造','手焊装配','每完整载板13个通孔件；5个SMD按键改由工厂贴装',1,'块','按用户既有自焊能力安排','当前只装一套完整乐器；第二块贴片板可留作备份，不自动加购第二套屏幕')
add('F04','制造','钢网/扩展料上料/损耗','按平台最终装配报价核计',1,'批','等待真实匹配报价','工厂供料的217个位号不要再按散买表重复购买；计入按键上料费')
add('F05','采购费用','运输/税费/线束加工费','板、两屏、线束、材料可能不同渠道',1,'批','未报价','不得以器件美元小计或273.22元基础屏价充当整机到手价')

source=json.loads(capture_path.read_text(encoding='utf-8'))
pin=lambda n:next(p['net'] for p in source['pads'] if p['ref']=='J11' and p['n']==str(n))
connections=[(1,1,'VCC'),(2,2,'GND'),(5,3,'CS'),(7,4,'RESET'),(6,5,'DC/RS'),(4,6,'SDI/MOSI'),(3,7,'SCK'),(8,8,'LED')]
harness=[dict(carrier='J11',carrier_pin=a,net=pin(a),module='MSP2401',module_pin=b,module_label=label,
              status='厂家通用资料已核；成品线需导通/极性检验') for a,b,label in connections]
assert [x['net'] for x in harness]==['5V_PERIPH','GND','DISP_VIS_CS_N','DISP_RESET_N','DISP_VIS_DC','DISP_MOSI','DISP_SCK','VIS_BL_EN']
(ROOT/'small-screen-harness.json').write_text(json.dumps({'module_mpn':'MSP2401','connections':harness,
 'not_connected':'模块9 SDO不接；10–14触摸端本方案不使用；载板9–11 NC，12为备用GND，不按相同针号直连',
 'conditions':'模块J1断开用于5V供电；3.3V数字IO；按厂商pin1方向检验，非镜像图',
 'source_url':'https://www.lcdwiki.com/2.4inch_SPI_Module_ILI9341_SKU:MSP2402','manufacturing_release':False},ensure_ascii=False,indent=2),encoding='utf-8')
issues=list(csv.DictReader((HW/'release-open-items.csv').open(encoding='utf-8-sig')))
result={'date':'2026-10-21','instrument_count':1,'assembly_board_quote_assumption':2,'manual_populated_boards':1,
 'board_bom':board,'external_items':items,'small_screen_harness':harness,'issues':issues,
 'counts':{'board_part_types':36,'placed_per_board':230,'factory_smt_per_board':217,'manual_through_hole_per_board':13,'manual_smd_buttons_per_board':0,'external_scope_rows':len(items)},
 'source_sha256':{p.name:h(p) for p in [HW/'design.json',HW/'procurement-native-candidate.csv',ROOT/'fresh-catalog.json',capture_path,checkpoint_path]},
 'hardware_checkpoint':{'file':checkpoint_path.name,'pcb_sha256':checkpoint['pcb_sha256'],'unconnected_errors':checkpoint['unconnected_errors'],'pending_nets':len(checkpoint['pending_nets'])},
 'price_policy':'USD目录阶梯仅参考；人民币单价与税运待实际报价，缺失价格保持空值；不计算伪整机总价',
 'manufacturing_release':False,'purchases_made':False}
(ROOT/'purchase-master.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# 完整采购范围准备 · r1 · 2026-10-21','',
 '目标为一套完整乐器。报价暂按2块SMT载板（第二块备份）、1块补焊13个通孔件；5块裸板为询价假设。还没有提交订单。',
 '217个SMT位号（包含5个按钮）交工厂匹配供料；不要再按散买MOQ重复购买。两屏仍各1套。缺失的人民币单价和税运不填零、不换汇伪造总价。','',
 f'板上36类/230位号已逐项覆盖；外部范围{len(items)}行，包含已有器材、模块、线材、结构、制造和费用。','',
 '## 外部购买与加工范围','', '| 编号 | 项目 | 数量 | 状态 | 下单/加工前条件 |','|---|---|---:|---|---|']
for p in items:lines.append(f"|{p['id']}|{p['item']} / {p['spec']}|{p['quantity']}{p['unit']}|{p['stage']}|{p['action']}|")
lines+=['','## 板上物料','', '| 料号 | 型号 | 每板用量 | 装配 | 当前散买库存 | 核对状态 |','|---|---|---:|---|---:|---|']
for p in board:lines.append(f"|[{p['code']}]({p['url']})|{p['mpn']}|{p['per_board']}|{p['assembly']}|{p['stock']}|{p['status']}|")
lines+=['','## 已关闭的资料缺口与仍待处理','',
 '小屏J11到模块八根信号线已形成明确错位接线表，见small-screen-harness.json；不再把所有供方针脚统一写成NOT_ASSIGNED。实际出货版、公母/长度及通电前导通仍需验。',
 f"大屏出货配置/CTP整价/完整PDF、最终机械、电源实测及PCB{checkpoint['unconnected_errors']}未连通仍未关闭。36类公开目录不是国内SMT匹配成功。按钮C318884本次散买库存0，但国内页面记录smtStockNumber=273109，因此决定把5个按键纳入工厂装配候选；同MPN、同封装，不改电路。最终平台库存和新增上料费仍需匹配报价。",
 '已发现86号扫描与本板的复位位和节点索引冲突，独立候选通过数字验证，见../hardware-contract-20261021-r1/README.md。不能把旧实验直接下载为产品。',
 '采购与制造任务继续进行；本表是完整范围账，不是所有项目均可立即下单的放行表。']
(ROOT/'采购范围与装配分工-r1.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps(result['counts'],ensure_ascii=False));print('No manufacturing release; no purchases.')
