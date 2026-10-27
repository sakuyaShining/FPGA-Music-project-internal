from pathlib import Path
import json,hashlib,datetime,csv,io,copy
B=Path(r'D:\FPGA-Project\codex-deliverables\dual-screen-review-20261020-v2');E=B/'module-plan-current-evidence'
def read(n):return json.loads((E/n).read_text(encoding='utf-8-sig'))
def save(n,x):(E/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
now=datetime.datetime.now().astimezone().isoformat();c=read('control-power-current-plan.json');proposal=read('edit-control-interface-current.json')
rows=copy.deepcopy(c['original56_allocation']);assert len(rows)==56 and len({r['reference'] for r in rows})==56
for r in rows:
 r.update(quantity=1,scope='Original227 functional baseline retained in control subassembly candidate',price_CNY=None,preweld_accepted=False)
 if r['reference']=='U9':
  for p in r['original_pin_nets']:
   if p['pad']=='10':p.update(original_net='GND',net='U9_SER_NEW',candidate_only=True)
for item in proposal['proposal_delta_parts']:
 for ref in item['reference'].split(','):
  row=dict(reference=ref,original_MPN=item['MPN'],original_LCSC=item['LCSC'],quantity=1,scope='New independent action candidate; factorySMT required, not purchased module',price_CNY=None,preweld_accepted=False)
  if ref=='UX1':row['original_pin_nets']=[dict(pad=p,net=n) for p,n in proposal['UX1_pin_nets'].items()]
  elif ref.startswith('SX'):row['logical_terminals']=[dict(terminal='one_side',net={'SX1':'EDIT_APPLY_N','SX2':'EDIT_SAVE_N','SX3':'EDIT_CANCEL_N'}[ref]),dict(terminal='other_side',net='GND')];row['physical_pad_binding']='SameTS1187 footprint verify before native board'
  elif ref.startswith('RX'):row['logical_terminals']=[dict(terminal='one_end',net='3V3_IO'),dict(terminal='other_end',net={'RX1':'EDIT_APPLY_N','RX2':'EDIT_SAVE_N','RX3':'EDIT_CANCEL_N'}[ref])]
  elif ref=='CX1':row['logical_terminals']=[dict(terminal='one_end',net='3V3_IO'),dict(terminal='other_end',net='GND')]
  rows.append(row)
assert len(rows)==64 and len({r['reference'] for r in rows})==64
save('control64-candidate-BOM-current.json',dict(at=now,state='UNRELEASED_ELECTRICAL_ALLOCATION_NOT_MANUFACTURING_BOM',original_items=56,new_items=8,total_before_added_connectors=64,rows=rows,placement_CPL_Gerber_available=False,complete_module=False,PCB_RTL_changes=False,original227_baseline_not_replaced=True))
out=io.StringIO(newline='');w=csv.writer(out);w.writerow(['Reference','MPN','LCSC','Quantity','Scope','Assembly status'])
for r in rows:w.writerow([r['reference'],r['original_MPN'],r['original_LCSC'],r['quantity'],r['scope'],'UNRELEASED factory preweld quote pending'])
(E/'control64-candidate-BOM-current.csv').write_text(out.getvalue(),encoding='utf-8-sig')
pdf=E/'Nano20K-3921-official-schematic.pdf'
storage=dict(at=now,state='OWNED_NANO_TF_SOCKET_ELECTRICAL_EVIDENCE_NOT_RECORDPLAY_ACCEPTANCE',official_product='https://wiki.sipeed.com/hardware/en/tang/tang-nano-20k/nano-20k.html',official_schematic=str(pdf),schematic_SHA=sha(pdf),schematic_page1based=5,visual=str(E/'Nano20K-TF-proof-current.png'),existing_socket='J7 Micro_SD_Card_Det',pins=[dict(J7=1,signal='DAT2',FPGA=80),dict(J7=2,signal='DAT3/SPI_CS',FPGA=81),dict(J7=3,signal='CMD/SPI_MOSI',FPGA=82),dict(J7=4,signal='3V3'),dict(J7=5,signal='CLK',FPGA=83,series_resistor='R49 22ohm'),dict(J7=6,signal='GND'),dict(J7=7,signal='DAT0/SPI_MISO',FPGA=84),dict(J7=8,signal='DAT1',FPGA=85)],existing_pullups='R53,R54,R55,R56,R57=10k to3V3;C26=4.7uF',dedup='No separate FPGA-side TFreader module required when using this ownedNano slot; card itself still required. This doesnotdedup instrument EEPROM or power protection.',recordplay='ActualPCM recordplay, block buffering, write stalls, file format and simultaneous live/score mix still unaccepted. Bitstream flash isnotfreeaudio storage.',USB_preparation_reader=dict(SKU='FIT0548',model='C289',listed_CNY=8,source='https://www.dfrobot.com.cn/goods-1605.html',quantity=1,stock_count_unknown=True,Qingyuan_dispatch_unknown=True,role='PC card preparation/export only; not product runtime dependency'),rejected_card_sources=[dict(SKU='FIT0570',source='https://www.dfrobot.com.cn/goods-1708.html',reason='Officialpage removed/discontinued; no purchaseprice'),dict(SKU='FIT0394',source='https://www.dfrobot.com.cn/goods-1037.html',reason='Officialpage removed/discontinued; no purchaseprice')],whole700budget_closed=False,physical_tests='UNMEASURED')
save('Nano-TF-storage-scope-current.json',storage)
md='''# 现有Nano的TF接口与录放采购边界

2026-10-27。拥有的Tang Nano20K自带J7 TF卡座，Nano3921官方原理图第5页已核。连接为DAT2→FPGA80、DAT3/SPI_CS→81、CMD/SPI_MOSI→82、CLK→83（22Ω串联）、DAT0/SPI_MISO→84、DAT1→85，供电3.3V；5条数据/命令线上有10k上拉，去耦4.7μF。证据图Nano20K-TF-proof-current.png与源PDF SHA见JSON。

由具体原理图证明：采用现有板载卡座时，不再采购一块外部FPGA侧TF读卡模块。TF卡仍需购买；EEPROM用于乐器定义保存，不能因此删除。Nano的码流Flash也不能当作空闲录音空间。

实际PCM录放、块读写/缓存、写忙间隙、文件格式与现场/曲谱混音未签收；不能以“有卡座”关闭录放功能或10ms目标。SPI模式与SDIO模式由最终产品驱动/CST确定，当前仅列已存在电气连接，不在本聊天修改RTL、格式化卡或烧录。

电脑准备/导出卡文件的USB读卡器候选：[川宇C289，DFRobot SKU FIT0548](https://www.dfrobot.com.cn/goods-1605.html)，网页价8元，数量1。实际库存数量、清远运费/发货未确认。它用于准备/导出，不是核心运行依赖；若用户实际已有可用读卡设备可据实去重，当前不暗算已拥有。

存储卡检索的两条原厂商城结果已明确下架：[FIT0570/32GB](https://www.dfrobot.com.cn/goods-1708.html)、[FIT0394/16GB](https://www.dfrobot.com.cn/goods-1037.html)，均不列可购买项，不以旧介绍/关联推荐冒充现货。卡的准确可买SKU、人民币价和交期仍需继续核对。

来源：[Sipeed原厂Nano20K](https://wiki.sipeed.com/hardware/en/tang/tang-nano-20k/nano-20k.html)及本地官方3921原理图。没有借板载单声道功放替代PCM5122/AUX。
'''
(E/'Nano-TF-storage-scope-current.md').write_text(md,encoding='utf-8')
gates=[dict(id='G1',item='84路传感前端',state='35项数值已提交，验收口径待用户决定；同源制造、预焊报价、交期未闭合'),dict(id='G2',item='控制/编辑/存储/保护',state='三独立键串接候选逐针合同与64件电气清单已生成；完整预焊板、布局/CPL、固件读回和产品动作语义未签收'),dict(id='G3',item='J10完整屏配置',state='等待已约定的完整配置/含运报价/出货日；物理针序未全部冻结'),dict(id='G4',item='PCM5122到3.5mmAUX',state='准确55元音频板候选保留；初始化、共享模拟路径人口、输出RC保护、准确转接件与供电仍待关闭'),dict(id='G5',item='全部采购附件与预算交期',state='板载TF卡座已核可省外部FPGA读卡模块；卡SKU未选；电极、线束、结构、供电、代焊运费均须补齐，总价≤700未证'),dict(id='G6',item='实体整机与视频',state='完整产品物理顶层/驱动/时序及12条实测未签收；没有将旧板测继承为新整机通过')]
readiness=dict(at=now,trigger='User asks whether onlySAVE/CANCEL interface remains and requests continue',only_one_remaining_item=False,all12requirements_retained=True,current_new_progress=['Three independent actions electrical/serial contract proposed;65536parallelpatterns checked, noRTL','Original56+8new=64candidate component allocation generated, excludes newconnectors andpreweldquote','OwnedNanoTFsocket verified byschematic; noextraFPGA-sideTFreader; cardstillneeded'],gates=gates,reference35_approval=False,complete_purchase_plan=False,whole700budget_closed=False,physical_tests='UNMEASURED',no_CAD_RTL_orders_or_messages=True,read_first=str(E/'edit-control-interface-current.md'),storage_read_first=str(E/'Nano-TF-storage-scope-current.md'))
save('module-readiness-current.json',readiness)
text='# 当前距离采购组装的剩余工作\n\n2026-10-27：不是只差保存/取消接口。新增三键候选解决的是电气输入设计，不能把它算成已经买到预焊成品或产品编辑功能已实现。\n\n|组|项目|实际未完成项|\n|---|---|---|\n'
for g in gates:text+='|'+g['id']+'|'+g['item']+'|'+g['state']+'|\n'
text+='\n新增进展：edit-control-interface-current.md/json列三键最小增量、全部脚号和位序；control64-candidate-BOM-current.csv/json列原56项和新增8件，未冒充正式BOM/CPL；Nano-TF-storage-scope-current.md/json保留板载TF证据、排除下架卡。不改PCB/RTL、不下单或外发询价。35项口径仍未获明确批准。\n'
(E/'module-readiness-current.md').write_text(text,encoding='utf-8')
for name in ['PCB-CURRENT-CAPACITY-RECOVERY-20261024.json','PCB-ACTIVE-WORK.json','实体交付当前入口.json','模块方案-当前证据.json']:
 p=B/name;x=json.loads(p.read_text(encoding='utf-8-sig'));x.update(updated_at=now,module_readiness_current=readiness,edit_control_interface_current=str(E/'edit-control-interface-current.json'),Nano_TF_storage_scope_current=str(E/'Nano-TF-storage-scope-current.json'));p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=B/'模块方案-当前工作单.md';s=p.read_text(encoding='utf-8-sig');s+='\n\n## 用户要求继续关闭编辑操作接口（2026-10-27）\n\n仍有六组采购/组装前缺口，见module-readiness-current.md/json。新增三独立实体键APPLY/SAVE/CANCEL的同总线165串接候选已形成逐针/16位序合同，原56+新增8件=64件电气分配，未增加外部FPGA GPIO、未改原图/RTL，不把新增第二165误称原有或8泛音实体键。65536种离线并行输入位序检查通过，仅设计模型，不是固件/板测。原Nano的TF座/上拉/去耦/FPGA80—85由官方3921图复核，省外部FPGA读卡模块，仍需卡/必要USB读卡器及实际PCM驱动验收。准确SKU库存核价受403阻断，原厂两款卡已下架；保存实际错误，不盲重试或视旧库存为现货。35项参考口径仍未批准，总价/预焊/清远到货未闭合。\n';p.write_text(s,encoding='utf-8')
print(json.dumps(dict(candidate_control_rows=len(rows),new_electrical_parts=8,readiness_groups=len(gates),only_one_remaining_item=False),ensure_ascii=True))
