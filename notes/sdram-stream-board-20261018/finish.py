# -*- coding: utf-8 -*-
from pathlib import Path
import json,hashlib,zipfile,subprocess,sys,datetime
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent;R=P/'experiments/sdram_stream_board_20261018';E=R/'evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
assert not (R/'delivery.json').exists(),'preserve existing evaluated snapshot'
up=read(R/'upstream.json')
for key in ('stream','timing'):
 U=Path(up[key+'_root']);assert sha(U/'delivery.json')==up[key+'_delivery_sha256']
 for rel,h in up[key+'_files'].items():assert sha(U/rel)==h,(key,rel)
frozen={}
for name in ('pcm_sdram_stream.v','pcm_sdram_arbiter.v','pcm_storage_buffers.v','pcm_sync_fifo.v','sdram_word_controller.v'):
 rel='rtl/'+name;assert sha(R/rel)==up['stream_files'][rel];frozen[rel]=sha(R/rel)
for name in ('board-model','final-check','timing-audit','hardware-audit','history-audit'):
 d=read(E/(name+'.json'));assert d['status'].startswith('PASS')
 root=P if name in ('hardware-audit','history-audit') else R
 for rel,h in d['inputs'].items():assert sha(root/rel)==h,(name,rel)
a=read(E/'timing-audit.json');h=read(E/'hardware-audit.json');history=read(E/'history-audit.json')
S=P/h['hardware_directory'];hw=read(S/'result.json');assert len(hw['runs'])==2 and len(history['failed_attempts'])==4
backups=[]
for pointer in ('latest-backup.txt','final-check-backup.txt'):
 B=Path((N/pointer).read_text());items=read(B/'manifest.json')
 with zipfile.ZipFile(B/'before.zip') as z:
  assert z.testzip() is None
  for v in items.values():assert hashlib.sha256(z.read(v['member'])).hexdigest()==v['sha256']
 backups.append(dict(root=str(B),files=len(items),sha256=sha(B/'before.zip'),manifest_sha256=sha(B/'manifest.json')))
