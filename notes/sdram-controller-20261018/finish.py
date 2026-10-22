# -*- coding: utf-8 -*-
from pathlib import Path
import json,hashlib,zipfile,subprocess,sys
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent;R=P/'experiments/sdram_controller_20261018';E=R/'evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
up=read(R/'upstream.json');U=Path(up['root']);old=read(U/'delivery.json')
assert sha(U/'delivery.json')==up['delivery_sha256']
for rel,h in old['files'].items():assert sha(U/rel)==h,('upstream changed',rel)
frozen={}
for p in (R/'engine').rglob('*'):
 if p.is_file():
  rel=p.relative_to(R).as_posix();assert sha(p)==up['files'][rel];frozen[rel]=sha(p)
for name in ('pcm_sync_fifo.v','pcm_storage_buffers.v','storage_probe.v'):
 rel='rtl/'+name;assert sha(R/rel)==up['files'][rel];frozen[rel]=sha(R/rel)
for name in ('sdram-reference','resource'):
 d=read(E/(name+'.json'));assert d['status'].startswith('PASS')
 for rel,h in d['inputs'].items():assert sha(R/rel)==h,(name,rel)
for mode in ('reference','buffered'):
 D=R/('synthesis_'+mode);d=read(D/'run.json');assert d['status']=='PASS synthesis only'
 for name,v in d['inputs'].items():assert sha(D/name)==sha(R/v['source'])==v['sha256']
resource=read(E/'resource.json');assert resource['logic_spare']>=0 and resource['bsram_spare']>=0
B=Path((N/'latest-backup.txt').read_text());backup=read(B/'manifest.json')
allowed={str(p) for prefix in ('38-','39-','49-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')}
with zipfile.ZipFile(B/'before.zip') as z:
 assert z.testzip() is None
 for path,v in backup.items():
  assert hashlib.sha256(z.read(v['member'])).hexdigest()==v['sha256']
  if path not in allowed:assert sha(Path(path))==v['sha256']
