# -*- coding: utf-8 -*-
from pathlib import Path
import json,hashlib,zipfile,subprocess,sys
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent;R=P/'experiments/pcm_buffer_20261018';E=R/'evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
up=read(R/'upstream.json');U=Path(up['root']);old=read(U/'delivery.json')
assert sha(U/'delivery.json')==up['delivery_sha256']
for group in ('source_files','evidence','inherited_76_artifacts'):
 for rel,h in old[group].items():assert sha(U/rel)==h,('original modified',rel)
frozen={}
for p in (R/'engine').rglob('*'):
 if p.is_file():
  rel=p.relative_to(R/'engine').as_posix();assert sha(p)==up['source_files'][rel];frozen[rel]=sha(p)
for name in ('fifo-reference','buffers','resource'):
 d=read(E/(name+'.json'));assert d['status'].startswith('PASS')
 for rel,h in d['inputs'].items():assert sha(R/rel)==h,(name,rel)
fifo=read(E/'fifo-reference.json')
for aw,data in fifo['results'].items():
 assert sha(E/('fifo-'+aw+'.in'))==data['stimulus_sha256']
 assert sha(E/('fifo-'+aw+'.tsv'))==data['trace_sha256']
resource=read(E/'resource.json');assert resource['logic_spare']>=0 and resource['bsram_spare']>=0
for mode in ('reference','buffered'):
 D=R/('synthesis_reference_retry' if mode=='reference' else 'synthesis_buffered');d=read(D/'run.json');assert d['status']=='PASS synthesis only'
 for name,v in d['inputs'].items():assert sha(D/name)==sha(R/v['source'])==v['sha256']
 assert sha(D/'probe.gprj')==d['project_sha256'] and sha(D/'synth.tcl')==d['tcl_sha256']
B=Path((N/'latest-backup.txt').read_text());backup=read(B/'manifest.json')
allowed={str(p) for prefix in ('38-','39-','49-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')}
with zipfile.ZipFile(B/'before.zip') as z:
 assert z.testzip() is None
 for path,v in backup.items():
  assert hashlib.sha256(z.read(v['member'])).hexdigest()==v['sha256']
  if path not in allowed:assert sha(Path(path))==v['sha256']
