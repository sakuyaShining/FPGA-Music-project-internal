from pathlib import Path
import json,hashlib,datetime
B=Path(r'D:\FPGA-Project\codex-deliverables\dual-screen-review-20261020-v2');E=B/'module-plan-current-evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
scope=read(E/'product-spec-12-comparison-current.json');front=read(E/'sensor-header-fanout-current.json')
rows=[
 dict(id='C1',class_name='可控且可迅速完成',work='12条需求→验收证据/责任/依赖清单',time='本轮已完成计划；详细证据表可在一个工作段内整理',dependency='已有规格、当前证据',done='每条明确所需实物操作、通过条件和证据；未验收不标通过',requirements=['R01','R02','R03','R04','R05','R06','R07','R08','R09','R10','R11','R12']),
 dict(id='C2',class_name='可控且可迅速完成',work='25音位/84电极用途与接口合同草案',time='2—4个专注工作小时的文档工作预算，不含电气/实物资格',dependency='沿已确认75音位电极+5八度+4备用；候选针序仍需验证',done='84个物理电极唯一用途/采集索引/连接器；所有C5与逐指位置/面积维度不漏项；未冻结音乐语义单列',requirements=['R02','R06']),
 dict(id='C3',class_name='可控且可迅速完成',work='完整接线/附件/预算表编制与核算',time='SKU/电路冻结后2—4个专注工作小时；现在只能形成缺项明确的草案',dependency='每项型号、接口、预焊状态、真实价格齐全',done='每根导线起止针号/电压/回流、转接与固定材料及运费代焊计入≤700；无隐藏SMT焊接',requirements=['R03','R06','R07','R09','R12']),
 dict(id='C4',class_name='可控且可迅速完成',work='视频脚本、镜头清单和分步验收记录模板',time='约1—2个专注工作小时的文档预算',dependency='原12条目标；核心演示顺序可提前安排',done='每项需展示的真实操作/画面/音频与证据明确；不以预录声音冒充即时演奏',requirements=['R01','R02','R03','R04','R05','R06','R07','R08','R09','R10','R11']),
 dict(id='T1',class_name='较不可控：技术问题决定耗时',work='完整预焊传感前端可制造设计',time='设置10月28日18:00检查点；不是完成承诺，不再用1—2天担保',dependency='右6电极路径+7控制网、完整候选、真实重铺/参考/全部旧接触/DC/物理DRC、原理图/针序/制造一致',done='同版可交工厂的真实源及制造文件；保存关闭重开通过；84用途/校准/全部保护保留',requirements=['R02','R11','R12']),
 dict(id='T2',class_name='较不可控：技术与可买实现均待闭合',work='控制/存储/断电隔离/电源保护/AUX完整可装实现',time='10月28日18:00同一设计检查点；当前无可信完成上限',dependency='现有部分直插候选并非完整预焊模块；电源/电平/保护/线材和真正可买组装方式',done='不让用户焊SMT；AUX线路输出/启动静音、反灌/关断、电源峰值均有买前资格证据，未删原功能',requirements=['R03','R06','R07','R09','R10','R12']),
 dict(id='T3',class_name='较不可控：整机接合不能按修一两个接口估时',work='四槽/逐指表达/触屏/实体编辑与保存/PCM录放/曲谱与现场共享资源的产品固件',time='先做最新真实进度与缺口盘点；缺完整任务分解，不能给1—3天上限',dependency='原负责实现工作区的可追溯源码/构建/引脚合同；本聊天仅只读核验，不擅改RTL/构建/烧录或消息他聊',done='与最终接线一致的产品顶层、时序合格构建及码流；真实源/编辑保存/录放共同运行，非命令刺激替身',requirements=['R01','R02','R03','R04','R05','R06','R07','R08','R10']),
 dict(id='T4',class_name='较不可控：结果可能迫使返工',work='实物传感标定、串扰、并发最坏延迟、电源/音频与整机稳定性',time='内部倒排至少保留10月31日—11月2日；不是承诺三天内必能修好',dependency='全部硬件到货且产品固件可用',done='25音位含C5表情成立；完整84采样/触屏/录放并发；最坏≤10ms；掉电恢复；AUX/供电实测',requirements=['R01','R02','R03','R07','R08','R09','R10','R11']),
 dict(id='X1',class_name='不可由本聊天保证：外部供应',work='屏幕完整配置含运价/现货/发货承诺',time='10月27日—28日取得实际回复是倒排目标；当前未收到',dependency='用户已同意询价；厂家页面真人验证未绕过',done='同一ER-TFTM070-5V4配置、CTP、预焊40针/配线、含运价及寄清远发货/到货信息；非基础价',requirements=['R03','R04','R12']),
 dict(id='X2',class_name='不可由本聊天保证：外部供应',work='小板/必要控制电路的真实预焊报价、排产、良率、出货和运输',time='需工厂实际确认；不得预填2天或3天。到齐目标10月30日晚',dependency='可制造文件及选定预焊方式、库存、工厂产能、付款授权由用户决定',done='明确买来即装的交付内容；报价含必要TH装配/运费；确认时间能支持装配视频',requirements=['R02','R06','R07','R09','R12']),
 dict(id='X3',class_name='不可由本聊天单方决定：用户/验收规则',work='真正尚未定且影响实现的操作语义与测试资源',time='先核已有直接决定，避免重复询问；仅真实缺项请用户决定',dependency='八度切换对在奏音、编辑试听/应用/保存/取消、曲谱来源/录入和录放修饰对象等现有记录',done='没有擅自删功能、替换成电脑操作或默降两层；视频所需外接AUX播放/录音资源确有安排',requirements=['R02','R04','R05','R06','R07','R08','R09'])]
