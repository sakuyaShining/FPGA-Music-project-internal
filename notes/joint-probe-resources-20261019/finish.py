# -*- coding: utf-8 -*-
"""Record evaluated probe work, failed routing, and unchanged engine boundaries."""
from pathlib import Path
import json,hashlib,zipfile,subprocess,sys,re
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent
R=P/'experiments/joint_probe_resources_20261019';E=R/'evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
assert not (R/'delivery.json').exists(),'never overwrite an evaluated snapshot'
h=read(E/'history-audit.json');t=read(E/'timing-audit.json')
assert h['status'].startswith('PASS') and not h['full_joint_timing_pass'] and t['status'].startswith('FAIL')
for d in (h,t):
    for rel,v in d['inputs'].items():assert sha(R/rel)==v,rel
assert h['inherited_engine_files']==88 and h['changed_upstream']==['rtl/joint_timing_top.v']
assert t['selected']['nominal']['slack_ns'] is None and t['selected']['stress']['slack_ns'] is None
backups=[]
for pointer in ('latest-backup.txt','mac-backup.txt','gap-backup.txt'):
    B=Path((N/pointer).read_text(encoding='utf-8'));items=read(B/'manifest.json')
    with zipfile.ZipFile(B/'before.zip') as z:
        assert z.testzip() is None
        for v in items.values():assert hashlib.sha256(z.read(v['member'])).hexdigest()==v['sha256']
    backups.append(dict(root=str(B),sha256=sha(B/'before.zip'),manifest_sha256=sha(B/'manifest.json'),files=len(items)))
