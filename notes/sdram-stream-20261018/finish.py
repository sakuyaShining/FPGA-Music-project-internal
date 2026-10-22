# -*- coding: utf-8 -*-
from pathlib import Path
import json,hashlib,zipfile,subprocess,sys,datetime
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent;R=P/'experiments/sdram_stream_20261018';E=R/'evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
assert not (R/'delivery.json').exists(),'preserve existing snapshot'
up=read(R/'upstream.json')
for key in ('controller','timing'):
 U=Path(up[key+'_root']);assert sha(U/'delivery.json')==up[key+'_delivery_sha256']
 for rel,h in up[key+'_files'].items():assert sha(U/rel)==h,(key,'upstream changed',rel)
frozen={}
for p in (R/'engine').rglob('*'):
 if p.is_file():
  rel=p.relative_to(R).as_posix();assert sha(p)==up['controller_files'][rel];frozen[rel]=sha(p)
for name in ('pcm_storage_buffers.v','pcm_sync_fifo.v','storage_probe.v','sdram_storage_probe.v'):
 rel='rtl/'+name;assert sha(R/rel)==up['controller_files'][rel];frozen[rel]=sha(R/rel)
assert sha(R/'rtl/sdram_word_controller.v')==up['timing_files']['rtl/sdram_word_controller.v']
for name in ('arbiter','stream','fault-recovery','resource'):
 d=read(E/(name+'.json'));assert d['status'].startswith('PASS')
 for rel,h in d['inputs'].items():assert sha(R/rel)==h,(name,rel)
resource=read(E/'resource.json');assert min(resource['logic_spare'],resource['bsram_spare'])>=0
for folder in resource['selected_builds']:
 D=R/folder;d=read(D/'run.json');assert d['returncode']==0 and not (D/'interruption.json').exists()
 for name,v in d['inputs'].items():assert sha(D/name)==sha(R/v['source'])==v['sha256']
assert read(R/'synthesis_buffered_final/interruption.json')['status'].startswith('NOT ACCEPTED')
B=Path((N/'latest-backup.txt').read_text(encoding='utf-8'));backup=read(B/'manifest.json')
allowed={str(p) for k in ('38-','39-','49-') for p in (P/'docs/02-技术方案').glob(k+'*.md')}
with zipfile.ZipFile(B/'before.zip') as z:
 assert z.testzip() is None
 for path,v in backup.items():
  assert hashlib.sha256(z.read(v['member'])).hexdigest()==v['sha256']
  if path not in allowed:assert sha(Path(path))==v['sha256'],path
