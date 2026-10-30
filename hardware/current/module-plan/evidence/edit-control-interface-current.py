from pathlib import Path
import json,hashlib,datetime
E=Path(__file__).parent
def read(n):return json.loads((E/n).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,x):(E/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
baseline=read('control-baseline-scope-review-current.json')
for c in baseline['original_schematic_checks']:assert sha(Path(c['file']))==c['sha256']
fw=read('firmware-readonly-interface-current.json');producer=[]
for p,old in fw['inputs'].items():
 p=Path(p);producer.append(dict(path=str(p),registered_sha=old['sha256'],current_sha=sha(p),unchanged=sha(p)==old['sha256']))
assert all(x['unchanged'] for x in producer),'Changed registered producer: inspect before relying on prior findings'
hw=Path(fw['hardware_contract_source']['path']);assert sha(hw)==fw['hardware_contract_source']['sha256'];pads=json.loads(hw.read_text(encoding='utf-8-sig'))['pads']
nets=['BUS_MOSI','SCAN_LATCH','BUS_SCK','BUS_RETURN','INPUT_LOAD_N','HARM_CS_N']
external=[dict(header=p['ref'],pin=p['n'],net=p['net']) for p in pads if p['ref'] in ['J5','J6'] and p['net'] in nets]
fpga_by_header={'6':15,'7':16,'8':27,'9':28,'15':17,'17':19}  # Nano3921 official schematic Rev1.30, page2
for p in external:p['FPGA_pin']=fpga_by_header[p['pin']]
legacy_H_to_A=['EDIT','PRESET3','PRESET2','PRESET1','PRESET0','ENC_PUSH','ENC_B','ENC_A']
new_H_to_A=['EDIT_APPLY_N','EDIT_SAVE_N','EDIT_CANCEL_N','SPARE_HIGH','SPARE_HIGH','SPARE_HIGH','SPARE_HIGH','SPARE_HIGH']
newpins={'1':'INPUT_LOAD_N','2':'BUS_SCK','3':'3V3_IO','4':'EDIT_CANCEL_N','5':'EDIT_SAVE_N','6':'EDIT_APPLY_N','7':'NC','8':'GND','9':'U9_SER_NEW','10':'GND','11':'3V3_IO','12':'3V3_IO','13':'3V3_IO','14':'3V3_IO','15':'GND','16':'3V3_IO'}
# Independent serial-chain model derived from the manufacturer's parallel-load/shift semantics.
# Every possible pair of parallel bytes is checked, including all old encoder/key states.
tested=0
for legacy in range(256):
 for actions in range(256):
  near=legacy;far=actions;wire=[]
  for k in range(16):
   wire.append((near>>7)&1)
   near=((near<<1)&255)|((far>>7)&1)
   far=(far<<1)&255
  word=0
  for b in wire:word=(word<<1)|b
  assert word==(legacy<<8)|actions
  assert (word>>8)==legacy
  tested+=1
vectors={}
for name,new in [('idle',255),('apply',127),('save',191),('cancel',223),('all_three',31)]:vectors[name]=f'0x{(255<<8)|new:04X}'
now=datetime.datetime.now().astimezone().isoformat()
bom=[dict(reference='UX1',MPN='SN74LV165ADR',LCSC='C273656',quantity=1,assembly='factorySMT'),dict(reference='SX1,SX2,SX3',MPN='TS-1187A-B-A-B',LCSC='C318884',quantity=3,assembly='factorySMT'),dict(reference='RX1,RX2,RX3',MPN='RC0603FR-0710KL',LCSC='C98220',quantity=3,assembly='factorySMT'),dict(reference='CX1',MPN='CL10B104KB8NNNC',LCSC='C1591',quantity=1,assembly='factorySMT')]
contract=dict(at=now,status='CONCRETE_PROPOSAL_NOT_IMPLEMENTED_OR_PURCHASE_RELEASED',purpose='Three separate physical APPLY/SAVE/CANCEL controls; no extra physical harmonic8keys, no PCF8575, no new externalFPGA GPIO.',original_schematic_unchanged=True,RTL_changed=False,physical_tests='UNMEASURED',hardware_baseline=baseline['actual_schematic_baseline'],proposal_total=dict(physical_buttons=8,encoder_with_push=1,LV165=2,LV595=1),proposal_delta_parts=bom,delta_part_count=8,original_control_part_allocation_count=56,new_control_part_allocation_count_before_new_connectors=64,external_header_nets=external,UX1_pin_nets=newpins,U9_only_proposed_net_change='Pin10: remove oldGNDtie, connect UX1.9; proposal only, native unmodified',wire_first8_H_to_A=legacy_H_to_A,wire_next8_H_to_A=new_H_to_A,frame='MSBfirst16bits: legacy_raw=frame[15:8], actions_raw=frame[7:0]; pressedAPPLY=~bit7,SAVE=~bit6,CANCEL=~bit5',idle_and_press_vectors=vectors,scope='Original8-bit firstbyte preserved electrically. Existing8bit reader cannot read new actions; final product16bit read/arbitration driver and physical wrapper remain unaccepted.',bus_contract=['HARM_CS_N high for KEY return, screen unselected; verify U11 selector truth table before final board release','Own BUS grant for complete load+16clock transaction; all other SPI owners excluded','SCAN_LATCH stays low throughout key transfer; no change to595 storage outputs','Next sensor control write must replace all8bits before latch; preserve LCD_RESET_N/TP_RESET_N shadow states','Schedule key clock bursts outside RC MEASURE quiet window; old scan module alone does not enforce wholeproduct arbitration','INPUT_LOAD_N low only at stableclock to capture, high before firstsample; sample initialQH before first risingclock','Atomic16bit frame, debounce activeLow keys separately; quadrature encoder data retained, not run through button debounce','At boot discard unspecified powerup state until first complete valid parallel load; no unintended SAVE from stale input'],timing=dict(design_clock_Hz=27000000,proposed_half_period_cycles=8,serial_clock_Hz=1687500,serial16_payload_us=16*16/27,added8_payload_us=8*16/27,proposed_load_low_cycles=8,proposed_load_release_guard_cycles=8,payload_and_guards_us=(16*16+8+8)/27,wholeproduct_latency_verified=False),action_semantics='APPLY/SAVE/CANCEL have separate inputs. Preview, saved/working/draft targets and playing-instance behavior still need product contract; no invented musical behavior is approved.',model_verification=dict(all_parallel_pairs=tested,original_firstbyte_preserved=True,raw16_roundtrip=True,RTL_simulation=False,board_test=False),manufacturer_source='https://www.ti.com/lit/ds/symlink/sn74lv165a.pdf',lookup_results='edit-control-parts-lookup-current.json; edit-control-parts-jlcsearch-current.json: both403, no stock/CNY price accepted',preweld_quote=False,whole700budget_closed=False,registered_producer_recheck=producer,hard35_reference_scope_approval=False)
contract['return_selector_proof']=dict(source='https://assets.nexperia.com/documents/data-sheet/74LVC1G157.pdf',version='Rev12,2023-08-15,page3',pin1='I1=KEY_QH',pin3='I0=RA_MISO',pin6='S=HARM_CS_N',pin4='Y=BUS_RETURN',truth='S=1 selectsI1/KEY_QH;S=0 selectsI0/RA_MISO',originalU11mapping='control-power-current-plan.json')
contract['bus_contract'][0]='Verified U11 truth table: HARM_CS_N high selectsKEY_QH and screen unselected; low selectsRA_MISO.'
contract['SIPO_latch_source']='https://www.ti.com/lit/ds/symlink/sn74lv595a.pdf'
save('edit-control-interface-current.json',contract)
md='''# 应用、保存、取消：独立实体操作接口候选

本文件把接口做成可审查的接线合同，尚未修改原理图、PCB或RTL，也未把它当作可以买来即装的模块。

## 最小增量

保留原4预设键、EDIT和按压编码器；仅增加APPLY（应用）、SAVE（保存）、CANCEL（取消）三个独立实体按钮。泛音8分区仍在J10屏上。合计为8个实体按钮和1个带按压编码器。

原U9八输入已满，故候选在同一预焊控制板中增加一片同型号SN74LV165ADR（UX1），串接到原U9串行输入。原U9和UX1共16个输入，使用11个，余5个固定高。它不是之前误加8泛音实体按钮的13键方案，也不是16个按钮或PCF8575方案。

## 新增器件及焊接责任

|数量|料号|立创编号|用途|
|---:|---|---|---|
|1|SN74LV165ADR|C273656|新增并入串出寄存器UX1|
|3|TS-1187A-B-A-B|C318884|应用/保存/取消，分别接对应输入与GND|
|3|RC0603FR-0710KL|C98220|每键10k上拉到3V3_IO|
|1|CL10B104KB8NNNC|C1591|UX1.16/8附近100nF去耦|

以上8件全部工厂贴片预焊；与原56项控制/接口/存储/保护合计64件，尚未算可能新增的线束连接器。数量账不等于成品价；立创公开详情及技能推荐社区查询本次均403，实际错误已保存，未绕验证或把旧库存当现货。准确人民币物料、加载费、PCB、通孔预焊、运费和交期仍需真实报价。

预焊外置按钮DFR0029-W的厂家售价10元/个，含一根线，供电3.3—5V；但官方教程说明按下为高电平，与本候选按下为低电平不同，不能直接替换上述按钮网络。尚未核完具体原理图/线序和清远交期，不把三块30元当成完整操作接口已完成。

## 原Nano接口保留

|Nano排针|FPGA脚|原信号|
|---|---:|---|
|J6.6|15|BUS_MOSI|
|J6.7|16|SCAN_LATCH|
|J6.8|27|BUS_SCK|
|J6.9|28|BUS_RETURN|
|J6.15|17|INPUT_LOAD_N|
|J6.17|19|HARM_CS_N|

这些排针/网络由原951主板捕获和Nano3921官方图相互核对。没有新增外部FPGA引脚；不因此代表现有产品固件支持新增输入。

## UX1逐针合同

|UX1脚|连接|
|---:|---|
|1|INPUT_LOAD_N，与U9.1共享|
|2|BUS_SCK，与U9.2共享|
|3|3V3_IO，未用E输入固定高|
|4|EDIT_CANCEL_N，10k上拉；按钮按下接GND|
|5|EDIT_SAVE_N，10k上拉；按钮按下接GND|
|6|EDIT_APPLY_N，10k上拉；按钮按下接GND|
|7|互补输出，不接|
|8|GND|
|9|接U9.10；必须移除原U9.10到GND的连接|
|10|GND，链末端串行输入|
|11、12、13、14|3V3_IO，未用A/B/C/D固定高|
|15|GND，允许移位|
|16|3V3_IO；与8脚间靠近放100nF|

UX1必须与原U9同3V3_IO供电，不能接到可单独关断的3V3_PERIPH。原U9.9仍输出KEY_QH，经过原U11回到BUS_RETURN。额外电路不能改变原保护、I²C隔离、屏复位或供电限流。

## 位序、共享总线与验收

16位MSB-first：先读原8位，顺序EDIT、PRESET3、PRESET2、PRESET1、PRESET0、ENC_PUSH、ENC_B、ENC_A；后读新增8位，顺序APPLY_N、SAVE_N、CANCEL_N、高、高、高、高、高。归一化为legacy_raw=frame[15:8]，actions_raw=frame[7:0]。归一化后原8位编码和次序不变；新的16位原始帧并不自动兼容旧8位驱动。

原按键全释放时，示例帧：全释放FFFF，单按应用FF7F，单按保存FFBF，单按取消FFDF，同时三键FF1F。所有键均按下接地；按键消抖和编码器正交解码须分开。

必须完整取得总线grant，屏HARM_CS_N保持高，并在整个按键读取期间把SCAN_LATCH保持低。16个时钟会改变595的移位级，却不应改变其输出锁存级；下次传感控制须重新写完整8位后才锁存，且保留两个屏复位位。把读键任务排在RC测量安静窗口外，不能只证明串行数据读得出便宣布不干扰电容计时。

按27MHz、半周期8拍，16位数据阶段9.481481μs，较8位增加4.740741μs；加候选load低/释放保护各8拍，共10.074074μs，未含仲裁等待、消抖或全产品延迟。TI手册支持3.3V和串接；这只是器件级依据，不是已测10ms整机目标。

离线两级串行模型穷举65536种并行输入，验证完整位序与原8位保持。不是RTL仿真、595实测、板测或厂家接受。登记producer文件SHA重新核对未变；现有scan_shift595本身仍是8位写出器，不含这个16位读键端点。完整产品读回、仲裁和物理顶层仍需实现/签收，本聊天不改RTL或烧录。

## 操作语义仍需区分

三个独立输入解决的是“能区分哪个实体键”，不自动解决试听/应用/保存/取消的数据语义。候选定义：应用不等于写EEPROM；保存只在完整提交及回读确认后显示成功；取消不能破坏已保存定义。草稿、正式定义、运行修饰和在响实例继续分离。具体试听对象、未应用草稿按保存的行为、换槽和在奏音更新时机仍按产品合同关闭，不能私自删功能、让非活动bank代替完整编辑器或修改16词提交校验。

来源：[TI原厂SN74LV165A](https://www.ti.com/lit/ds/symlink/sn74lv165a.pdf)、[DFR0029-W商品](https://www.dfrobot.com.cn/goods-865.html)、[按钮原厂教程](https://wiki.dfrobot.com.cn/_SKU_DFR0029_数字大按钮模块_V2)。全部原始脚号、穷举结果、源SHA和现有接口依据见同目录edit-control-interface-current.json。
'''
md+='\n\n补充已核依据：Nexperia 74LVC1G157原厂Rev12第3页与原U11网络一致：1脚I1=KEY_QH，3脚I0=RA_MISO，6脚S=HARM_CS_N，4脚Y=BUS_RETURN；S高选择KEY_QH，S低选择RA_MISO。因此读键保持屏片选高，沿用原读回选择器。TI SN74LV595A原厂资料将移位级与输出存储级分开；按键时钟期间必须禁止SCAN_LATCH上升沿，仍须用最终固件/示波器验收其真实行为。\n'
(E/'edit-control-interface-current.md').write_text(md,encoding='utf-8')
print(json.dumps(dict(status=contract['status'],model=contract['model_verification'],frames=vectors,new_parts=8,no_extra_external_GPIO=True,all_registered_sources_unchanged=True),ensure_ascii=True))
