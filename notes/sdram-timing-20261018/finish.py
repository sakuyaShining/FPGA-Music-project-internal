# -*- coding: utf-8 -*-
"""Freeze stage81 only after bound functional, timing and physical checks."""
from pathlib import Path
import datetime,hashlib,json,subprocess,sys,zipfile
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent
R=P/'experiments/sdram_timing_20261018';E=R/'evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
assert not (R/'delivery.json').exists(),'preserve existing snapshot; create a new evaluated revision'
up=read(R/'upstream.json');U=Path(up['root'])
assert sha(U/'delivery.json')==up['delivery_sha256']
for rel,h in up['files'].items():assert sha(U/rel)==h,('upstream changed',rel)
assert sha(R/'reference/sdram_word_controller_unregistered.v')==sha(U/'rtl/sdram_word_controller.v')
for name in ('sdram-reference','board-model','pin-equivalence','timing-audit','hardware-audit'):
 d=read(E/(name+'.json'));assert d['status'].startswith('PASS')
 root=P if name=='hardware-audit' else R
 for rel,h in d['inputs'].items():assert sha(root/rel)==h,(name,rel)
a=read(E/'timing-audit.json');h=read(E/'hardware-audit.json')
assert a['bench_gate'] and not a['production_qualified'] and h['runs']==2
S=P/h['hardware_directory'];hw=read(S/'result.json');assert 'restored' in hw
backups=[]
for pointer in ('latest-backup.txt','prefixed-backup.txt'):
 B=Path((N/pointer).read_text(encoding='utf-8'));manifest=read(B/'manifest.json')
 with zipfile.ZipFile(B/'before.zip') as z:
  assert z.testzip() is None
  for rel,item in manifest.items():
   member=item['member'] if isinstance(item,dict) else rel
   digest=item['sha256'] if isinstance(item,dict) else item
   assert hashlib.sha256(z.read(member)).hexdigest()==digest
 backups.append(dict(root=str(B),files=len(manifest),sha256=sha(B/'before.zip'),manifest_sha256=sha(B/'manifest.json')))