engine=read(P/'experiments/register_memory_20261018/delivery.json')['source_engine']
for label,cwd,args in [('main',P,['tools/scripts/project_baseline.py','--check','notes/baselines/main-2026-10-09-board-diag.json']),('engine',Path(engine['root']),['tools/scripts/project_version.py','check','project/versions/engine-safety-20261014-01.json'])]:
 out=subprocess.run([sys.executable,*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
 (E/('identity-'+label+'.log')).write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode==0
arb=read(E/'arbiter.json');stream=read(E/'stream.json');fault=read(E/'fault-recovery.json')
cycles=sum(x['cycles'] for x in arb['results']);clears=sum(sum(x['clears']) for x in arb['results']);accepted=sum(sum(x['memory_clients'].values()) for x in arb['results'])
a=resource['before'];b=resource['after'];delta=resource['delta']
title='82-录放缓冲与SDRAM环形调度接合-2026-10-18.md'
entry=f'''**2026-10-18录放环形调度接合**：见[82号]({title})与`experiments/sdram_stream_20261018/project/CURRENT.md`，版本`sdram-stream-20261018-v0`。先备份101项，冻结原音乐/双FIFO，沿用81号注册输出控制器；新增录制/回放独立SDRAM环形区、四客户轮转及clear接受/清退/完成围栏，停止采集仍排空旧队列。四配置共{cycles}拍/{accepted}内存请求/{clears}清空、最多等其他3次授予；双后端整链及溢出前缀/读空恢复、四个故障反例在数字范围**已验证**。同工程{a['Logic']}→{b['Logic']}Logic，{b['BSRAM']}BSRAM，余{resource['logic_spare']}Logic/{resource['bsram_spare']}BSRAM；只算联合综合，无新PnR/板验。中间一次工具卡住人工终止，退出0仍不计通过，串行新工程正常完成后才签收。本轮无下载/COM/Flash/TF访问，板上仍76号；实际新调度**已实现待验证**。逻辑数据搬运已接通，但TF/文件/非易失/事件配对/最终混音/完整音乐联合时序仍**待实现/待验证**，整机**部分实现**。下一步隔离调度板验、联合时序与资源优化，再接TF和回放音频，不能用SDRAM易失缓存冒充断电保存。'''
report=f'''# 录放缓冲与SDRAM环形调度接合 · 2026-10-18

## 0. 版本与范围

`sdram-stream-20261018-v0`，入口`experiments/sdram_stream_20261018/project/CURRENT.md`。录制和回放两路短FIFO已接到实际SDRAM控制接口，数据搬运/清空围栏在记载数字范围**已验证**；新增调度的实体路径**已实现待验证**，完整产品仍**部分实现**。回放PCM目前仍为独立逻辑输出，没有接最终DAC混音；没有TF文件、持久存储或曲谱事件配对。

按38/39、工作树分布和main基线先核对版本，ZIP/逐项哈希备份101项后新建实验目录。main HEAD仍fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12，main192/engine246输入检查PASS。原80/81全部交付文件保留；冻结{len(frozen)}个本轮继承的引擎/表/原缓冲/旧探针输入，控制器逐字节沿用81号注册输出版本。原源、GUI和旧快照未改，旧文档快照不因新追加状态而重写。

本轮未开串口、下载、访问Flash/TF或发声音，板上仍为81号末尾已恢复的76号配置固件。未把81号旧诊断实测当成本轮调度板验，也未把新的逻辑端口当真实板边引脚。

## 1. 新增数据路径

录制：实时PCM抽头→既有短FIFO→SDRAM录制环形区→主机/后续介质消费者。

回放：主机/后续介质生产者→SDRAM回放环形区→既有短FIFO→独立回放PCM输出。

`pcm_sdram_arbiter.v`有四类客户：录制写入、录制读出、回放写入、回放预取；最多一个内存请求在途，按轮转顺序选择可服务客户。请求选中时锁存地址/数据，在内存req_valid&&!req_ready期间保持；内存接受时才对输入FIFO/主机给ready，内存响应时才更新已提交的环形指针与计数。读出先存入独立单字保持寄存器，消费者阻塞时保持数据，避免阻塞另一方向或SDRAM自主刷新。

默认RING_AW17：两个区域各131072个16位样本，即各256KiB，总512KiB。半字地址录制000000～01FFFF、回放020000～03FFFF；互不交叠，剩余SDRAM未分配，不写成最终文件/时长分区。默认短FIFO_AW10各1024×16，沿用79号已测源；16位抽头仍为PCM[23:8]，属于资源/搬运原型，不冻结最终录音量化和文件格式。按现有27000000/512采样率，单个空环形区容量约2.486秒，是容量算式，不是对任意TF卡暂停的保证。

环形level只统计SDRAM中已提交的字，不包含输入短FIFO、在途写及已预取的输出保持字；主机不能只读该level就判断整个录制已排空。默认2KiB短FIFO仍不等于完整媒体缓存。所有接口同一时钟，不提供CDC或多在途/重排能力。

## 2. 停止与清空边界

rec_enable=0仅停止继续捕获，已排队数据仍可排出；play_enable=0仅暂停按sample_tick消费，预取可继续。它们是底层传输端口，不替用户冻结实体录制按钮、停止位置、循环叠录或新音/旧音的音乐规则。

每方向clear采用valid/ready接受，再给clearing和单拍done。接受clear的当拍就阻止该方向新输入和输出，丢弃未消费的保持字；若已有请求向内存呈现，即使尚未接受，也必须保持地址/数据/valid直到握手，再等响应退出，不能撤回造成未知归属。该方向旧事务退出后才重置指针/计数并给done，短FIFO在done采样边沿清空，期间不能接收下一会话数据。另一方向可继续服务，clear不复位SDRAM控制器/刷新。

调用方必须按握手提交clear，等done后再开始新会话，并在clear边界处理其自身旧数据头；只把clear打一拍而不看ready并非可靠命令协议。已呈现的旧内存写可能仍落入物理RAM，但在clear完成前不会对新会话发布，并从新指针重新覆盖；不承诺撤销物理写或文件原子性。若后端永不接受/返回，clear也可能永不done；本轮没有补外部超时恢复或掉电文件保护。

新增围栏还处理“clear请求撞上前一拍已生成的play_valid/miss脉冲”，避免已取消会话的脉冲流到下游。原短FIFO/溢出策略保持：录制溢出后锁存，后续停止采入，已接受连续前缀仍可排出，明确clear才能恢复；回放缺字只报告miss/underflow，不产生重复的有效样本。如何把miss转为听感上的静音/保持/淡出仍是后续混音边界，本轮不替用户决定。

## 3. 实际验证

### 3.1 调度与会话

`check_arbiter.py`：AW1/3/5/17四组各170004拍，共{cycles}拍、{accepted}次内存接受和{clears}次clear。独立慢速地址存储模型加入0～18拍返回延迟、请求暂停、输出阻塞；Python用两个deque核对输入/输出顺序与clear取消边界，不按DUT指针重写参考实现。含全局复位取消事务，故响应总数49113少于接受数49139，不把被复位取消的26笔列为静默丢失。

记录/检查请求等待时地址数据不变、保持输出不变、环形计数不溢出、同方向clear时无新接受、clear完成前旧事务已退出。外部可服务条件下轮转等待最多其他3次授予；这是服务机会界，不是内存任意阻塞下的绝对时间保证。指定慢后端测试的最长clear109拍；不能据此承诺所有后端109拍内结束。

三种故意错误被检出：回放写入错误区域→读未初始化数据；内存未退出就提前clear→环形计数异常；忽略读头反压继续预取→保持数据被覆盖。另曾试过去掉取消响应保护，但现有clear围栏仍挡住该变体，未被检出；它不列入三个成功故障反例，相关历史实验文件保留。随机覆盖不是形式证明或所有故障覆盖。

### 3.2 完整数字搬运链

`check_stream.py`同时实例化两短FIFO、两环形区和调度，分别接独立慢内存及81号真实控制器＋自写SDR命令/时序模型。每组210003拍，按512拍消费，测试主机录制消费者暂停20000拍（约0.741ms）、回放生产者暂停20000拍、内存请求端暂停两段各2000拍（约74.074us），并加入非空清空和在途清空。

每组实际293个捕获样本、272个录制输出，其中21个按显式clear取消；539个主机回放输入、320个有效回放，其余按三次clear取消。两deque逐值核对，无未说明的丢失或错序，正常场景无溢出/读空。停止录制后另排出20个积压样本，证明停止采入不等于清掉已有数据。真实命令模型记录831写/620读/531刷新，最长刷新间隔395拍，未超过模型421拍期限。

这些整链测试用缩小的8样本短FIFO和64样本环形区，促使频繁满载/回绕；默认17位地址参数另经上述调度测试和实际联合综合，但没有用默认256KiB区跑真实介质停顿/完整容量实板扫测。命令模型仍为子集，不覆盖实际die、电气建立保持、温压与PLL。去掉回放valid清空围栏的第四个故障反例，在相撞拍被“stream output during clear”断言检出。

### 3.3 故意资源耗尽与恢复

`check_fault_recovery.py`用4样本短FIFO/8样本环形区、64拍加速采样，故意长时间不排录制数据和停止供给回放。录制恰好排出连续13样本前缀，溢出锁存一次；clear后继续输出78个新样本。回放32个输入对应32个有效输出，124次缺字均报告miss，没有把上一字重复标成有效；两次回放clear和一次录制clear后最终故障标志与队列归零。此为数字异常路径测试，不是现有音频速率或听感验收。

测试编写期间，夹具曾在下降沿根据当时ready撤销尚未到上升沿握手的valid，造成假性尾部残留；修正生产者只按已发生的握手换头，并在显式clear处理生产者旧头，再重跑。初始复位期未知值不进入有效数据参考。未通过降低实际数据一致性/清退判据来通过测试。

本轮没有重跑所有原音乐/配置/显示回归，原源/表/旧缓冲保持并逐项核验，继承对应版本证据；没有门级仿真、新板级下载或新音频听感结论。

## 4. 联合资源及构建可信度

同器件、同文件集合、同工程，唯一变体文件为sdram_stream_probe.v。参考接81号注册控制器＋既有FIFO但内存由外部逻辑测试口驱动；接合版由新增调度驱动，保留同端口以对比。保留的旧sdram_req*输入在接合版未使用，属于资源探针，不是最终GPIO分配。主音乐I²S/PCM路径没有被回放输出替换。

| 工程 | Logic | 寄存器 | BSRAM |
|---|---:|---:|---:|
| 本轮注册控制器/未接调度参考 | {a['Logic']} | {a['Register']} | {a['BSRAM']} |
| 录放SDRAM调度接合 | {b['Logic']} | {b['Register']} | {b['BSRAM']} |
| 差值 | {delta['Logic']:+d} | {delta['Register']:+d} | {delta['BSRAM']:+d} |

剩余{resource['logic_spare']}Logic/{resource['bsram_spare']}BSRAM。此为完整逻辑探针的**联合综合已验证**，尚无实际GPIO/时钟顶层和联合PnR；不承诺剩余314Logic能容纳TF块、文件协议、事件轨、混音、非易失和最终屏幕。调度层次181寄存器/280LUT，整体Logic差值包含全局映射变化，不能当固有模块价格。独立81号1:1 PLL与专用封装引脚时钟包装还未一起接入本轮完整音乐顶层，81号setup/hold余量不能继承为新系统余量。

第一次在清空脉冲修正前的buffered构建20612Logic保留为旧候选，不作为当前身份结果。修正后的synthesis_buffered_final生成20422Logic报告但工具未正常退出；经核对具体进程路径后人工终止，工具表面返回0，另写interruption.json明确NOT ACCEPTED，绝不按0签收。随后单独新建synthesis_buffered_retry串行构建，108.42秒正常退出且同为20422Logic；最终审计只接受该次与正常退出的reference_final，并逐项核对当前源码/工程/Tcl/报告哈希。

## 5. 状态与下一步

| 项目 | 状态 | 后续边界 |
|---|---|---|
| 双向FIFO/SDRAM环形数据搬运、clear围栏、公平调度 | 已验证 | 限记载模型/参数与数字场景 |
| 同时录放数据压力、溢出/缺字与恢复 | 已验证 | 回放还是逻辑输出，不是音频混音 |
| 新调度真实板级运行/完整音乐联合时序 | 已实现待验证 | 必须有新时钟/引脚包装、约束与PnR，不能复用旧诊断签收 |
| 主机/实体录放命令、全路径排空/错误状态 | 待实现 | 新增底层端口尚未接GUI/实体按钮；level不足以单独判断已保存 |
| TF块、文件保存、曲谱事件配对、非易失配置 | 待实现 | SDRAM易失，断电后不保留 |
| 伴奏回放＋现场音乐最终混音 | 待实现 | 本轮未改变原音频输出 |

下一步先做独立新调度板级包装与测试、完整音乐＋存储时序/资源预算；余量紧时按有独立参考的优化恢复空间，再接TF块传输和回放音频。保留用户的自定义乐器、同音分层、录好伴奏后现场演奏、右手分区/半径/松手保持/全和弦与断电保存目标；本轮没有替用户新增或裁定叠录、循环、轨数和异常听感规则。

测试入口check_arbiter.py、check_stream.py、check_fault_recovery.py；资源入口synthesize.py reference/buffered 新目录后缀，audit_resources.py核对选定目录；verify_delivery.py仅身份检查。交付delivery.json在适当验证后新建，记录备份、源、测试、构建和文档。没有覆盖旧快照或把源码指纹PASS当产品完成。
'''
(P/'docs/02-技术方案'/title).write_text(report,encoding='utf-8')
for prefix in ('38-','39-','49-'):
 path=next((P/'docs/02-技术方案').glob(prefix+'*.md'));text=path.read_text(encoding='utf-8')
 assert '**2026-10-18录放环形调度接合**' not in text
 if prefix=='38-':
  anchor='## 0. 最重要的发现：最新成果并不都在 main\n';assert anchor in text;text=text.replace(anchor,anchor+'\n'+entry+'\n',1)
 else:first,rest=text.split('\n',1);text=first+'\n\n> '+entry+'\n'+rest
 path.write_text(text,encoding='utf-8')
(R/'project/CURRENT.md').write_text(f'''# 当前录放SDRAM数据搬运实验 · 82

版本sdram-stream-20261018-v0，完整产品部分实现。报告../../../docs/02-技术方案/{title}

- 101输入先备份，原音乐/GUI/双FIFO与旧交付保持；SDRAM控制器同81号。
- 新增两个256KiB默认环形区、四客户轮转、独立clear握手/在途清退，停止采入继续排空。
- 数字调度{cycles}拍/{clears}clear，双后端整链/异常恢复与四个故障反例已验证。
- 正常工具结束的新联合综合{b['Logic']}Logic/{b['BSRAM']}BSRAM，余{resource['logic_spare']}Logic/{resource['bsram_spare']}BSRAM；无新PnR/板验。
- 回放为独立PCM逻辑输出，未接最终混音/DAC。TF/文件/事件轨/非易失/录放GUI命令仍待实现。
- 新调度实体路径已实现待验证；本轮未开COM/下载/访问Flash或TF，板上仍76号。
- 先做调度板验/联合时序及资源恢复，再接媒体和回放音频；旧81号时序不外推新顶层。
- check_arbiter.py/check_stream.py/check_fault_recovery.py为数字验证，verify_delivery.py只核身份。
- synthesis_buffered_final有interruption.json，不得因表面exit0作为合格构建；选定buffered_retry。
''',encoding='utf-8')
(R/'README.md').write_text('见project/CURRENT.md和82号报告。双向SDRAM环形调度数字接合与联合综合已验证；新调度板验/完整录放产品仍待完成。\n',encoding='utf-8')
files={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='delivery.json' and p.suffix not in ('.vvp','.o')}
documents={p.relative_to(P).as_posix():sha(p) for prefix in ('38-','39-','49-','82-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')};assert len(documents)==4
d=dict(version='sdram-stream-20261018-v0',time=datetime.datetime.now().astimezone().isoformat(),
 status='partial product; new bidirectional SDRAM ring transport verified in recorded digital tests and joint synthesis only',
 source_main='fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12',frozen_inputs=frozen,files=files,documents=documents,
 stage_files={p.relative_to(P).as_posix():sha(p) for p in N.glob('*.py')},
 backup=dict(root=str(B),files=len(backup),sha256=sha(B/'before.zip'),manifest_sha256=sha(B/'manifest.json')),
 resource={k:resource[k] for k in ('before','after','delta','logic_spare','bsram_spare')},
 controller_source_sha256=sha(R/'rtl/sdram_word_controller.v'),fifo_backend_connected=True,final_mixer_connected=False,
 hardware_tested=False,fpga_programmed=False,serial_opened=False,flash_accessed=False,tf_accessed=False,
 persisted=False,full_system_pnr=False,current_board='76 unchanged this stage; restored and verified by stage81')
(R/'delivery.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS bounded checks and recorded identities',files=len(files),backup=len(backup),resource=d['resource'],cycles=cycles,clears=clears,hardware_tested=False),ensure_ascii=False))