milestones=[
 dict(date='2026-10-27',goal='当天优先完成真实缺口/采购依赖/验收清单，并推动完整屏报价；已有方案只作候选',failure_meaning='当天未收口不是自动砍功能；将未定项列入检查点，不继续只报局部线数'),
 dict(date='2026-10-28T18:00:00+08:00',goal='内部方案检查点：84前端及控制保护实际可制造/可装方案、硬件接口合同；必要固件缺口已明确',failure_meaning='若仍无可制造前端或完整可装控制方案，完整12条按期交付风险显著；立即报告具体障碍/同功能替代与实际工期，不扩大搜索时限或自动减功能'),
 dict(date='2026-10-30T20:00:00+08:00',goal='倒排到齐目标：关键预焊硬件、屏、线束/配件到齐，同时匹配产品固件可进入联调',failure_meaning='若关键件仍无可靠到货承诺，或固件仍缺关键闭环，原完整交付排期没有足够正常联调缓冲；需基于事实决定交付路径，不能靠纸面进度确认可行'),
 dict(date='2026-10-31/2026-11-01',goal='组装、电源/AUX、单银行→六银行84路标定、触屏/控制/存储与录放分步联调',failure_meaning='失败先隔离根因，记录实际电气和功能证据；不把旧板测或离线通过替代'),
 dict(date='2026-11-02',goal='完整12条联合演示彩排/稳定性与最坏延迟，留修正时间',failure_meaning='仍缺核心功能或≤10ms证据时如实报告，不临时虚报整机达标'),
 dict(date='2026-11-03',goal='拍摄、录音、剪辑和导出检查；内部目标当晚完成，11月4日不再作为主开发日',failure_meaning='拍摄必须基于真实已能完成的操作；未批准削减仍未获批准')]
plan=dict(at=now,timezone='Asia/Shanghai',deadline='2026-11-04',internal_video_target='2026-11-03 evening',baseline=str(E/'product-spec-12-comparison-current.json'),
 scope='All12 product requirements, later authorized module/hybrid manufacturing form,500-700CNY allin,preweld preferred,onlyNano20K owned',
 time_interpretation='C budgets are focused document/audit effort after named prerequisites, not wall-clock product completion guarantees. T checkpoints are timeboxes for review, not promises. X durations unknown until external confirmation. Do not add rows serially or assume all work parallel.',
 rows=rows,milestones=milestones,
 critical_paths=[['Complete compatible hardware scheme','Actual quote/stock/preweld dispatch','Parts arrive','Assembly/calibration','Full12function/latency proof','Video'],['Current actual firmware gap inventory','Product physical integration and timing-qualified build','Hardware/firmware joint test','Video']],
 current_distance='Hardware scheme not frozen; no complete buy-and-assemble plan; external quote/delivery not committed; product firmware fullintegration not accepted; all new physical testsUNMEASURED. Not at final assembly-only stage.',
 risk_conclusion='Nov4 full12 delivery cannot currently be substantiated. It remains possible only if hardware supply and product firmware close early enough for real assembly/tests/video; no success probability or guaranteed date is claimed.',
 owners=dict(this_chat='Hardware plan/evidence, sourcing research without seller messaging/order, read-only registered-source contract checks; no RTL/build/flash',user='Previously agreed screen quote; purchasing and physical assembly/video when exact plan is ready; unresolved choices only when truly necessary',suppliers='Availability/assembly quote and production/delivery commitments',firmware='Implementation in its authorized producer context; this plan does not message or assign work to another chat'),
 no_function_cut=True,no_order_payment_outbound_message=True,no_new_automation=True,no_CAD_RTL_build_flash_changes=True,physical_tests='UNMEASURED')