engine=read(P/'experiments/register_memory_20261018/delivery.json')['source_engine']
for label,cwd,args in [('main',P,['tools/scripts/project_baseline.py','--check','notes/baselines/main-2026-10-09-board-diag.json']),('engine',Path(engine['root']),['tools/scripts/project_version.py','check','project/versions/engine-safety-20261014-01.json'])]:
 out=subprocess.run([sys.executable,*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
 (E/('identity-'+label+'.log')).write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode==0
title='81-SDRAM时序排查与板级读写验证-2026-10-18.md'
entry=f'''**2026-10-18 SDRAM时序与板验**：见[81号]({title})及`experiments/sdram_timing_20261018/project/CURRENT.md`，版本`sdram-timing-20261018-v0`。先备份109项，修复前再备份194项；隔离注册命令/地址/DQM输出，18万拍9593事务旧源对照和原SDR模型/四反例通过。补齐内部SDRAM映射、双向min/max及相关时钟约束，27→27MHz PLL改善核心时钟分布；正常setup/hold为+5.704/+0.225ns，加严为+4.204/+0.037ns，原未注册加严−0.877ns反例和漏约束假绿反例保留。实际COM6/B、ID81B，仅操作2 SRAM，两次8MiB双图案写读各16777216事务无错；已恢复76号并确认身份、512拍采样与2048零PCM。限定板上路径**已验证**，原始PLL输入PR1014/确切die与封装时序/温压和长期保持仍**待验证**，不作量产签收。本轮无Flash/TF访问或音乐源/GUI/旧快照变更；完整音乐＋新控制器联合资源/PnR、FIFO仲裁/环形区、TF文件/非易失/混音仍**待实现/待验证**，整机**部分实现**。下一步接录放缓冲与SDRAM有界调度/清退，再做联合时序与实测。'''
report=f'''# SDRAM时序排查与板级读写验证 · 2026-10-18

## 0. 结论、版本和安全边界

发现真实的时序余量风险并完成隔离修正；在声明的工程I/O时序包络内，静态分析和两次实体SDRAM全地址双图案写读均通过，范围**已验证**。这支持下一步接入录放缓冲；整机仍**部分实现**，不能据此宣布录音、TF文件、非易失保存或量产时序完成。

版本`sdram-timing-20261018-v0`，实现入口`experiments/sdram_timing_20261018/project/CURRENT.md`。main HEAD仍`fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12`，main192/engine246输入身份复核PASS。按38/39入口核对工作树；先ZIP/逐项哈希备份109项，再在修复前备份194项；原80号控制器/全部交付输入、原音乐引擎、GUI及旧快照均保持。

实际只对FTDI序列2025030317B/COM6和JTAG单器件GW2AR ID0x0000081B执行有界诊断，下载器仅用operation_index=2（SRAM Program）。测试不发声音，音频四输出固定低；不读写Flash、TF或用户文件。结束已下载回76号`config-sram.fs`，回读C0=72/C2=76/C3=1/D0=75/D1=1/A4=D3/A9=32，active/fingers=0，采样间隔512拍，2048个PCM样本全零。GUI继续用76号`launch_gui.cmd`，本轮未升级音乐固件或修改音乐规则。

## 1. 发现的风险与修正

旧控制器状态组合译码直接驱动SDRAM命令/地址/DQM，27MHz反相转发时钟只有约18.519ns半周期窗口。正常配置虽正余量很小，加严I/O延迟与时钟不确定性后，实际输出路径出现−0.877ns建立违例。该工具的汇总TNS仍显示0，故新审计读取实际Setup/Hold/Recovery/Removal路径表最小值，不以“TNS=0”单独放行。

命令/地址/DQM/写输出使能改为寄存器输出，通过预测下一状态保持原命令拍次。接受请求当拍用输入地址生成ACT，后续用锁存地址；没有给音乐引擎加拍，也未改变控制器握手、刷新、CAS3或读捕获的原逻辑时序。

最初直连板载时钟的核心布线分布有限。独立诊断加入27MHz输入/27MHz输出的1:1 rPLL，ODIV32、VCO864MHz，核心logic_clk采用PRIMARY时钟覆盖四象限；锁定前保持复位，再两级同步释放。先试ODIV16/VCO432MHz被器件工具范围检查拒绝，失败工程保留且未下载。输入clk_d仍有PR1014通用布线警告，**待验证/处理**；并未将警告抹去。仿真宏旁路PLL，仅验证逻辑功能，不能证明PLL锁定抖动或锁失行为；实体两次配置成功只覆盖当时条件。

## 2. 约束、映射和实际静态结果

按高云嵌入式SDRAM接口命名暴露55个O_sdram*/IO_sdram*信号，PnR引脚表确认均落在内部p*引脚，不占用户板边GPIO。外部13脚为时钟4、复位S2/87（高有效）、UART69、LED15～20和静音音频51/54/55/56；没有使用错误的S1/87映射。

SDC声明37.037ns输入时钟、PLL生成时钟及反相SDRAM转发时钟。32位DQ均有输入max/min，52位命令/地址/银行/DQM/DQ均有输出max/min；常量CKE/CS无动态时序。仅外部异步复位源和LED/UART状态输出设例外，没有将SDRAM/相关时钟设成异步或false path。UART端点例外按异步外设处理，其协议另做功能测试，不能当UART引脚边沿已测量。

正常包络：DQ输入max6.5/min1ns，输出max3/min−2ns，setup/hold不确定性0.5/0.2ns。加严包络：输入max10ns，输出max4/min−3ns，不确定性1/0.5ns。这些是明确的工程假设，**确切封装内die、速度档、封装延时尚未绑定，时序参数资格仍待验证**。加严不是超频，时钟仍27MHz。

| 独立诊断构建 | 最小setup/ns | 最小hold/ns | 最小recovery/ns | 最小removal/ns |
|---|---:|---:|---:|---:|
| 旧组合输出，正常 | +0.623 | +0.225 | — | — |
| 旧组合输出，加严 | −0.877 | +0.039 | — | — |
| 注册输出，直连时钟，正常 | +3.152 | +0.225 | — | — |
| 注册输出，直连时钟，加严 | +1.652 | +0.037 | — | — |
| 最终注册输出＋PLL，正常 | +5.704 | +0.225 | +34.430 | +1.190 |
| 最终注册输出＋PLL，加严 | +4.204 | +0.037 | +33.930 | +0.890 |

最终独立诊断PnR为498Logic/358寄存器/13外部IO，使用1个PLL。它不包含完整音乐/GUI/屏幕/录放链；不能把它的余量外推整机。80号联合20114Logic/31BSRAM、余622/15仍仅属于旧控制器的联合综合；**新控制器和PLL接合后的完整联合综合/PnR待实现/验证**。原78号音乐诊断的时序证据继续按原版本阅读，本轮没有重跑整个音乐引擎。

旧正常构建build_nominal虽生成时序报告，但未取得正常退出记录，只作为排查参考，不计入可下载候选；最终build_pll32_nominal/stress均有正常退出与当前输入哈希绑定的run.json，并由审计验证。

漏掉转发时钟和I/O约束的错误工程报告了+30.341/+0.425ns“好看”余量，已由约束审计明确拒绝。保留其报告和旧加严负余量，作为防止假绿的反例。默认工具只报告各类最坏25条路径，最终正常分析1068端点/2224路径；当前是声明约束与报告路径审核，不是逐位完整路径证书。加严hold仅+0.037ns，仍需结合实际规格/电气条件审视。

## 3. 数字验证与实体结果

1. 注册前后旧源逐拍对照180000拍，9593个接受事务（4801写/4792读）、9588响应，6次异步复位及拍间输入变化；比较握手、命令、地址、掩码和DQ。响应差额来自复位取消事务。结果为采样行为等价，不能证明所有组合瞬态或形式等价。
2. SDR独立子集模型重跑2147事务（1090读/1057写）、95刷新、最长刷新间隔397拍、最长接受至响应11拍；缩短tRCD、延迟刷新、错误半字掩码、反压阻塞刷新四个错误副本均被检出。它仍非原厂完整器件模型。
3. 板级包装小地址仿真验证两图案/128操作、UART原子快照和校验、S2在途取消后重初始化、音频静音；读返回延迟3/10/16ns通过，20ns超半周期的反例被BIST检出。模型没有FPGA实际路径、电气或温压效应；20ns案例的PASS表示成功检出错误，不能说20ns正常工作。
4. 实体两次重新配置后运行全8MiB/4194304半字地址扫描，各依次写读两种互补图案。图案为地址低16位异或高6位，再异或A55A/5AA5。每次8388608写＋8388608读，共16777216操作；两次33554432半字操作、累计64MiB读写流量，均无BIST错误。四bank、行列与两半字都实际遍历。每秒UART快照各收到7帧含最终PASS/phase1/index3FFFFF/count1000000，末数据A565一致。

最终PASS在打开串口后约6.938秒收到，但测试已在下载结束期间自动启动；这个时间**不是完整扫测耗时或存储吞吐测速**，每秒快照也不是逐笔外部回读。测试覆盖当前单板、当前供电/室温和这两图案；图案存在地址异或碰撞，不是完整地址别名或March故障覆盖，未做长时间保持、温压扫描、外部示波器测边沿、物理S2或断电循环。

第一轮主机脚本错误地要求下载器输出“success”，实际工具输出Finished和状态6020，脚本提前退出，随后仍执行恢复下载。该轮没有完成读写验收，也未及时通过脚本确认恢复，记录如实保留为FAIL。修正为检查实际操作/设备/100%/状态/Finished后，另建会话重新完整执行两轮及恢复；没有覆盖失败日志。离线审计从原始UART字节重新校验帧、计数、图案末值和下载/恢复日志，确认结果与源码/约束/码流哈希一致。

## 4. 状态与下一步

| 项目 | 状态 | 边界/后续 |
|---|---|---|
| 注册输出、声明包络静态时序与反例 | 已验证 | 限独立诊断与上述工程假设 |
| 实体SDRAM基本读写 | 已验证 | 单板、两轮、两图案，非长期资格 |
| 原音乐固件恢复/零PCM | 已验证 | 已回76号，无新听感或模拟音质结论 |
| 确切die/封装时序、原始输入时钟警告、长期/温压/边沿 | 已实现待验证/讨论中 | 保留风险，不签量产 |
| 完整音乐＋新控制器联合资源与PnR | 待实现/待验证 | 独立诊断余量不能代替整机 |
| 录/放FIFO→独立SDRAM环形区、有界仲裁/清空清退 | 待实现 | 接受、提交和在途会话所有权须独立 |
| TF块/文件、事件轨配对、非易失配置、最终回放混音 | 待实现 | SDRAM易失，不能保存到断电后 |

下一步先做录放FIFO到SDRAM的独立区域和有界调度，处理录制停止/清空/会话切换时仍在途的响应，验证并行录放、刷新和后台长停顿；再做音乐联合资源/PnR及对应板验。未新增循环叠录、多轨数量、量化或异常淡出等音乐规则。当前音色分层/个人伴奏合奏总体仍部分实现。

可重跑的离线入口：check_sdram.py、check_pin_equivalence.py、check_board.py、audit_timing.py、check_hardware_evidence.py；构建入口为build_board.py 新目录名 nominal（或stress），已有构建目录不得覆盖。verify_delivery.py只校验身份，不触发下载。硬件脚本位于notes/sdram-timing-20261018/bench_hardware.py，会临时下载并恢复，不能当普通离线测试自动运行。交付delivery.json绑定输入/报告/证据与两份备份；旧快照保留。

依据：[高云DS226](https://cdn.gowinsemi.com.cn/DS226E.pdf)、[引脚定义UG229](https://cdn.gowinsemi.com.cn/UG229E.pdf)、[时序约束指南SUG940](https://cdn.gowinsemi.com.cn/SUG940E.pdf)、[Sipeed Nano20K](https://wiki.sipeed.com/en/nano20k)。检索的[EM638325资料](https://etron.com/wp-content/uploads/2022/04/EM638325_Rev-3.2.pdf)仅为时序参考候选，未将它认定为本板封装内真实die。
'''
(P/'docs/02-技术方案'/title).write_text(report,encoding='utf-8')
for prefix in ('38-','39-','49-'):
 path=next((P/'docs/02-技术方案').glob(prefix+'*.md'));text=path.read_text(encoding='utf-8')
 assert '**2026-10-18 SDRAM时序与板验**' not in text
 if prefix=='38-':
  anchor='## 0. 最重要的发现：最新成果并不都在 main\n';assert anchor in text;text=text.replace(anchor,anchor+'\n'+entry+'\n',1)
 else:
  first,rest=text.split('\n',1);text=first+'\n\n> '+entry+'\n'+rest
 path.write_text(text,encoding='utf-8')
(R/'project/CURRENT.md').write_text(f'''# 当前SDRAM时序/板验实验 · 81

版本sdram-timing-20261018-v0。完整产品部分实现，报告../../../docs/02-技术方案/{title}

- 先备份109项，修复前再备份194项；原80号/音乐引擎/GUI/快照保持。
- 注册命令引脚/1:1 PLL、声明I/O包络PnR和反例：限定范围已验证。
- 正常setup/hold +5.704/+0.225ns；加严+4.204/+0.037ns，确切die/封装延迟/原始PLL输入警告仍待验证。
- 实体8MiB两图案、两次配置重测共33554432半字操作无错；当前室温/供电，不替代长期/温压/示波器资格。
- 已恢复76号音乐配置固件，身份/512拍/2048零PCM已验证；GUI仍../envelope_resources_20261017/launch_gui.cmd。
- 无Flash或TF访问。无新物理S2/模拟音质结论；SDRAM不能断电保留。
- FIFO环形调度、TF/文件/非易失/最终混音待实现；完整音乐＋新控制器资源/PnR待验证。
- check_hardware_evidence.py只离线审计。notes中的bench_hardware.py实际下载后恢复，勿混入普通回归。
- verify_delivery.py仅身份核验；不得据PASS宣布完整产品完成。
''',encoding='utf-8')
(R/'README.md').write_text('见project/CURRENT.md和81号报告。独立SDRAM时序与板级基本读写已验证；完整音乐/录放接合仍部分实现。\n',encoding='utf-8')
files={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='delivery.json' and p.suffix not in ('.vvp','.o')}
documents={p.relative_to(P).as_posix():sha(p) for prefix in ('38-','39-','49-','81-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')};assert len(documents)==4
stage_files={p.relative_to(P).as_posix():sha(p) for p in N.rglob('*') if p.is_file() and '__pycache__' not in p.parts and (p.suffix=='.py' or p.name.endswith('.txt') or p.parent.name.startswith('hardware-'))}
d=dict(version='sdram-timing-20261018-v0',time=datetime.datetime.now().astimezone().isoformat(),
 status='partial product; bounded diagnostic RTL/declared-envelope STA and two physical SDRAM sweeps verified',
 source_main='fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12',source_engine_manifest=engine['manifest'],upstream_root=str(U),
 files=files,documents=documents,stage_files=stage_files,backups=backups,
 timing={mode:a['selected'][mode]['slack_ns'] for mode in ('nominal','stress')},diagnostic_resource=a['selected']['nominal']['resource'],
 hardware_tested=True,hardware_scope='current single board/two complementary address-pattern sweeps only',
 hardware_directory=h['hardware_directory'],current_board='stage76 config-sram.fs restored; identity and zero PCM verified',
 current_board_sha256=hw['restore_bitstream_sha256'],tested_sdram_bitstream_sha256=hw['test_bitstream_sha256'],
 flash_accessed=False,tf_accessed=False,fifo_backend_connected=False,persisted=False,full_system_pnr=False,production_qualified=False)
(R/'delivery.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS identities frozen after bounded validation',files=len(files),stage_files=len(stage_files),backups=[b['files'] for b in backups],timing=d['timing'],current_board=d['current_board']),ensure_ascii=False))
