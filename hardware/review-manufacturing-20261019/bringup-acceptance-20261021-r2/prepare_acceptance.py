"""Build unexecuted bench worksheets, bound to saved hardware source hashes.

Never overwrite measured records: templates are written separately from runs/.
Only static source contracts are checked here; no physical pass is inferred.
"""
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parent
PROJECT=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
save=lambda name,obj:(OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
sys.path.insert(0,str(ROOT))
from resume_offline import read_native
from current_state import current_checkpoint

checkpoint_path,checkpoint,capture_path=current_checkpoint(ROOT)
native_ok={p:sha(PROJECT/p)==s for p,s in checkpoint['files'].items()}
assert all(native_ok.values())
pcb=PROJECT/'pcb/PCB1.epcb2'
live=read_native(pcb)
design={p['ref']:p for p in read(ROOT/'design.json')['parts']}
capture=read(capture_path)
actual={(p['ref'],str(p['n'])):p['net'] or None for p in capture['pads']}
contracts={
 'U17':{'3':'3V3_IO','4':'PWR_FAULT_N','6':'5V_PERIPH'},
 'U8':{'13':'GND','10':'3V3_IO','4':'MUX_DISABLE','5':'RC_DRIVE','6':'LCD_RESET_N','7':'TP_RESET_N'},
 'U15':{'17':'3V3_IO','3':'VIS_BL_EN','20':'3V3_PERIPH'},
 'J5':{'1':None},'J11':{'8':'VIS_BL_EN'},
 'J13':{'1':'5V_IN','2':'GND'},'J12':{'1':'AUX_L','2':'AUX_R','3':'GND'}}
for ref,pins in contracts.items():
    for pin,net in pins.items():
        assert design[ref]['nets'][pin]==net,(ref,pin,'design',design[ref]['nets'][pin],net)
        assert actual[ref,pin]==net,(ref,pin,'capture',actual[ref,pin],net)
fault_attachments=[(r,n) for (r,n),net in actual.items() if net=='PWR_FAULT_N']
assert set(fault_attachments)=={('U17','4'),('R68','2'),('TP8','TP8')},fault_attachments
native_tp={p['num']:p for (kind,_),p in live.items() if kind=='PAD' and p['num'].startswith('TP')}
points=list(csv.DictReader((ROOT/'pcb-testpoints.csv').open(encoding='utf-8-sig',newline='')))
assert len(native_tp)==len(points)==21
for p in points:
    v=native_tp[p['name']]
    assert v['netName']==p['net']
    assert abs(v['centerX']*.0254-float(p['x_mm']))<.0001
    assert abs(v['centerY']*.0254-float(p['y_mm']))<.0001
master=read(ROOT/'purchase-preparation-20261021-r1/purchase-master.json')
assert sum(p['per_board'] for p in master['board_bom'])==230
assert sum(p['per_board'] for p in master['board_bom'] if p['assembly']=='工厂SMT供料')==217
assert sum(p['per_board'] for p in master['board_bom'] if p['assembly']=='手焊通孔')==13

identity=dict(hardware_revision=None,pcb_sha256=sha(pcb),actual_bom_sha256=None,
    bitstream_sha256=None,product_firmware_qualified=False,nano_revision=None,
    small_screen_revision=None,large_screen_configuration=None,
    harness_revision=None,instruments=None,date_utc=None,operator=None)
stages=[
 ('A01','同版制造资料与原生DRC','零未连通；Gerber/钻孔/BOM/CPL同版，回流与机械审查完成'),
 ('A02','工厂供料及费用','217位号精确匹配与替料审批；含按钮、税运和上料费用'),
 ('A03','PCBA到货外观','230最终实装位号；pin1/极性/焊桥及通孔方向核准'),
 ('A04','断电阻抗','三路3.3V隔离；无电源误短；保存阻抗趋势'),
 ('B01','线束断电导通','预期线路和未连接脚逐项核对；电源极性插合后测量'),
 ('C01','仅外部5V空载','保护链电压、关断残压/电流和温升'),
 ('C02','仅USB/Nano','主机轨、外设残压/反灌；实板与码流身份'),
 ('C03','Nano初始化后外部5V','完整595安全字与实际复位延时；三路3.3V与5V'),
 ('C04','电子负载阶跃','实际负载点压降、启动/限流/恢复与温升'),
 ('C05','四状态及顺序空载','2种接通顺序、分别断开；测量而非仿真推定'),
 ('D01','小屏单独','J1/5V/IO；彩条与观看方向；八线错位正确'),
 ('D02','大屏单独','同一SKU图纸/引脚；SPI4读回、忙超时、满背光启动'),
 ('D03','双屏/595/165仲裁','CS互斥、完整重装8位、重新LOAD、扫描保留复位位'),
 ('D04','触摸/I2C','真实地址；两侧电平与上升时间；超时恢复'),
 ('D05','编码器/按键','真实输入字、去抖方向/定位和显示并发'),
 ('D06','音频静音/时钟','锁定回读、零PCM；AUX和BTL分别验证'),
 ('E01','三电极/覆盖层小样','材料、线长、噪声/漂移/触摸分布；确定性能门槛'),
 ('E02','单组14路','参考地址排除、不同节点位置与超时'),
 ('E03','六组84路','25/26候选索引、八度选择5节点、备用节点和全帧统计'),
 ('E04','最新完整固件实现','真实协议包装、共同PnR/STA及资源检查；候选测试不替代'),
 ('E05','全负载供电顺序复验','两屏+传感+音频+TF；各顺序和重配置后恢复'),
 ('E06','完整并发长测','记录持续时间、欠载、最大存储停顿、误触/恢复和温升')]
save('stage-records-TEMPLATE.json',dict(identity=identity,physical_tests_executed=False,
    stages=[dict(id=i,stage=s,exit_evidence=e,status='pending',measured_result=None,
                 acceptance_limits=None,evidence_files=[],failure_action=None) for i,s,e in stages]))
power_points=[p for p in points if p['name'] in ['TP2','TP3','TP4','TP5','TP6','TP7','TP8','TP9']]
states=[('both_off',False,False),('usb_only',True,False),('external_only',False,True),('both_on',True,True)]
save('power-records-TEMPLATE.json',dict(identity=identity,physical_tests_executed=False,
    note='TP8 depends on peripheral pull-up rail: off-state low does not alone mean a fault. Supply current and reverse current must be measured separately; voltage is insufficient.',
    states=[dict(state=s,usb=u,external_5v=e,load_configuration=None,sequence=None,
        bench_voltage_setting_v=None,bench_current_limit_a=None,input_current_a=None,
        reverse_current_a=None,temperatures_c={},measurements=[dict(point=p['name'],net=p['net'],
          voltage_v=None,min_transient_v=None,max_transient_v=None,acceptance_limits=None,
          status='pending',evidence_files=[]) for p in power_points]) for s,u,e in states]))
harness=list(csv.DictReader((ROOT/'harness-contract.csv').open(encoding='utf-8-sig',newline='')))
for r in harness:
    assert actual[r['reference'],r['pin']]==(None if r['net']=='NC' else r['net'])
save('harness-records-TEMPLATE.json',dict(identity=identity,physical_tests_executed=False,
    note='Carrier pin names and candidate module mapping only. N/A is unresolved or an electrode destination, not a pin-to-pin wiring instruction. Keep all unapproved destinations pending.',
    pins=[dict(carrier=r['reference'],pin=r['pin'],net=r['net'],
        candidate_destination=r['supplier_module_pin'],actual_destination=None,
        continuity_ohm=None,unintended_shorts_checked=False,orientation_photo=None,
        status='pending') for r in harness]))
sources=['design.json',capture_path.relative_to(ROOT).as_posix(),checkpoint_path.name,'pcb-testpoints.csv','harness-contract.csv',
    '装配与分阶段验收-r2.md','purchase-preparation-20261021-r1/purchase-master.json',
    'hardware-contract-20261021-r1/contract-results.json']
save('static-contract-results.json',dict(utc=datetime.now(timezone.utc).isoformat(),
    source_sha256={s:sha(ROOT/s) for s in sources},native_files_unchanged=native_ok,
    critical_pin_contracts=contracts,fault_attachments=fault_attachments,
    native_testpoints_verified=21,harness_carrier_pins_verified=len(harness),
    assembly_counts={'total':230,'smt':217,'through_hole':13},
    stage_records=len(stages),power_measurement_slots=len(states)*len(power_points),
    static_checks_passed=True,physical_tests_executed=False,manufacturing_release=False))
print(json.dumps({'static_checks_passed':True,'testpoints':21,'harness_pins':len(harness),
                 'stages':len(stages),'physical_tests_executed':False},indent=2))