write(E/'delivery-risk-plan-current.json',plan)
md='''# 11月4日前完整实体与视频交付：时间可控性计划

以PRODUCT-SPEC.md全部12条为范围；允许模块/必要简单预焊小板，但不删功能。预算全部新增硬件、线束/电极/固定材料、电源、预焊/运费≤700元；仅Nano20K在手。以下时间是规划预算/检查点，**不是已经确认的完成日期、厂家交期或实测成功承诺**。

## 一、可控且能迅速完成

| 工作 | 工作预算/条件 | 具体交付 |
|---|---|---|
| 12条→验收/依赖/责任清单 | 本轮已作完整分类；详细记录可一个工作段整理 | 每条对应实际操作与证据，未完成不标绿 |
| 25音位/84电极用途与接口合同草案 | 2—4个专注工作小时，只是文档工作预算 | 75+5+4用途/采集位/针号；逐指位置/面积、C5不遗漏，未定操作语义列出 |
| 全部接线/附件/预算表 | **准确SKU与电路冻结后**2—4小时文档预算 | 每根线起止/电压/回流、转接固定与运费代焊入账；当前不能跳过SKU/报价直接称可买 |
| 视频脚本/镜头与验收模板 | 约1—2小时文档预算 | 演奏、表情、右手、编辑保存、录放/曲谱合奏、脱机与延迟等真实演示步骤 |

这类文档不需要等待硬件全到齐，可先做；做完文档不等于功能已经实现。

## 二、较不可控：需要解决技术或集成问题

| 工作 | 当前真实缺口 | 何时检查/通过条件 |
|---|---|---|
| 84路完整预焊前端 | 右6电极路径+7控制网；完整候选真实重铺/参考/回流/旧接触/DC/DRC与同版制造 | **10月28日18:00内部检查点**，检查是否已有可制造、可预焊的完整方案；不把1—2天当完成担保 |
| 控制/存储/保护/AUX | 已核部分直插件不是完整预焊模块；断电隔离、电源容量/保护及3.5mm线路配套未闭合 | 与前端同一检查点；必须明确买来可装，不能隐藏贴片焊接或用普通模块漏必要电路 |
| 完整产品固件 | 四槽、逐指表达、屏、实体编辑保存、真实PCM/曲谱与现场共享资源等整机接合证据未齐 | 先核真实最新源码/构建/缺口，再分解实现；当前**不能给1—3天可信上限**。本聊天仍只读，不改RTL/构建/烧录或消息其他聊天 |
| 到货后的真实联调 | 传感寄生/串扰/标定、电源/音频、并发丢帧与≤10ms等结果未知，可能返工 | 倒排保留**10月31日—11月2日**；这是缓冲安排，不是三天一定修得好的保证 |

目前14路排针扇出+左8完整路径仅为离线物理/连通候选。Ground假设模型未验收，原生仍21网56项，不能把局部成功乘六当六块前端可装交付。

## 三、不可由本聊天保证的环节

| 环节 | 依赖谁/什么 | 必须取得的实际证据 |
|---|---|---|
| 屏完整配置/价格/现货 | 用户已同意询价、厂家实际回复 | 同一SPI/5V/FT5316/预焊排针及线束、含运价和清远发货到货信息；不套基础价 |
| 工厂预焊/排产/物流 | 完整制造文件、实际库存、工厂产能和运输 | 六板及必要其他电路真实报价、装配范围、发货/到货承诺；**目前没有已确认交期** |
| 尚未定且阻塞的操作语义 | 已有直接决定及用户必要选择 | 先查证、不重复问已决定事项；只把真正尚未定的八度在奏音/编辑反馈/曲谱来源等请用户决定，不擅自减功能 |
| 视频外接播放/录音资源 | 实际可用AUX设备/录音方式 | 无须内置喇叭；如确需额外购买试听设备，先单列预算和用途，不默认产品必购 |

“不可控”表示本聊天不能保证结果/时长，并不是无事可做：可核实库存交期、准备明确报价资料、选同功能现货替代并记录条件。但未回复时不能自行填一个交期。

## 四、倒排检查点（均为内部目标，未获供应商承诺）

| 日期 | 目标 | 若未达成的含义 |
|---|---|---|
| **10月27日** | 完整缺口/依赖/验收清单；推动屏完整报价，继续必要设计与接口核对 | 不再仅以局部走线数报告整体进度 |
| **10月28日18:00** | 前端与控制保护可制造/可装方案、完整硬件接口合同；固件真实缺口已明确 | 若仍无完整前端/控制实现，完整交付风险显著，必须给具体阻塞与同功能替代，不能无限试布 |
| **10月30日晚** | 关键预焊件/屏/全部配件到齐，同时产品固件可进入联调 | 若仍无可靠到货承诺或关键固件闭环，原完整排期缺正常联调缓冲，不能继续宣称稳妥可交 |
| **10月31日—11月1日** | 组装、逐级电源/AUX/单组→六组传感、触屏/控制/存储录放联调 | 记录并修复真实问题，不用历史小样替代 |
| **11月2日** | 完整12条联合演示彩排、稳定性/最坏延迟核验，修正 | 缺项如实列出，不自动删掉难演示的功能 |
| **11月3日** | 拍摄、录音、剪辑、导出检查，当晚完成内部视频目标 | 11月4日不留作主开发日；不得用预录声音伪装实时功能 |

## 五、距离最终交付的位置

硬件关键链：**兼容完整方案 → 真实报价/库存/预焊 → 到货 → 组装标定 → 12条联合实测 → 视频**。

固件关键链：**最新真实缺口盘点 → 产品物理接合与时序合格构建 → 与实物联合验证 → 视频**。两条链必须都完成；供应确认期间可做文档和已有源码核对，但不假定所有开发/大型几何/实物都能并行。

现在硬件尚在方案冻结前，固件缺完整整机签收证据，外部交期未确认，实物UNMEASURED；**还没有进入“只差装起来拍视频”的阶段**。完整12条在11月4日前能否交付，目前缺足够证据证明。功能没有获准削减，本计划不擅自砍功能或延后某条验收，也不下单或修改另一聊天。
'''
(E/'delivery-risk-plan-current.md').write_text(md,encoding='utf-8')
for n in ['PCB-CURRENT-CAPACITY-RECOVERY-20261024.json','PCB-ACTIVE-WORK.json','实体交付当前入口.json','模块方案-当前证据.json']:
 p=B/n;d=read(p);d['updated_at']=now;d['delivery_risk_plan']=str(E/'delivery-risk-plan-current.json')
 if 'read_first' in d:d['read_first']=list(dict.fromkeys([str(E/'delivery-risk-plan-current.md')]+d['read_first']))
 write(p,d)
