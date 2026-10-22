# -*- coding: utf-8 -*-
"""Record validated changes and the actual unresolved placement failure."""
from pathlib import Path
import json,hashlib,zipfile,subprocess,sys
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent;R=P/'experiments/joint_timing_20261019';E=R/'evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text(encoding='utf-8'))
assert not (R/'delivery.json').exists(),'preserve evaluated snapshots'
h=read(E/'history-audit.json');assert h['status'].startswith('PASS') and not h['full_joint_timing_pass']
for rel,v in h['inputs'].items():assert sha(R/rel)==v,rel
t=read(E/'timing-audit.json');assert t['status'].startswith('FAIL') and not t['bench_gate']
assert '158 REG(s) unPlaced' in '\n'.join(h['rejected_builds']['5']['errors'])
backups=[]
for pointer in ('latest-backup.txt','ram-fix-backup.txt','native-ram-backup.txt'):
    B=Path((N/pointer).read_text(encoding='utf-8'));items=read(B/'manifest.json')
    with zipfile.ZipFile(B/'before.zip') as z:
        assert z.testzip() is None
        for v in items.values():assert hashlib.sha256(z.read(v['member'])).hexdigest()==v['sha256']
    backups.append(dict(root=str(B),sha256=sha(B/'before.zip'),manifest_sha256=sha(B/'manifest.json'),files=len(items)))