engine=read(P/'experiments/register_memory_20261018/delivery.json')['source_engine']
for label,cwd,args in [('main',P,['tools/scripts/project_baseline.py','--check','notes/baselines/main-2026-10-09-board-diag.json']),('engine',Path(engine['root']),['tools/scripts/project_version.py','check','project/versions/engine-safety-20261014-01.json'])]:
    out=subprocess.run([sys.executable,*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (E/('identity-'+label+'.log')).write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode==0,(label,out.stdout,out.stderr)
out=subprocess.run([sys.executable,'-m','serial.tools.list_ports','-v'],capture_output=True,text=True,encoding='utf-8',errors='replace')
(E/'serial-inventory.log').write_text(out.stdout+out.stderr,encoding='utf-8')
version='joint-probe-resources-20261019-v0';title='86-联合探针资源调整与布线失败边界-2026-10-19.md'
entry=f'''**2026-10-19联合探针资源后续**：见[86号]({title})和`experiments/joint_probe_resources_20261019/project/CURRENT.md`，版本`{version}`。先备份116项，MAC前15项、RAM延迟前11项；85号音乐引擎88文件及全部时序/引脚约束不变。仅把验证探针历史链迁至9个DSP寄存器与96拍RAM延迟，普通寄存器11243→10760；五配置10万拍逐位历史对照、DSP/延迟反例，以及两延迟各200实际音乐PCM录入/读出和200图案播放在限定数字范围**已验证**。联合布局通过，但正常策略仍DesRoute/PR0004，路由**未通过**；PnR报告20478Logic、10357/10368CLS、32BSRAM、22.75/24DSP，无有效setup/hold/recovery/removal余量、无新码流，加严构建未运行。三个前候选路由失败及错误目标中止均保留；不能用0 unrouted字样放行。COM6未找到，串口清单为空，本轮板状态未核实；无下载/发音/Flash/TF操作，最后成功确认仍76号。探针**已实现待验证**、整机**部分实现**，禁止下载结构探针；下一步针对核心高占用/局部路由及真实命令包装继续优化，不擅减复音/泛音或取消可视化，不据此裁定双板。'''
report=f'''# 联合探针资源调整与布线失败边界 · 2026-10-19

## 0. 结论与版本

版本`{version}`，入口`experiments/joint_probe_resources_20261019/project/CURRENT.md`。**前一轮的寄存器放置失败已推进到布局完成，但本轮路由仍失败，没有有效联合时序结果或新板级固件。** 本轮仅调整结构验证探针的输入历史存储；音乐引擎88文件和85号全部引脚/正常及加严时序约束逐文件保持。没有取消音乐功能、减少32组/16分量、改右手规则或擅自决定双板。

新路径**已实现待验证**：限定数字行为已验证，完整物理实现未通过；整机仍**部分实现**。main仍`fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12`，收尾重新核验main192/engine-safety246。备份116项、MAC前15项、RAM延迟前11项，三个ZIP逐成员验证；85/84/83及原源、GUI、旧快照保留。备份指针在`notes/joint-probe-resources-20261019/`。

本轮未下载、未触发音频、未访问Flash或TF。只读查询COM6因端口不存在失败，之后串口枚举为空；**当前板状态未核实**，最后一次成功确认仍为76号。不能推断此次仍在运行，也不将旧固件状态算成本候选实体验证。

## 1. 调整的范围与准确语义

85号输入为587位串行历史，普通寄存器及局部配对接近器件极限。本轮新增`rtl/probe_scan_store.v`，当前顶层选择9个54位MULTALU18X18输出寄存器，乘法输入为0、结果为C，逐拍保存486个活动位；其余活动位使用普通寄存器。

扫描映射26..121为cfg_valid/commit/slot/part/word，共96位。当前核心CONFIG_SERIAL=1，这些并行配置位不被消费，但它们构成串行历史的一部分，不能简单删除，否则后续控制延迟错误。使用128深、1位循环BSRAM及读寄存器保持**恰好96拍**的历史延迟，7位指针初值0、RAM初始化0。并行观察影子保留逻辑正确性；在此顶层未被消费而被工具优化掉。UART配置输入仍动态连接，并非删掉配置功能。

顶层硬化486位、RAM跨越96位、剩余5位；输入/后续控制不增加拍延迟。仍保留两级scan同步器、观察器、27→27MHz PLL与55个SDRAM封装内端口、14个实体引脚。扫描映射由生成器校验配置跨度，生成器重跑后顶层、CST/SDC及映射文件哈希不变。扫描链与旧版一样不由用户复位清空；RAM/指针上电初始化只在模型与综合范围验证，实体未验证。

该结构探针仍没有有效事件命令原子帧，不能直接演奏；956输出位按30块寄存奇偶观察，可能抵消相关信号。外部四根音频输出固定静音，内部音频仍被观察。**禁止下载本探针，bench_gate始终false**；即使未来得到静态时序通过，也需另做真实命令包装和实体功能验证。

## 2. 实际测试

`check_scan_store.py`五配置各20000拍，共100000拍：WIDTH/HARD_WORDS/GAP_SIZE为54/1/0、108/2/0、587/6/0、587/9/96、587/0/96。对独立全宽普通移位寄存器逐位比较，覆盖0/1/随机输入、跨字及循环指针回绕；当前587位包括未消费配置影子的所有位均检查。故意翻转DSP输入位与把RAM延迟改错一拍均被拒绝。该参数模块仅验证上述配置，不宣称任意WIDTH/GAP均支持。

DSP模型从本机已安装高云prim_sim.v精确摘取ALU54D、MULTALU18X18与GSR，来源及整库/片段哈希在reference。最初测试夹具没有模拟上电GSR脉冲，首两拍同步器未知进入宽字算术，X扩散后无法冲出，输入对照失败。修正夹具：上电GSR低、3个负沿后释放；没有强制RTL输入为已知，也没有放宽断言。另保留缺少GSR的故障夹具，仍会失败。厂商模型为功能模型，不能替代真实DSP/BSRAM电气和时序验证。

`check_joint.py`重新运行最终包装与完整引擎，SDRAM读延迟3/16ns两例各125352拍：223个PCM周期，200个非零音乐PCM截位样本录入/逐字读出，200个独立图案回放，刷新310次、最大间隔394拍、PCM间隔512拍，外部音频静音与观察器检查通过。700拍真实输入位移之后，夹具**force内部控制向量**实施有效音乐命令；这是联合数字测试，不是实体串行命令通路。故意翻转录入样本1位被拒绝，缺少上电GSR夹具也被拒绝。

音乐88文件未改，85号原生音高/校准/985PCM旧轨迹等历史证据逐文件身份保留；本轮没有重跑那些回归，不能写成本轮新测试。新的10万拍及联合PCM/故障测试是本轮实际重跑结果。最终回放未接现场DAC混音、TF文件及断电保存仍未实现；83号旧32位诊断比较异常的精确根因仍未解决。

## 3. 构建历史与物理失败

| 构建 | 实际候选 | 结果 |
|---|---|---|
| nominal_v0 | ALU54D六字历史链，默认策略 | 布局通过，路由失败，DesRoute/PR0004，0 unrouted；453.69秒 |
| nominal_v1 | 同一ALU54D，策略1 | 布局通过，路由失败，9571 unrouted；709.22秒 |
| nominal_v2 | MULTALU18X18六字历史链，默认策略 | 布局通过，路由失败，DesRoute/PR0004，0 unrouted；411.34秒 |
| nominal_v3 | 生成路径错误，仍为六字/无RAM延迟 | 主动中止并标记NOT ACCEPTED；58.11秒，无有效综合报告，不是目标候选 |
| nominal_v4 | 最终九字DSP＋96拍RAM延迟 | 布局通过，路由失败，DesRoute/PR0004，0 unrouted；479.45秒 |

v3错误来自生成脚本写错顶层路径，已修正、保留interruption.json，并以全新v4重建。所有历史输入副本/返回码/日志保留，不覆盖失败。三个前候选虽普通寄存器下降，后端占用仍接近上限；只改变策略没有构成修复，故本轮不继续随机试策略。

最终v4综合20164Logic/10760普通寄存器/32BSRAM，相比85号20189Logic/11243寄存器/31BSRAM，普通寄存器减少483，但Logic只减少25；DSP从13.75增至22.75/24。DSP硬寄存器不计入普通寄存器数，不能把减少483解读成总状态减少483或免费资源。

失败PnR报告20478/20736Logic、10357/10368CLS、10760寄存器、32/46BSRAM、22.75/24DSP。后端相对综合额外314Logic：ALU1964→2280、LUT17336→17334；具体产生原因尚未定位，不直接断言是工具错误或唯一拥塞根因。CLS接近100%，仅依赖普通寄存器数量下降不足以证明可路由。

**工具返回1并明确DesRoute failed；PR0004文字即使写0 unrouted也必须判失败。** 没有Bitstream generation completed，没有新.fs，也没有可验收setup/hold/recovery/removal路径表；正常与加严审计slack均null。加严完整构建未运行；缺少DQ最小输入/最大输出约束、负hold反例仍被审计拒绝，不新增内部/SDRAM false path或放宽原时序换通过。

## 4. 资源定位与下一步

| 当前综合层次 | Logic | 普通寄存器 | BSRAM |
|---|---:|---:|---:|
| 音乐 |14710|7238|20|
| 可视化 |2909|1648|7|
| 传感扫描 |1523|1458|2|
| 录放搬运 |501|265|2|
| SDRAM控制 |153|99|0|

以上为层次合计；不能再与父层次重复相加。resource-map.json保留主要/高占用子层次与原始XML身份。当前完整system本身19796Logic，探针与观察开销368Logic；有很小包装开销也不意味着系统可以路由或容纳TF、混音、实际界面等新增功能。

下一步优先检查主要音乐/可视化/扫描层次中的局部状态、访问结构及高扇出路径，给每个优化建立原行为/故障反例，再重新联合PnR；同时评估有原子事件的真实接口包装，避免把本实验DSP消耗方案直接升级为产品架构。不通过减复音/泛音、删可视化或放宽约束制造通过，也不据失败擅自确定双板/扩大预算。

## 5. 交付状态

| 项目 | 状态 |
|---|---|
| DSP/RAM扫描历史存储及顶层接合 | 已实现待验证：数字对照已验证，完整物理实现未通过 |
| 当前五配置历史、两延迟联合PCM及故障反例 | 已验证：限上述模型与激励 |
| 完整联合布局 | 已验证：仅布局阶段完成，不等于物理签收 |
| 完整路由/时序/新板级功能 | 待验证：路由失败，禁止下载本探针 |
| 实际命令包装、最终PCM混音、TF文件/分轨/非易失 | 待实现 |
| 真实显示/触控/模拟音质与本轮板状态 | 待验证 |

`audit_candidate.py`、`audit_timing.py`、`audit_history.py`和`verify_delivery.py`记录实际失败及身份；证据/哈希PASS不能替代布局路由或产品通过。当前选中源码仅用于下一轮研究，不是已签收产品候选。

evidence/build输出位于D:/FPGA-Project/codex-builds/joint-probe-resources-20261019，通过NTFS目录联接访问；复制时需一并保留D盘数据或重跑。其余源与报告位于项目，旧快照保持，不为消除漂移重写基线。
'''
docs=[];p=P/'docs/02-技术方案'/title;p.write_text(report,encoding='utf-8');docs.append(p)
for prefix in ('38-','39-','49-'):
    p=next((P/'docs/02-技术方案').glob(prefix+'*.md'));text=p.read_text(encoding='utf-8')
    if prefix=='38-':
        marker='## 0. 最重要的发现：最新成果并不都在 main\n';assert marker in text;text=text.replace(marker,marker+'\n'+entry+'\n',1)
    else:
        heading,rest=text.split('\n',1);text=heading+'\n\n> '+entry+'\n'+rest
    p.write_text(text,encoding='utf-8');docs.append(p)
current=f'''# 联合探针资源调整 · 86

版本{version}；整机部分实现；报告../../../docs/02-技术方案/{title}

- 85号引擎88文件/全部约束保持，仅替换探针输入历史为9个DSP寄存器与96拍RAM延迟。
- 普通寄存器11243→10760；综合20164Logic/32BSRAM，失败PnR20478Logic/10357CLS/22.75DSP。
- 10万拍全位历史对照、DSP/延迟故障反例及两延迟联合PCM回归通过；旧引擎回归继承身份，未重跑。
- 布局通过、路由FAIL，无有效联合时序、无新码流；加严构建未运行。0 unrouted不是PASS。
- v0/v1/v2路由失败、v3错误目标主动中止、v4最终路由失败，所有输入和日志保留。
- 结构扫描没有有效音乐命令协议，外部静音，禁止下载，bench_gate=false。
- 本轮COM6不存在、串口清单空，当前板状态未核实；最后成功确认76号，无下载/发音/Flash/TF操作。
- 当前源码已实现待验证，不是产品签收；下一步定位局部资源/路由与真实命令包装，保持音乐功能。
- 最终混音/TF文件/非易失/实体显示触控仍待实现或待验证，不据此确定双板/取消功能。
- 输出在D盘联接；证据/身份审计PASS不是路由/时序通过。

实际回归：check_scan_store.py、check_joint.py；资源账：resource_map.py。
审计：audit_candidate.py build_nominal_v4、audit_timing.py、audit_history.py、verify_delivery.py。
保留的check_*_variant.py和reference/probe_scan_store_*为中途候选历史，不是最终源码资格证明。
'''
(R/'project/CURRENT.md').write_text(current,encoding='utf-8');(R/'README.md').write_text(current.replace('../../../docs/','../../docs/'),encoding='utf-8')
files={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='delivery.json'}
stage={p.relative_to(P).as_posix():sha(p) for p in N.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.zip'}
d=dict(version=version,status='部分实现',files=files,documents={p.relative_to(P).as_posix():sha(p) for p in docs},stage_files=stage,backups=backups,
    latest_synthesis=h['latest_synthesis'],joint_placement_status='PASS placement phase only',joint_routing_status='FAIL DesRoute/PR0004',joint_timing_status='NOT AVAILABLE: route failed',
    bench_gate=False,new_hardware_tested=False,current_board='not verified this turn: COM6 absent; last successful observation stage76',
    flash_read_or_written=False,tf_accessed=False,final_mixer_connected=False,files_saved=False)
(R/'delivery.json').write_text(json.dumps(d,indent=2),encoding='utf-8')
print('NEW evaluated snapshot:',version,len(files),'files; backups',[b['files'] for b in backups])