engine=read(P/'experiments/register_memory_20261018/delivery.json')['source_engine']
for label,cwd,args in [('main',P,['tools/scripts/project_baseline.py','--check','notes/baselines/main-2026-10-09-board-diag.json']),('engine',Path(engine['root']),['tools/scripts/project_version.py','check','project/versions/engine-safety-20261014-01.json'])]:
 out=subprocess.run([sys.executable,*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
 (E/('identity-'+label+'.log')).write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode==0
a=resource['before'];b=resource['after'];delta=resource['delta']
title='80-SDRAM单事务控制与时序模型验证-2026-10-18.md'
entry=f'''**2026-10-18 SDRAM控制增量**：[{title[:2]}号]({title})与`experiments/sdram_controller_20261018/project/CURRENT.md`为新存储控制实验。先备份108项；冻结79号引擎/双FIFO，新增16位单事务、32位SDRAM/半字DQM、200us候选初始化、CAS3、显式预充电与自主刷新。2147事务/1090读1057写、95刷新、最长间隔397拍、最长接受后响应11拍及四个故障反例，在自写子集模型范围**已验证**。公平联合综合{a['Logic']}→{b['Logic']}Logic，BSRAM仍{b['BSRAM']}，余{resource['logic_spare']}Logic/{resource['bsram_spare']}BSRAM；整体映射差值不等于控制器固有成本。真实die时序/封装内引脚/约束/收发时钟/PnR/板验仍**待验证/待实现**，没有下载/串口/Flash或介质访问，板上仍76号。FIFO到SDRAM环形缓冲/仲裁尚未连接，TF/文件/非易失/混音仍**待实现**；整机**部分实现**。下一步缓冲调度/在途事务清退与实际SIP包装/模型、资源和板级验证，不把子集模型PASS当实体RAM已可用。'''
report=f'''# SDRAM单事务控制与时序模型验证 · 2026-10-18

## 0. 版本、来源和范围

`sdram-controller-20261018-v0`，入口`experiments/sdram_controller_20261018/project/CURRENT.md`。先读38/39、git状态与main192基线，核对工作树分布与79号435项交付身份；再ZIP备份108项实现/构建入口/文档，校验每项。main HEAD仍`fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12`；本轮main192/engine246输入身份PASS。冻结79号90个引擎/表/缓冲及旧探针输入，不改原源、GUI、旧交付或快照。

控制RTL在记载子集模型和综合范围**已验证**，实体控制路径**已实现待验证**；实际器件时序资格、封装内连接/约束、时钟布线与PnR仍**待实现/待验证**。本轮无新下载、COM、Flash或存储介质访问/采购，板上保留76号。录放整体**部分实现**；没有文件录音、TF或非易失保存，也尚未连接FIFO到SDRAM的环形缓冲。

官方依据：[高云DS226-2.7E](https://cdn.gowinsemi.com.cn/DS226E.pdf)说明QN88搭配64Mbit容量、32位数据宽度的SDR组织，4bank、2048行、256列、4096次刷新/64ms；[Sipeed板卡说明](https://wiki.sipeed.com/en/nano20k)用于核对Nano20K器件/板载资源。[高云控制器接口指南](https://cdn.gowinsemi.com.cn/IPUG279E.pdf)用于核对初始化/模式/命令职责，不声称已实例化其加密IP。安装目录中只有可见包装和受保护实现，未解密或复制其算法。实际封装内die速度档及完整时序表尚未取得/绑定，因此本轮延迟参数是保守工程候选，不能凭模型签收硬件。

## 1. 实现和时序候选

`sdram_word_controller.v`：单时钟、一个16位请求/响应在途，支持8MiB对应的22位半字地址。地址[21:20]选择bank，[19:9]选择行，[8:1]选择列，[0]选择半字；写数据复制到32位DQ，通过DQM1100/0011只修改一半，读时选择所需半字。每次ACT→READ/WRITE→显式PRECHARGE ALL，不实现开放行、突发多字、低功耗或跨时钟接口。

候选时钟27MHz，SDRAM时钟暂以系统时钟反相表示，命令/写数据在系统上升沿后保持，读数据在系统上升沿捕获。该相位关系仅为当前逻辑接口模型，最终必须采用经约束/验证的时钟转发与内部SIP引脚映射；不能直接把这个无CST探针下载并认为可用。

初始化等待5400拍（目标27MHz下200us），随后全预充电、两次自动刷新和模式写入；BL1、CAS3。候选tRP/tRCD/tWR/tMRD均3拍，tRFC9拍；默认ACT至预充电至少6拍，模型还检查tRAS。读取CAPTURE比READ命令晚足够的CAS窗口；写响应与读响应都在预充电恢复后才发布。

刷新计数阈值384拍，到期停止接受新请求，当前事务结束后优先刷新。即使rsp_valid被上游长时间拒绝，仍可在空闲总线发刷新；不让响应反压冻结存储维持任务。响应数据/有效位在等待期间保持，输入引脚变化不修改已锁存地址/数据。reset取消控制器会话并完整重新初始化，不承诺跨复位数据保留、未确认写入的原子性或上层文件一致性。

## 2. 独立模型和实际测试

`tb/sdram_timing_model.v`是自写的SDR命令子集模型：从真实命令/行列/银行/DQM和三态DQ记录数据，独立检查初始化、开放行、tRP/tRCD/tRAS/tWR/tRFC/tMRD、CAS输出、总线争用及刷新期限。它不是原厂die模型，不覆盖所有SDR命令、实际I/O电气、建立保持、温度/电压漂移、保持失效或自刷新；当前输出延时3ns也是模型假设。

`tb/tb_sdram.v`在约27MHz仿真周期运行。32个定向地址覆盖四bank、首末行、首末列和两个半字；再加992个分散地址。写后反向读回，并逐个更新定向半字、检查另一半未改。另测试响应持有2000拍仍能刷新，以及在ACT等待中复位、重新初始化后新写读。该复位点只覆盖所记载的在途状态，不是每一条命令上的穷举复位。

最终实际结果：2147次确认事务，1090读、1057写，95条自动刷新；最长刷新间隔397拍（约14.704us），模型上限421拍（64ms/4096按27MHz取整约束）。最长接受请求至可见响应11拍，未计上游响应等待、复位中断和仲裁/CDC，不能直接当完整录放吞吐或端到端延迟保证。

四个故意错误副本分别缩短tRCD、推迟刷新、写错半字掩码，以及让未消费响应阻止刷新；均因对应时序/内容断言失败，副本不进入选定实现。最初夹具把init刚变高时的ready误报为“初始化前接受”，另将操作期刷新计时起点误当最后REF命令时刻，已修正模型/夹具并重跑；没有为消除这些夹具失败降低目标时序约束。

本轮没有重跑79号双FIFO或78号音乐/配置回归；这些源逐项保持一致，继承对应版本的已绑定证据，不将它们列为本轮重跑。没有门级仿真/完整联合PnR或板级读写验收。

## 3. 联合资源预算

`sdram_storage_probe`在79号音乐＋可视化＋双FIFO探针旁追加真实控制器，原音乐PCM/I²S和缓冲实例保持。请求/响应暂引出逻辑端口，尚未由录制/播放队列驱动，SDRAM总线也只是逻辑端口。reference将新增控制输出接常量，buffered接入控制器；同一器件、工具/工程、文件集合，只有sdram_storage_probe.v内容不同。

| 工程 | Logic | 寄存器 | BSRAM |
|---|---:|---:|---:|
| 本轮无控制器参考 | {a['Logic']} | {a['Register']} | {a['BSRAM']} |
| 控制器接入候选 | {b['Logic']} | {b['Register']} | {b['BSRAM']} |
| 差值 | {delta['Logic']:+d} | {delta['Register']:+d} | {delta['BSRAM']:+d} |

当前余{resource['logic_spare']}Logic/{resource['bsram_spare']}BSRAM。控制器自身层次报告为87寄存器、163LUT、不用BSRAM；联合Logic变化包含其他模块全局映射变化，不能将净增{delta['Logic']}当成控制器固有成本。无完整IO/PnR，余量不能保证TF、文件、环形地址/仲裁、事件轨和混音均可装入。

## 4. 下一步与未决项

继续连接录制/播放FIFO与两块独立SDRAM环形区域，加入读写/刷新有界仲裁和停止后在途事务清退，先用该接口模型做长停顿和清空/换会话测试。随后核对QN88内部存储引脚与专用时钟约束，准备独立RAM板级诊断/复位/吞吐测试；通过后才接TF块与文件、非易失参数和配对事件轨。当前没有可下载的合格SDRAM板级镜像。

若后续资源不足，继续评估同步存储/共享控制等优化，再依据完整PnR决定是否需要双板；本轮不削减复音/泛音、显示、右手分区/保持/全和弦或伴奏目标，不冻结录制量化位置、异常淡出和叠录等音乐交互。SDRAM易失，实际断电保存仍待实现。

测试入口check_sdram.py；资源synthesize.py reference/buffered与audit_resources.py；身份verify_delivery.py只核对文件，不替代功能测试。新交付在适当验证后记录，旧快照不更新。
'''
(P/'docs/02-技术方案'/title).write_text(report,encoding='utf-8')
for prefix in ('38-','39-','49-'):
 path=next((P/'docs/02-技术方案').glob(prefix+'*.md'));text=path.read_text(encoding='utf-8')
 if '**2026-10-18 SDRAM控制增量**' in text:continue
 if prefix=='38-':
  anchor='## 0. 最重要的发现：最新成果并不都在 main\n';assert anchor in text;text=text.replace(anchor,anchor+'\n'+entry+'\n',1)
 else:first,rest=text.split('\n',1);text=first+'\n\n> '+entry+'\n'+rest
 path.write_text(text,encoding='utf-8')
(R/'project/CURRENT.md').write_text(f'''# 当前存储控制实验 · SDRAM80

版本sdram-controller-20261018-v0，整体部分实现。报告：../../../docs/02-技术方案/{title}

- SDRAM单事务控制/模型：记载范围已验证，真实时序/引脚/时钟/PnR/板验待验证或待实现。
- 联合{b['Logic']}Logic/{b['BSRAM']}BSRAM，余{resource['logic_spare']}Logic/{resource['bsram_spare']}BSRAM。
- FIFO到SDRAM环形区/仲裁尚未接入；TF/文件/非易失/最终混音仍待实现。
- 原音乐/双FIFO源码保持79号；本轮没有重跑其全部既有回归。
- 未下载/开COM/访问Flash或介质，板上仍76号，GUI用../envelope_resources_20261017/launch_gui.cmd。
- 此目录没有合格板级镜像。测试check_sdram.py，身份verify_delivery.py。
''',encoding='utf-8')
(R/'README.md').write_text('见project/CURRENT.md。SDRAM逻辑控制与子集模型实验，尚未接合录放队列或完成实体RAM资格验证。\n',encoding='utf-8')
files={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='delivery.json' and p.suffix not in ('.vvp','.o')}
documents={p.relative_to(P).as_posix():sha(p) for prefix in ('38-','39-','49-','80-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')};assert len(documents)==4
d=dict(version='sdram-controller-20261018-v0',status='partial product; SDRAM subset-model RTL tests and joint synthesis verified only; physical timing/pins unqualified',source_main='fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12',upstream_delivery_sha256=up['delivery_sha256'],frozen_inputs=frozen,files=files,documents=documents,stage_scripts={p.relative_to(P).as_posix():sha(p) for p in N.glob('*.py')},backup=dict(root=str(B),files=len(backup),sha256=sha(B/'before.zip')),resource={k:resource[k] for k in ('before','after','delta','logic_spare','bsram_spare')},hardware_tested=False,fpga_programmed=False,serial_opened=False,flash_accessed=False,storage_media_accessed=False,fifo_backend_connected=False,persisted=False,full_system_pnr=False,current_hardware='76 left unchanged',timing_parameters_qualified=False)
(R/'delivery.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS identities after bounded verification',files=len(files),backup=len(backup),resource=d['resource']),ensure_ascii=False))