p=B/'模块方案-当前工作单.md';t=p.read_text(encoding='utf-8');marker='\n## 完整交付可控性与倒排计划'
p.write_text(t.split(marker)[0]+marker+'\n\n计划见module-plan-current-evidence/delivery-risk-plan-current.md/json。按全部12条分可控文档/较不可控技术集成/外部不可保证交期；10月28日18:00方案检查点，10月30日晚为关键到齐倒排目标，10月31日—11月2日留组装联调，11月3日完成内部视频目标。均非供应商承诺/功能必成保证。前端仍未制造放行；固件完整产品接合亦未签收，不能仅以6条走线估算离交付距离。不减功能、不新建自动化、不改RTL/烧录或外发消息。\n',encoding='utf-8')
for src,name in [(Path(scope['spec_source']),'product-spec-baseline-source-current.md')]+[(Path(x['path']),'pitch25-user-decision-source-current.json' if i==0 else 'C5-three-electrode-source-current.json') for i,x in enumerate(scope['pitch_decision_sources'])]:
 (E/name).write_bytes(src.read_bytes())
files=['delivery-risk-plan-current.py','delivery-risk-plan-current.json','delivery-risk-plan-current.md','product-spec-12-comparison-current.py','product-spec-12-comparison-current.json','product-spec-12-comparison-current.md','audio-AUX-scope-current.json','audio-AUX-scope-current.md','audio-playback-sourcing-current.json','product-spec-baseline-source-current.md','pitch25-user-decision-source-current.json','C5-three-electrode-source-current.json']
p=B/'模块方案-当前证据.json';d=read(p)
for f in files:d.setdefault('evidence_sha256',{})[f]=sha(E/f)
d['local_comparison_update_remote_pending']=True;write(p,d)
write(E/'delivery-risk-stage-file-map-current.json',dict(at=now,evidence_files=files,native_file_checks=read(E/'control-power-current-plan.json')['native_file_checks'],plan=str(E/'delivery-risk-plan-current.md'),scope='All12 delivery uncertainty planning + corrected AUX and exact source snapshots; no implementation changes'))
print(json.dumps(dict(plan_saved=str(E/'delivery-risk-plan-current.md'),rows=len(rows),milestones=len(milestones),deadline_guarantee=False,physical_tests='UNMEASURED'),ensure_ascii=False))