for label,cwd,args in [('main',P,['tools/scripts/project_baseline.py','--check','notes/baselines/main-2026-10-09-board-diag.json']),('engine',Path(old['source_engine']['root']),['tools/scripts/project_version.py','check','project/versions/engine-safety-20261014-01.json'])]:
 out=subprocess.run([sys.executable,*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
 (E/('identity-'+label+'.log')).write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode==0
before=resource['before'];after=resource['after'];delta=resource['delta']
title='79-录放双向缓冲与停顿边界验证-2026-10-18.md'
entry=f'''**2026-10-18录放缓冲增量**：[{title[:2]}号]({title})和`experiments/pcm_buffer_20261018/project/CURRENT.md`为新存储实验入口，音乐引擎沿用78号。先备份206项；新增两路1024×16同步RAM FIFO、录制溢出锁存/连续前缀保护、播放读空报告与独立清空。2/8/1024深度共153180拍独立队列参考/坏指针反例、2290578拍双路压力仿真通过；512拍采样、约14.81ms后台停顿后2344录制样本完整、同时2304播放样本无读空。公平联合综合{before['Logic']}→{after['Logic']}Logic、{before['BSRAM']}→{after['BSRAM']}BSRAM，余{resource['logic_spare']}Logic/{resource['bsram_spare']}BSRAM。限定数字缓冲/综合**已验证**，无PnR/板验；SDRAM/TF控制器、文件保存、非易失、最终混音/曲谱配对仍**待实现**。本轮无下载/串口/介质/Flash访问，板上仍76号，原源/GUI/快照保持；录放整体**部分实现**。小FIFO单向满容量约19.42ms，不能保证卡停顿；下一步SDRAM初始化/刷新/读写与缓冲调度资源探针，后端切换还须清退在途事务。'''
report=f'''# 录放双向缓冲与停顿边界验证 · 2026-10-18

## 0. 版本与范围

`pcm-buffer-20261018-v0`，独立实验`experiments/pcm_buffer_20261018`。音乐引擎冻结复制78号，实际复制{len(frozen)}个源码/表文件逐项与78号相同；本轮新增缓冲模块、压力测试、联合资源探针。main HEAD仍`fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12`，main192与engine246身份PASS。先ZIP备份206项并逐项校验；原引擎、GUI、78号交付和旧快照不覆盖。

缓冲原语在记载RTL测试及联合综合范围**已验证**；录放整体**部分实现**，实际SDRAM/TF控制器、文件保存、断电保留、伴奏混音和事件/曲谱配对均**待实现**。本轮没有PnR、实体测试、下载、COM、Flash/存储介质访问或采购；当前板上仍76号。不能把测试里的内存队列或回读数据称为已保存的录音。

## 1. 实现

- `pcm_sync_fifo.v`：同一时钟的弹性FIFO，容量精确为2^AW，包含预取头。默认1024×16，单同步RAM读；读数据不复位，以head_valid屏蔽旧数据；指针/水位/有效位可清空。空队列写入后要经过预取，不能假定零延迟直通。满队列允许同拍取出并写入，输出被反压时保持内容稳定。
- `pcm_storage_buffers.v`：录制与播放两路独立FIFO。录制入口不反压音乐引擎，首次无法接收就锁存错误并拒绝后续采样，已经排队的数据可继续排出，形成可识别的连续前缀；必须clear后重新使用。它是错误保护原语，不冻结实体UI如何提示、停止/保存损坏录音等交互。
- 播放按外部sample_tick请求消费；有数据时寄存输出play_valid/data，空时发play_miss并锁存play_underflow。它不擅自插零、重复上一音或决定淡出/恢复策略；未来混音器必须处理miss，不能忽略后继续报成功。此时序需要与最终音频流水线对齐，尚未接入I²S混音。
- clear只清队列及该方向错误，不是后端请求取消。接后端后必须先停发、清退/确认在途事务，再清队列开始新会话；当前没有世代标识/跨时钟桥，旧事务隔离和复位同步仍属后端接合要求。

默认每方向2KiB。采样频率沿用27MHz/512=52734.375Hz，1024样本理论容量约19.418ms，实际余量随水位变化；该小FIFO只承担片内解耦，不能替代61号规划的SDRAM大环形缓冲，也不能保证任意TF卡busy时长。

`storage_probe.v`沿原instrument_layer_probe追加旁路缓存测量，现场PCM/I²S、左右手、分层、可视化实例和连线保持。输入取monitor PCM[23:8]仅作为本次16位资源探针，最终录制位置、量化/饱和和文件格式仍需与真实输出核对。播放数据只引出逻辑端口，没有混入发声链；并行双路压力测试不代表批准叠录功能。

## 2. 验证证据

| 测试 | 实际结果 |
|---|---|
| 独立Python deque参考 | 深度2/8/1024分别50032/50050/53098拍，共153180；全满、全空、同拍进出、反压保持、指针回绕、40次/组复位或清空；内容/顺序/容量/占用逐拍核对，允许定义内的一拍预取等待 |
| 反例 | 故意将读指针每次增2，深度8在cycle19即检出应为1却得到2；错误副本只用于测试 |
| 双路压力 | 2290578拍：先双路填满，录制溢出保护时播放仍可完整消费1024样本；读空明确报告；clear后不泄漏旧播放数据 |
| 原生采样节拍 | 每512拍一次采样，后台前400000拍不排出录制（按目标27MHz换算约14.8148ms），再分段排出；2344样本全部有序排出，期间播放2304样本且无读空/录制溢出 |
| 超预算停顿 | 连续提供1100个样本且不排出，只保留前1024，明确锁存溢出；不恢复成中间有洞却无错误的录音 |

测试是独立序列和理想后台握手，不是实体SDRAM/SD卡时序或可听音质测试。冻结音乐引擎源码/表完全相同，因此本轮继承78号既有音乐/配置回归证据，没有重复声称本轮重跑这些测试或104项GUI测试。无门级仿真、无完整联合PnR。

## 3. 联合资源

Gowin1.9.11.03、GW2AR-18C，同一storage_probe顶层/工程、同一冻结音乐与显示等源；reference只将新增缓存输出接常量，buffered接入实际两路缓存。两边输入集合和工程文件相同，只有storage_probe.v不同，报告逐项绑定。

首轮reference生成报告后gw_sh没有正常退出，核对进程归属后主动终止；终止操作返回了0，但该次明确标记NOT ACCEPTED，不当作成功构建。记录保留在synthesis_reference，正式参考使用正常完成的synthesis_reference_retry。不能仅以报告存在或外部终止后的返回码0判定通过。

| 工程 | Logic | 寄存器 | BSRAM |
|---|---:|---:|---:|
| 本轮无缓存参考 | {before['Logic']} | {before['Register']} | {before['BSRAM']} |
| 双路缓存接入 | {after['Logic']} | {after['Register']} | {after['BSRAM']} |
| 差值 | +{delta['Logic']} | +{delta['Register']} | +{delta['BSRAM']} |

当前余{resource['logic_spare']}Logic、{resource['bsram_spare']}BSRAM。这是无最终GPIO的综合预算，不是已通过布局布线或全存储功能容量保证。两路缓存实际各一块BSRAM；保持19.42ms容量而不减少泛音、复音或修改演奏规则。后续控制器、地址仲裁、事件暂存、混音和平滑等还要占用资源，不能重复使用78号的17块余额。

## 4. 下一步与未决项

下一步隔离SDRAM初始化、刷新、读写和有界仲裁，先用时序模型和资源探针验证，再接本FIFO；之后才是TF块读写、超时/CRC/提交恢复、文件和配对事件轨。当前队列clear不能撤销外部读请求，必须在后端接合时补事务清退/会话隔离测试。实卡资格、最大busy、供电扰动、外部时序、真实整机PnR仍须实测。

文件录制与伴奏播放的用户操作、读空后的平滑处理、录制量化位置、叠录/循环/变速等未决项保持；本轮不替用户冻结。原右手分区/同侧最近/两侧中点/松手保持/全和弦、两八度滑条、四槽自定义和伴奏目标不变。非易失参数保存同样尚未实现，SDRAM不是掉电存储。

入口：`check_fifo.py`、`check_buffers.py`、`synthesize.py reference/buffered`、`audit_resources.py`。`verify_delivery.py`仅核对交付文件身份；新快照在本轮适当验证后建立，旧快照不改。当前设备仍使用76号已实测入口，此目录没有新板级镜像可供下载。
'''
(P/'docs/02-技术方案'/title).write_text(report,encoding='utf-8')
for prefix in ('38-','39-','49-'):
 path=next((P/'docs/02-技术方案').glob(prefix+'*.md'));text=path.read_text(encoding='utf-8')
 if '**2026-10-18录放缓冲增量**' in text:continue
 if prefix=='38-':
  anchor='## 0. 最重要的发现：最新成果并不都在 main\n';assert anchor in text;text=text.replace(anchor,anchor+'\n'+entry+'\n',1)
 else:first,rest=text.split('\n',1);text=first+'\n\n> '+entry+'\n'+rest
 path.write_text(text,encoding='utf-8')
(R/'project/CURRENT.md').write_text(f'''# 当前存储实验 · PCM双向缓冲79

版本pcm-buffer-20261018-v0，音乐引擎沿用78号，录放整体部分实现。
报告：../../../docs/02-技术方案/{title}

- 两路1024×16FIFO/错误保护：限定数字测试与联合综合已验证，无PnR/板验。
- 联合{after['Logic']}Logic/{after['BSRAM']}BSRAM，余{resource['logic_spare']}Logic/{resource['bsram_spare']}BSRAM。
- 新增缓冲不是SDRAM/TF控制器、文件保存或混音；这些仍待实现。
- 无下载/COM/Flash/介质访问，板上仍76号，GUI继续../envelope_resources_20261017/launch_gui.cmd。
- 验证check_fifo.py、check_buffers.py；身份verify_delivery.py。冻结引擎在engine/，原78号不修改。
- 下一步SDRAM控制与缓冲调度、后端会话隔离/资源验证，再接TF、非易失、录放/事件轨。
''',encoding='utf-8')
(R/'README.md').write_text('见project/CURRENT.md。独立PCM存储缓冲实验，暂无实体存储后端或下载镜像。\n',encoding='utf-8')
files={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='delivery.json' and p.suffix not in ('.vvp','.o')}
documents={p.relative_to(P).as_posix():sha(p) for prefix in ('38-','39-','49-','79-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')};assert len(documents)==4
d=dict(version='pcm-buffer-20261018-v0',status='partial recording/playback product; bounded FIFO/stream RTL tests and joint synthesis verified only',source_main='fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12',upstream_delivery_sha256=up['delivery_sha256'],frozen_engine=frozen,files=files,documents=documents,stage_scripts={p.relative_to(P).as_posix():sha(p) for p in N.glob('*.py')},backup=dict(root=str(B),files=len(backup),sha256=sha(B/'before.zip')),resource={k:resource[k] for k in ('before','after','delta','logic_spare','bsram_spare')},hardware_tested=False,fpga_programmed=False,serial_opened=False,flash_accessed=False,storage_media_accessed=False,media_backend_implemented=False,persisted=False,mixing_implemented=False,full_system_pnr=False,current_hardware='76 left unchanged')
(R/'delivery.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS identity capture after verification',files=len(files),backup=len(backup),resource=d['resource']),ensure_ascii=False))