engine=read(P/'experiments/register_memory_20261018/delivery.json')['source_engine']
for label,cwd,args in [('main',P,['tools/scripts/project_baseline.py','--check','notes/baselines/main-2026-10-09-board-diag.json']),('engine',Path(engine['root']),['tools/scripts/project_version.py','check','project/versions/engine-safety-20261014-01.json'])]:
    out=subprocess.run([sys.executable,*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (E/('identity-'+label+'.log')).write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode==0
version='joint-timing-20261019-v0';title='85-音乐存储联合布局与RAM模式修正-2026-10-19.md'
entry=f'''**2026-10-19联合布局实际边界**：见[85号]({title})与`experiments/joint_timing_20261019/project/CURRENT.md`，版本`{version}`。先备份106项、修RAM前8项、原生RAM前8项；保留84/83及原源。建立保留音乐/可视化/扫描/录放的串行结构探针，实际PLL与55个SDRAM内部端口；不是实体演奏协议，禁止下载。联合PnR先暴露rc_delta_store的DPB READ_FIRST不支持，已改为写口保持＋碰撞旧值旁路；36万拍对照、160帧位置/5帧扫描回归通过。音高双存储改原生RAM，寄存器718→142，8万拍独立全地址及96万拍音高对照、三组985PCM旧轨迹逐字节一致；两延迟各200音乐PCM录入/读出和200图案播放在限定数字范围**已验证**。但最终综合20189Logic/11243寄存器/31BSRAM，默认和策略1均PR0003，仍158寄存器未放置，**联合布局未通过、无有效时序余量、加严构建未运行**。全部六构建保留FAIL；不能用资源总数或RTL回归放行。新路径**已实现待验证**、整机**部分实现**，没有下载/Flash/TF/新听感；COM6只读确认76号就绪/活动0/512拍。下一步压缩结构探针开销/状态布局并重做联合PnR，最终混音/文件/非易失继续**待实现**，不据此擅自减少功能或裁定双板。'''
report=f'''# 音乐存储联合布局与RAM模式修正 · 2026-10-19

## 0. 结果与版本

版本`{version}`，入口`experiments/joint_timing_20261019/project/CURRENT.md`。本轮得到两个经过数字回归的实现修正，并实际尝试完整音乐/可视化/扫描/SDRAM逻辑的联合布局。**联合布局仍未通过；没有可签收的联合时序结果和新板级镜像。** 新实现属于**已实现待验证**（实体/布局），限定数字回归**已验证**，整机**部分实现**。

main仍`fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12`，main192/engine-safety246身份核对。先读取AGENTS、38/39及工作树分布，备份106输入；修RAM前再备份8项，原生RAM试验前再备份8项，三个ZIP均逐成员哈希验证。备份入口`notes/joint-timing-20261019/`三个指针；84/83、GUI、原产品及旧快照不修改。

本轮仅只读检查实际COM6，板上仍76号：profile72、ABI1、D3/32、case76，就绪/无故障、活动0、512拍采样。未下载新码流、未发起发音测试、未操作Flash/TF，未做新听感/S2/断电测试。身份/状态回读不是85号实体功能验证。

## 1. 联合探针的范围

旧`sdram_stream_probe`有大量逻辑端口，不是可直接分配GPIO的实体顶层。新增`joint_timing_top`将587个动态输入位接成串行历史链，通过两级同步器进入核心；956位非物理输出分成30个32位奇偶校验块，寄存后串行观察。部分相关输出可能在奇偶观察中抵消，因此它不是形式可观测性证明。五个上游历史未使用的sdram_req*输入固定0；旧LEGACY_PAD关闭路径仍由工具移除，其余主要模块保留。

该探针保留音乐/分层/包络/音高/效果、旧音乐可视化、RC扫描/位置、双FIFO/环形仲裁及实际SDRAM控制器。采用83号27→27MHz PLL（OD32/VCO864）、锁定前复位/同步释放、S2/87高有效和SDRAM封装内部端口映射。新增输入最终用原板UART接收70脚，观察输出69脚；外部14脚、SDRAM内部55端口。SDC继续双向min/max、相关转发时钟和正常/加严工程包络；只对外部复位、异步状态输出及只连接首级同步器的scan_in设例外，不给SDRAM/内部逻辑加false path。

输入位移没有事件帧原子性，也不是UART音乐命令协议；任意串行历史可产生无效演奏事件。外部四根音频输出固定静音，内部音频信号进入观察路径。显示/触控/PCM回放DAC/TF尚无实体完整接合。**禁止将本探针作为实体演奏固件下载**，bench_gate始终false；不把它描述成最终面板和整机引脚设计。即使将来它完成静态时序，也仍需要有效命令包装、功能测试和独立板验。

## 2. 校准存储的实际布局错误及修正

首构建综合通过，但布局入口报PA2122：`memory_memory_0_0_s`和`memory_memory_0_1_s`两个DPB的WRITE_MODE0=10不支持。源码定位到`rc_delta_store`，同一端口无条件读取old_word且在WRITE写入，推断READ_FIRST模式。不是音乐CPU算力不够，也不能只凭综合PASS判断可部署。

修正：WRITE时保持old_word，使用此前READ拍已取得的旧字；另一读口如果和本拍写入同地址，使用寄存的旧字低半部旁路，保持原先读取旧值的接口语义，避免依赖原生跨口碰撞行为。read_delta输出仍是同拍边沿后的值，不增加接口拍延迟；校准、known/valid、协议与帧状态保持。新旧源码三配置LANES/CW=2/8、6/12、8/12各120000拍，合计360000拍，94477次同地址碰撞（94304次旧字已知）、随机行故障/错序/背压及每例6次异步复位，逐拍比较所有对外输出通过。故意损坏碰撞旧值被拒绝。

旧独立位置参考160帧及完整6路96节点/26条滑条的5帧数字扫描回归通过；后者17325拍/324个控制字。它们使用理想RC数字模型，不是实体电容/电极验收。

## 3. 音高原生RAM优化

仅用分离数组推断RAM不足以解决寄存器布局。新增`pitch_native_store`，用GW2AR RAM16SDP4和复制读口实现独立异步双读、单写；指令和后台更新各有独立存储。原有initialized/from_command/pending、指令优先、复位屏蔽、即时旁路、滑音/LFO/限幅和输出拍语义不变。音高模块实际寄存器718→142，新增存储不占BSRAM；厂商相关原语限制留在独立模块。

仿真使用从本机已安装高云simlib精确摘取的RAM16SDP4功能模型，来源/整库哈希在reference/vendor-model-source.json；并不是独立硅片电气/时序模型。2/8、32/18、32/20、128/20四配置各20000拍对照独立数组，共80000拍/40000写入；每例78次完整异步地址扫描和读写同地址检查通过。

完整pitch_mod对84号冻结源码的NG/QW=2/18、8/18、32/18、32/20各240000拍，共960000拍输出/epoch比较通过，包含步长/符号边界、样本重叠、冲突与异步复位。gq全组比较使用逻辑影子状态，不能说它直接读到了全部物理原语内容；实际RAM端口由独立存储测试与真实poff对照补充。刻意交换原生读口导致逻辑状态不一致，被断言拒绝。原语初始化为0，真实逻辑仍依靠元数据屏蔽未初始化/复位前旧值。

三组原音乐回归报告合计506645拍/985PCM，完整PCM/I²S轨迹与71号参考逐字节相同，包括和弦修饰、双层音色和触点演奏。未减少32组/16分量，未改右手分区/松手保持/全和弦、配置音乐规则。首PCM/I²S启动未知的旧边界保留，本轮没有新增完整GUI/ADSR配置文件编译器/显示性能回归结论。

## 4. 联合RTL数据路径验证

为了测试真实连接而不是任意位移，测试夹具在验证700拍输入位移后**force内部控制向量**，旁路PLL功能锁定，执行真实音乐事件；这是仿真手段，不能作为已经可用的硬件命令通路。

对SDRAM读返回延迟3/16ns分别运行125352拍：每次223个PCM周期、200个实际非零音乐PCM截位样本写入/逐字读出，以及200个独立图案播放样本均通过，刷新310次、最大间隔394拍，PCM间隔512拍。检查输入连接、30块注册观察逻辑、外部音频静音；故意将真实录制输入翻转一位，被live record mismatch拒绝。两次合计400录制/400播放样本只是小范围数字联合验证，不是实际音频录入/曲谱/混音产品完成，也没有重做83号双回绕/8MiB实体测试。

pcm[23:8]仍是资源/搬运实验格式，未冻结最终录音位深；回放数据未接到现场DAC混音。模型为原有自写SDR命令/时序子集，未模拟PLL抖动和真实die温压。83号旧32位最终诊断比较异常的精确根因仍未解决；本轮并未以新功能回归消除该风险。

## 5. 六次构建与当前未通过边界

| 构建 | 结果 | 原因/范围 |
|---|---|---|
| nominal_v0 | FAIL | DPB READ_FIRST模式不支持；综合20668Logic/31BSRAM |
| nominal_v1 | FAIL | RAM模式修正后，探针新增输入误填68脚，封装无此脚；已按原CST改70 |
| nominal_v2 | FAIL | PR0003：248个等效LUT和792个寄存器未放置；综合20548Logic |
| nominal_v3 | FAIL | 单侧原生RAM候选仍608寄存器未放置；非最终源码身份，不作有效候选 |
| nominal_v4 | FAIL | 双侧原生RAM、默认策略仍158寄存器未放置 |
| nominal_v5 | FAIL | 同一最终RTL、place/route策略1仍158寄存器未放置 |

最后两次最终源码综合20189Logic/11243寄存器/31BSRAM。相对20736Logic总数看似余547，但实际CLS布局已达到上限，寄存器与LUT/ALU/RAM的可配对及局部位置不能只按总量相减。布局失败报告的20187Logic也是未完成的布局统计，不能称已容纳或可部署。原生RAM优化消除了576个音高寄存器、改善失败规模，但仍未解决整个结构探针的放置。

**没有完成路由，没有有效setup/hold/recovery/removal余量，没有输出可用的新码流。** 正常工程尚无法布局，故未额外运行加严完整构建；加严SDC仅准备和静态条目检查。audit_timing.json明确FAIL，两个模式slack均null，绝不以空表/零TNS当通过。缺少DQ最小输入/最大输出约束及负hold的反例均被静态检查拒绝。审计匹配工具ERROR的可变空格，避免依赖固定日志排版；全部六次工具失败与构建输入副本保留，不覆盖旧失败。

该探针还有537个顶层寄存器及观察/输入路由开销，后续需要区分验证包装成本与真实产品状态成本。这个结果不足以裁定原产品绝对无法单板实现，也不授权取消音乐功能或直接扩大预算上双板；同样不能忽略失败宣称单板最终功能已确定装得下。

## 6. 交付与下一步

| 项目 | 状态 |
|---|---|
| 校准存储模式修正、音高原生RAM实现 | 已实现待验证：限定数字回归已验证，实体及完整布局未验证 |
| 联合结构探针/约束/实际构建入口 | 部分实现：已产生真实失败边界，完整布局未通过 |
| 音乐/校准/原生存储/联合RTL回归 | 已验证：限上述模型/激励 |
| 联合时序与新板级下载 | 待验证：布局失败，禁止下载本探针 |
| 真实命令包装、最终PCM混音、TF文件/事件轨/非易失 | 待实现 |
| 实体显示/触控及模拟输出质量 | 待验证 |

下一步先围绕寄存器配对/局部占用继续优化，减少结构探针附加开销并评估真实接口包装，再做联合PnR；取得有效时序与功能命令后才进入板验。保持原音乐规则，不通过缩复音/泛音或删除可视化来制造通过。混音/文件工作仍须按资源账接入。

源码与备份在项目内；本轮evidence/build_*输出位于D:/FPGA-Project/codex-builds/joint-timing-20261019，通过NTFS目录联接访问。复制交付时需要一并保留D盘输出或重跑。verify_delivery只检查身份；audit_history的PASS是证据审计通过，**不是联合布局或时序通过**。没有自动下载入口，bench_gate=false。main/engine旧快照保留，新增delivery记录本轮源码、失败与有效数字证据。
'''
docs=[];p=P/'docs/02-技术方案'/title;p.write_text(report,encoding='utf-8');docs.append(p)
for prefix in ('38-','39-','49-'):
    p=next((P/'docs/02-技术方案').glob(prefix+'*.md'));text=p.read_text(encoding='utf-8')
    if prefix=='38-':
        marker='## 0. 最重要的发现：最新成果并不都在 main\n';assert marker in text;text=text.replace(marker,marker+'\n'+entry+'\n',1)
    else:
        heading,rest=text.split('\n',1);text=heading+'\n\n> '+entry+'\n'+rest
    p.write_text(text,encoding='utf-8');docs.append(p)
current=f'''# 当前音乐存储联合布局 · 85

版本{version}；整机部分实现；报告../../../docs/02-技术方案/{title}

- 新增串行结构探针；是时序验证包装，不是演奏固件，禁止下载，bench_gate=false。
- 修复RC校准DPB不支持的读写模式，音高双原生RAM保留原音乐行为，寄存器718→142。
- 校准36万拍、音高96万拍、原生存储8万拍、位置160帧/扫描5帧及三组985PCM轨迹回归通过。
- 两返回延迟各200实际PCM录入/读出与200图案播放数字验证通过；测试强制内部控制，不是实际录音功能。
- 全部六次联合构建保留FAIL。最终综合20189Logic/11243寄存器/31BSRAM；两布局策略均158寄存器未放置。
- 未完成路由，无有效联合时序余量；加严完整构建未运行，新路径已实现待验证。
- 板上仍76号，COM6只读确认活动0/512拍/就绪；本轮无下载、发音或Flash/TF访问。
- 下一步继续资源/状态布局及真实接口包装，再做联合PnR；最终混音/文件/非易失待实现。
- 输出使用D盘联接；audit_history/verify_delivery的PASS只表示证据/身份审计，不表示布局通过。
'''
(R/'project/CURRENT.md').write_text(current,encoding='utf-8');(R/'README.md').write_text(current.replace('../../../docs/','../../docs/'),encoding='utf-8')
files={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='delivery.json'}
stage={p.relative_to(P).as_posix():sha(p) for p in N.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.zip'}
d=dict(version=version,status='部分实现',files=files,documents={p.relative_to(P).as_posix():sha(p) for p in docs},stage_files=stage,backups=backups,
    latest_synthesis=h['latest_synthesis'],joint_placement_status='FAIL:158 REG unplaced in two strategies',joint_timing_status='NOT AVAILABLE: no completed route',
    bench_gate=False,new_hardware_tested=False,current_board='stage76 existing SRAM firmware, read-only check passed',
    flash_read_or_written=False,tf_accessed=False,final_mixer_connected=False,files_saved=False)
(R/'delivery.json').write_text(json.dumps(d,indent=2),encoding='utf-8')
print('NEW evaluated snapshot of validated RTL and failed placement:',version,len(files),'files')