engine=read(P/'experiments/register_memory_20261018/delivery.json')['source_engine']
for label,cwd,args in [('main',P,['tools/scripts/project_baseline.py','--check','notes/baselines/main-2026-10-09-board-diag.json']),('engine',Path(engine['root']),['tools/scripts/project_version.py','check','project/versions/engine-safety-20261014-01.json'])]:
 out=subprocess.run([sys.executable,*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
 (E/('identity-'+label+'.log')).write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode==0
title='83-录放SDRAM调度板验与诊断比较修正-2026-10-18.md'
entry=f'''**2026-10-18录放SDRAM板验**：见[83号]({title})与`experiments/sdram_stream_board_20261018/project/CURRENT.md`，版本`sdram-stream-board-20261018-v4`。先备份19项、诊断修订前再备份117项；82号五个搬运RTL逐字节保持。实际COM6/B、ID81B仅操作2 SRAM，默认1024字FIFO/每向256KiB环形区，两次完整静音合成图案测试各1345540内存事务：266240样本/方向含两次回绕、停止后排空、在途/阻塞请求清空、132097连续前缀、8次读空和4096样本/方向恢复均在限定范围**已验证**。早期四个物理版本最终前缀比较异常均保留FAIL并恢复76号；分字节寄存复核后两次通过，未证明旧异常根因为工具或排除全部时序因素。选定v4加严PnR setup/hold +4.205/+0.011ns，余量紧、原始时钟布线警告/确切die温压/完整联合时序仍**待验证**。已恢复76号，身份/512拍/2048零PCM确认，无Flash/TF操作。新调度限定板验完成，文件/非易失/最终混音/真实音乐录放及完整联合PnR仍**待实现/待验证**，整机**部分实现**。下一步先恢复逻辑余量并做音乐＋存储联合时序，再接回放混音/TF文件，不能用独立诊断余量签整机。'''
report=f'''# 录放SDRAM调度板验与诊断比较修正 · 2026-10-18

## 0. 结论、版本和现有固件

82号录放搬运路径在真实Nano20K/封装内SDRAM、默认1024字短FIFO和每方向256KiB环形区上，完成两次完整合成图案诊断，在下述限定范围**已验证**。这一步验证数据搬运与异常恢复，没有真实演奏音频录制、文件保存或伴奏与现场声音混音；完整产品仍**部分实现**。

版本`sdram-stream-board-20261018-v4`，入口`experiments/sdram_stream_board_20261018/project/CURRENT.md`。先读38/39与工作树分布、git状态和main基线；备份19项实现/约束/回退镜像等，再在诊断修订前备份117项并逐项校验ZIP。main HEAD仍fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12，main192/engine246输入身份复核PASS。82号五个搬运RTL和80/81/82交付文件均保持；本轮只新增包装/诊断/验证，不改音乐引擎、GUI或音乐规则，不重写旧快照。

实际识别FTDI2025030317B/COM6、JTAG单器件GW2AR ID0000081B；仅operation_index=2 SRAM Program。音频四输出固定低，全程静音；未访问Flash/TF或采购。每次失败及最终成功后均恢复76号config-sram.fs，最终C0=72/C2=76/C3=1/D0=75/D1=1/A4=D3/A9=32，active/fingers=0，采样间隔512拍，2048个内部PCM样本全零。GUI仍用76号launch_gui.cmd。两次重新下载不等于两次断电测试，本轮没有新增物理S2或模拟听感结论。

## 1. 独立诊断包装和真实覆盖

沿用81号27→27MHz PLL（VCO864MHz）、锁定前复位/同步释放、S2/87高有效和55个SDRAM内部SIP端口；外部仍13脚（时钟4、复位87、UART69、LED15～20和静音音频51/54/55/56）。PnR引脚表核对内部p*映射，避免误把SDRAM端口分配为板边GPIO。

`sdram_board_top.v`使用82号原始pcm_sdram_stream/arbiter/双FIFO和81号原控制器，自动产生两个不同盐值的16位计数图案，内部逐字比较返回数据。正常阶段sample_tick=512拍，符合现有52.734375kHz；异常阶段加速到32拍以快速填满缓存，不把它说成产品采样率。新增诊断状态和串口不接音乐引擎，也没有TF/媒体消费者。

默认每方向131072个16位SDRAM字（256KiB），录制区000000～01FFFF、回放区020000～03FFFF，合计512KiB。新测试访问这两个区域，并非本轮又扫了全部8MiB/四bank；全地址双图案旧证据仍属于81号。

每次完整测试的六项条件：

1. 每方向266240个正常样本，超过2×131072，读/写指针各经过两次环形回绕；双路同时运行，含主机录制消费者暂停及回放生产者暂停。正常期无内部数据不一致/溢出/读空报告。
2. 内存请求已呈现但被阻塞时，对两路发clear；固定保持32拍，检查请求地址/数据/有效位保持，并检查该方向不能提前done，开放请求后再清退。
3. 已接受请求、尚等响应时发clear，记录一次在途清空事件，确认等待响应退出后完成；两方向clear合计6次done（3轮×2）。
4. 故意不消费录制数据直至溢出，随后逐字核对132097个连续前缀样本，即131072环形字＋1024短FIFO字＋1预取保持字；没有把后续缺口后的样本接上。
5. 无播放数据时触发8次明确miss，不能把上一字重复标为有效；异常标志在clear后复位。
6. 使用新图案恢复，每方向再4096样本，数据与计数一致；两段正常阶段停止采入后总计排出8193个积压样本。

每次内存接受总数1345540，等于4×(266240+4096)＋2×132097＋2个被清退的诊断事务；两次合计2691080。最终tests=3F/state18/flags25/error0，四个恢复计数均4096，prefix132097/miss8/clear6/held32/inflight1。UART分别49/50个64字节原子快照，校验错误0；原始字节离线重新解析、核对帧和计数及下载/回退日志，绑定当前源码/约束/码流哈希。

最终内部运行计数149131337拍，按27MHz约5.523秒；主机打开串口后约4.55秒见PASS，因为设计已在下载结束期间开始运行，这个串口等待时间不能当完整测速。正常＋恢复每方向270336样本，双次每方向540672；均是合成测试图案，不是用户音频录制。

## 2. 早期失败与诊断修订

四个早期物理尝试全部保留为FAIL，不能算通过：revision0汇总条件报code11；拆开判据后的revision1、显式32位常量的revision2，以及单一错误选择/状态写入的revision3均报code12（最终prefix检查）。这些版本已完成正常数据和异常恢复，报告的prefix132097/clear6/after_stop8193符合预期，但最终内部比较仍判失败。每轮都自动回76号并回读2048零PCM，未覆盖失败记录或在原码流上改标签。

最终revision4把32位prefix比较拆为四个字节的异或归约，分别寄存，在下一状态检查四位不匹配标志，再发布最终成功位。原32位相等要求不变，没有忽略前缀长度或放宽成功条件。最终两次真实运行均通过。单一错误选择、独立最终状态及明确常量位宽也保留，用于清晰地记录错误优先级。

**旧异常的精确根因仍待定位。** 原RTL/缩小包装仿真没有复现该失败；分阶段、显式位宽和错误选择改写单独均未解决，不能据最终改写有效就断言是高云工具BUG，也不能绝对排除映射/时序等因素。教育版综合网表受保护，本轮未进行其门级功能比对，也未解密。该问题属于独立诊断最终比较路径，未修改82号搬运源去迎合PASS；旧版镜像不作为合格候选。后续联合时序/更长运行验证必须保留该风险。

## 3. 仿真与失败反例

最终包装在自写SDR命令/时序模型中，对3/10/16ns读返回延迟各跑85071拍、11帧；使用缩小FIFO2/环形3参数和正常48/恢复24样本，覆盖同一六阶段流程与一次模拟S2在阻塞事务中的复位重初始化。最终回报prefix13/miss8/clear6/held32/inflight1，刷新195次、最长间隔396拍。PLL以功能宏旁路，不模拟锁定/抖动；该模型非原厂完整die模型，不验证真实电气/温压。

三种故意错误包装分别改错录制图案、回放图案和帧校验，均被对应code1/code2/帧校验断言拒绝。另有默认实际位宽的38项最终判据单元测试：正确计数通过，错误测试掩码/前缀/clear/停止后计数被拒绝；前缀32个位逐一翻转全部拒绝。这是定向最终判据测试，刻意直接设置内部状态，不能当额外流量或门级验证。

测试夹具最初等待state H_REQ且hold5时复位，而该状态在hold5前已进入H_WAIT，导致没有实际触发复位；修正到H_WAIT并明确要求reset计数1后才通过，原先未触发复位的结果不作验收。没有为通过测试删除真实复位判据。原82号全随机/整链源保持，未重跑全部音乐/配置/显示回归，不把源码身份核对列为功能重跑。

## 4. 时序、资源与边界

SDC沿81号工程包络，32位DQ输入min/max、52位动态输出min/max与相关生成时钟均核对；只对外部复位源与异步LED/UART状态端点设例外，不给SDRAM或核心时钟增加false path。静态审计读取实际setup/hold/recovery/removal路径表，不能仅凭TNS0放行。所有构建正常工具退出，生成源码副本、工程/Tcl和报告均绑定哈希；最终选定build_stress_v4。

| v4独立诊断构建 | setup/ns | hold/ns | recovery/ns | removal/ns |
|---|---:|---:|---:|---:|
| 正常工程包络 | +5.705 | +0.013 | +32.142 | +2.471 |
| 加严包络、实际下载 | +4.205 | +0.011 | +31.642 | +2.171 |

正常包络输入max6.5/min1ns、输出max3/min−2ns、setup/hold不确定性0.5/0.2ns；加严输入max10ns、输出max4/min−3ns、不确定性1/0.5ns，仍27MHz。早期revision0正常构建hold仅0.002ns，故从开始就选择加严独立布局实测；最终仍只有0.011ns保持余量，不能称余量宽裕或完整资格通过。

v4诊断PnR2578Logic/1395寄存器/13外部IO，包含测试状态、图案比较和原子UART快照；它没有完整音乐/可视化/传感/文件链。82号完整逻辑探针20422Logic/31BSRAM、余314/15仍只属于该联合综合，**音乐＋存储＋实际时钟顶层的联合PnR仍待实现/验证**，不能用独立诊断余量签整机装得下。

残留PR1014在原始PLL输入clk_d，核心logic_clk用PRIMARY；轮转候选3→2位截断警告是82号原有模4索引，该源未改。确切封装内die/速度档/封装延时未绑定，SDC为工程假设；默认报告只列各类最坏25条路径，不是逐位完整证书。未做示波器边沿/电源温度扫描、长时间保持、物理S2或断电循环。合成图案不是完整March/地址别名故障覆盖。

## 5. 当前状态与下一步

| 项目 | 状态 | 后续 |
|---|---|---|
| 82号默认双向数据搬运、环形回绕/清退/恢复实体路径 | 已验证 | 限本板两轮合成图案/上述条件 |
| v4逐字节寄存最终判据 | 已验证 | 单元/包装与两轮实板；旧比较异常根因待定位 |
| 原76号固件恢复/身份/静音 | 已验证 | 本轮不新增听感或模拟音质结论 |
| 完整音乐＋实际存储顶层联合资源/时序 | 待实现/待验证 | 现有Logic余314，先恢复空间和联合PnR |
| TF块/文件、事件轨配对、非易失配置 | 待实现 | SRAM/SDRAM均不能替代断电保存 |
| 真实录音＋伴奏回放与现场声音混音、实体/GUI命令 | 待实现 | 本轮没有把play_data接回DAC或保存用户音频 |

下一步先恢复必要逻辑余量，准备音乐＋实际SDRAM时钟/接口联合时序，再接独立回放PCM与现场合成的混音及TF块/文件闭环。新增实现仍应先隔离、备份、带独立参考验证，不能减少复音/泛音或改右手分区/松手保持/全和弦等用户规则来换资源。叠录/循环/轨数/异常听感等未决语义不在本轮冻结。

离线入口check_board.py/check_final.py/audit_timing.py/check_hardware_evidence.py/check_history.py；verify_delivery.py只检查身份，不打开串口。notes中的bench_hardware.py会真实临时下载并恢复，不能混入普通回归。协议见project/BOARD_PROTOCOL.md。delivery.json在上述检查完成后新建，绑定两份备份、全部历史失败和最终有效证据；旧快照保留。
'''
(P/'docs/02-技术方案'/title).write_text(report,encoding='utf-8')
for prefix in ('38-','39-','49-'):
 path=next((P/'docs/02-技术方案').glob(prefix+'*.md'));text=path.read_text(encoding='utf-8')
 assert '**2026-10-18录放SDRAM板验**' not in text
 if prefix=='38-':
  anchor='## 0. 最重要的发现：最新成果并不都在 main\n';assert anchor in text;text=text.replace(anchor,anchor+'\n'+entry+'\n',1)
 else:first,rest=text.split('\n',1);text=first+'\n\n> '+entry+'\n'+rest
 path.write_text(text,encoding='utf-8')
(R/'project/CURRENT.md').write_text(f'''# 当前录放SDRAM调度板验 · 83

版本sdram-stream-board-20261018-v4；完整产品部分实现。报告../../../docs/02-技术方案/{title}

- 82号五个搬运RTL保持；原音乐引擎/GUI/旧交付不改。
- 默认FIFO10/RING17（每向256KiB）两次合成图案板验通过，各1345540事务，六项mask3F。
- 双向回绕、停止后排空、阻塞/在途清空、连续前缀、读空和恢复在限定范围已验证。
- 旧四次最终比较异常均为FAIL，不能计通过；v4逐字节寄存复核有效，旧根因仍待定位。
- 实际下载加严v4 setup/hold +4.205/+0.011ns，余量紧；完整音乐联合PnR/确切die/温压仍待验证。
- 已恢复76号，身份/512拍/2048零PCM确认；GUI仍../envelope_resources_20261017/launch_gui.cmd。
- 未读写Flash/TF，全程静音，无物理S2或新听感/断电验收。
- TF/文件/非易失/最终混音/真实音乐录放仍待实现；不能把合成诊断当录制伴奏完成。
- verify_delivery.py/check_hardware_evidence.py仅离线；notes下bench脚本会真实下载后恢复。
''',encoding='utf-8')
(R/'project/BOARD_PROTOCOL.md').write_text('''# 独立83号静音诊断协议

本协议仅该测试镜像，不是音乐固件寄存器协议。UART115200/8N1，每0.1秒原子64字节，全部多字节小端。字节0..2=A5/83/01，63为0..62异或。state18成功、19失败；字节4位0 PASS、1 FAIL、2 initialized、3 overflow、4 underflow、5 PLL lock、6 busy；字节5的六个完成位对应83号六阶段。

| 字节起点 | 长度 | 内容 |
|---|---:|---|
| 3 | 1 | 状态 |
| 4/5 | 各1 | 标志/六项完成掩码 |
| 6 | 4 | 内部运行拍数 |
| 10/14/18/22 | 各4 | 当前阶段录制输入/读出、回放输入/输出计数 |
| 26/30/34/38 | 各4 | 停止后排出/溢出前缀/读空/clear done累计 |
| 42/46 | 各4 | 阻塞保持拍数/在途清空事件 |
| 50 | 4 | 失败索引；code12为四位字节不匹配标志 |
| 54/56 | 各2 | 实际/期望低16位 |
| 58 | 1 | 错误码；0无错，1/2数据，3正常期异常，4超时，5/6阻塞清空，7前缀过多，8/9异常恢复，10在途覆盖，11..14最终判据 |
| 59 | 4 | 内存接受请求数 |
| 63 | 1 | XOR |

默认最终成功必须state18/flags25/tests3F、当前四计数4096、after_stop8193、prefix132097、miss8、clear6、held32、inflight1、requests1345540、error0。持续状态是快照，不是逐样本串口回读；首阶段计数会在明确测试阶段重置，cycles保持单调至终止。失败会锁存，主机必须恢复音乐固件。镜像只允许SRAM临时下载，主机不能写Flash。
''',encoding='utf-8')
(R/'README.md').write_text('见project/CURRENT.md和83号报告。独立默认参数双向SDRAM搬运板验，不是音乐录放/文件/最终混音固件。\n',encoding='utf-8')
files={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='delivery.json' and p.suffix not in ('.vvp','.o')}
documents={p.relative_to(P).as_posix():sha(p) for prefix in ('38-','39-','49-','83-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')};assert len(documents)==4
stage_files={p.relative_to(P).as_posix():sha(p) for p in N.rglob('*') if p.is_file() and '__pycache__' not in p.parts and (p.parent==N or p.parent.name.startswith('hardware-'))}
d=dict(version='sdram-stream-board-20261018-v4',time=datetime.datetime.now().astimezone().isoformat(),status='partial product; default synthetic bidirectional SDRAM stream bench verified twice; old final-compare root cause unresolved',
 source_main='fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12',files=files,documents=documents,stage_files=stage_files,frozen_inputs=frozen,backups=backups,
 hardware_tested=True,hardware_scope='two synthetic six-case runs, one board and current supply/ambient; no actual musical recording/mix',
 hardware_directory=h['hardware_directory'],failed_physical_revisions=4,successful_runs=2,
 selected_build='build_stress_v4',timing={k:a['selected'][k]['slack_ns'] for k in ('nominal','stress')},diagnostic_resource=a['selected']['stress']['resource'],
 current_board='stage76 config-sram.fs restored; identity and zero PCM verified',current_board_sha256=hw['restore_bitstream_sha256'],tested_bitstream_sha256=hw['test_bitstream_sha256'],
 flash_accessed=False,tf_accessed=False,files_saved=False,persisted=False,final_mixer_connected=False,full_system_pnr=False,production_qualified=False,old_compare_root_cause_resolved=False)
(R/'delivery.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS bounded validation and recorded identities',files=len(files),stage_files=len(stage_files),backups=[b['files'] for b in backups],successful_runs=2,failed_revisions=4,timing=d['timing'],current_board=d['current_board']),ensure_ascii=False))
