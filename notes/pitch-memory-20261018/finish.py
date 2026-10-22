# -*- coding: utf-8 -*-
"""Publish a new evaluated snapshot only after resource and regression gates pass."""
from pathlib import Path
import json,hashlib,zipfile,subprocess,sys
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent
R=P/'experiments/pitch_memory_20261018';E=R/'evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
assert not (R/'delivery.json').exists(),'never overwrite an evaluated delivery'
for name in ('regression-audit','resource'):
    d=read(E/(name+'.json'));assert d['status'].startswith('PASS')
    for rel,h in d['inputs'].items():assert sha(R/rel)==h,(name,rel)
a=read(E/'resource.json');m=read(E/'config-music.json')
up=read(R/'upstream.json')
for prefix in ('','board_'):
    U=Path(up[prefix+'root']);assert sha(U/'delivery.json')==up[prefix+'delivery_sha256']
    for rel,h in up[prefix+'files'].items():assert sha(U/rel)==h,(prefix,rel)
B=Path((N/'latest-backup.txt').read_text());items=read(B/'manifest.json')
with zipfile.ZipFile(B/'before.zip') as z:
    assert z.testzip() is None
    for v in items.values():assert hashlib.sha256(z.read(v['member'])).hexdigest()==v['sha256']
H=Path((N/'latest-restore.txt').read_text(encoding='utf-8'));hw=read(H/'result.json')
assert hw['status'].startswith('PASS') and hw['zero_pcm_samples']==2048
assert hw['script_sha256']==sha(N/'restore_stage76.py')
assert sha(Path(hw['image']))==hw['image_sha256']
engine=read(P/'experiments/register_memory_20261018/delivery.json')['source_engine']
for label,cwd,args in [('main',P,['tools/scripts/project_baseline.py','--check','notes/baselines/main-2026-10-09-board-diag.json']),('engine',Path(engine['root']),['tools/scripts/project_version.py','check','project/versions/engine-safety-20261014-01.json'])]:
    out=subprocess.run([sys.executable,*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (E/('identity-'+label+'.log')).write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode==0
version='pitch-memory-20261019-v0'
title='84-音高状态分存与资源优化验证-2026-10-19.md'
entry=f'''**2026-10-19音高状态资源优化**：见[84号]({title})与`experiments/pitch_memory_20261018/project/CURRENT.md`，版本`{version}`。先备份102项，82号音乐/存储副本仅改pitch_mod状态存储；96万拍四配置逐拍/全组对照、两故障反例、原三组506645拍/985PCM轨迹逐字节一致及配置/包络回归，在限定数字范围**已验证**。公平综合{a['before']['Logic']}→{a['after']['Logic']}Logic，省{-a['delta']['Logic']}，BSRAM仍31，余{a['logic_spare']}Logic/15BSRAM；寄存器增加{a['delta']['Register']}，并非整表变成RAM。无完整联合PnR或新音高实体验证，优化路径**已实现待验证**，整机**部分实现**。系统盘耗尽期间的轨迹/构建不签收，转D盘后完整重跑并保留失败；没有删除历史交付。用户断电后已用操作2重载76号，COM6身份/512拍/2048零PCM通过，无Flash/TF或新听感结论。下一步音乐＋实际SDRAM时钟联合时序，再接回放混音/文件；83号旧比较异常根因仍待定位，不据本轮综合解除。'''
report=f'''# 音高状态分存与资源优化验证 · 2026-10-19

## 0. 结果与版本

版本`{version}`，实现目录`experiments/pitch_memory_20261018/`。本轮完成音高状态存储优化及限定数字回归，**已验证**；优化后真实实体路径**已实现待验证**，整机**部分实现**。不是完整伴奏录放交付，也没有整机时序签收。

开始读取38/39及工作树分布、git状态、main192基线。先将102项输入（音乐/调度源码、旧交付与对应设计文档等）做ZIP/哈希备份，归档入口`notes/pitch-memory-20261018/latest-backup.txt`。main仍`fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12`；engine-safety246身份另核对，不覆盖旧快照。82/83号及原GUI/旧产品源保持。

用户于10月19日告知断电，实际重载76号`package/config-sram.fs`，SHA256 `{hw['image_sha256']}`。识别B串口COM6、A调试器和GW2AR/ID81B，仅操作2 SRAM；身份C0/C2/C3=72/76/01、D0/D1=75/01、A4/A9=D3/20、活动音符0、采样512拍、2048个零PCM通过。没有Flash/TF访问、发音测试、物理S2或新的模拟听感验收。板上是76号，**不是本轮84号优化版**。记录`{H.relative_to(P).as_posix()}`。

## 1. 实现及保持的规则

唯一改变的上游实现是`engine/src/pitch_mod.v`。旧表允许背景逐组更新与指令写入在同一拍写不同音符组，因此不能简单改成单写口RAM或删除其中一笔写入。新实现分开command_mem和materialized_mem，使用initialized/from_command元数据决定可见值；复位清元数据并隐藏旧RAM内容，指令与后台写同组时仍由指令优先。未增加输出拍延迟，保留即时写旁路、pending逻辑读取、重复样本overrun、滑音步长、LFO/颤音与限幅算术。

同条件综合实际只推断出部分分布式RAM，后台数据/其他状态仍消耗寄存器；不能说整表已放入RAM。保留gq逻辑视图供旧源码全组对照，未被真实逻辑读取的调试视图会优化掉。32组/16分量和原双层原型不减配，右手分区/松手保持/全和弦等音乐交互规则不变；没有借资源优化冻结尚未确定的轨数、循环或叠录语义。

## 2. 数字验证

- NG/QW分别2/18、8/18、32/18、32/20，各240000拍，合计960000拍。与冻结82号旧源码比较poff、overrun、epoch元数据及每组逻辑状态；包含正负极值、0/65535步长、sample与指令重合、同组竞争、不同组双写、样本突发和每例12次异步复位，另比较拍间地址/开关变化。属于有限激励对照，不是形式证明或门级验证。
- 两个故意破坏版本分别失去指令优先权、泄露复位前RAM，均被对应存储/输出断言拒绝；没有进入选定实现。
- 原三组506645拍、985PCM的和弦修饰/双层/触点音乐完整轨迹，与71号有效参考逐字节一致；另在包络配置开启下重跑原兼容/双层轨迹并逐字节一致。签收审计新增逐行序号检查，避免只读到内部PASS便忽略文件不完整。
- 独立包络参考50000拍、49999更新，覆盖五状态、4149次消费与1016次释放元数据保持；最大包络分频两次回绕/门事件检查通过。
- 自定义配置到实际PCM链覆盖独立ADSR、编辑后旧音快照、持续/混合/击发与最终静音。实际测试输出：`{m['log'].splitlines()[0]}`。这里的配置HEX为冻结上游测试数据，本轮未重跑主机GUI/文档编译器或显示/存储全套测试。

已有启动首PCM/前512拍I2S未知的历史记录仍保留；本轮不以旧轨迹一致宣称该边界已修复。83号诊断旧32位最终比较异常根因仍待定位，本轮没有解密受保护网表或验证旧比较电路。

## 3. 公平资源对照与时序边界

Gowin V1.9.11.03教育版、GW2AR-LV18QN88C8/I7，同一完整逻辑探针`sdram_stream_probe`、同一工程文件列表，仅替换pitch_mod源码。选定构建`synthesis_reference_final`和`synthesis_buffered_bank_v3`均正常结束，逐输入/副本/工程/报告哈希核对；完整音乐、旧可视化/扫描和双向SDRAM搬运均在该逻辑资源探针内。

| 指标 | 旧实现 | 新实现 | 变化 |
|---|---:|---:|---:|
| Logic | {a['before']['Logic']} | {a['after']['Logic']} | {a['delta']['Logic']} |
| 寄存器 | {a['before']['Register']} | {a['after']['Register']} | +{a['delta']['Register']} |
| BSRAM | {a['before']['BSRAM']} | {a['after']['BSRAM']} | 0 |

剩余{a['logic_spare']}/20736 Logic、15/46 BSRAM。音高模块细项见`evidence/resource.json`，实际增加20个分布式RAM资源项、LUT1591→1209、寄存器654→718；单项不能直接换算成全部Logic差值。这是用分布式存储/元数据与逻辑映射交换资源，收益有限。

本轮**没有联合PnR/新的板级音高路径测试**。该顶层是大量外部逻辑端口的资源探针，不能直接按它分配物理GPIO或下载。实际27MHz PLL、SDRAM内部SIP引脚/时钟和完整音乐的联合包装、全部约束/最坏路径仍**待实现/待验证**；节省305Logic不证明文件控制器/最终混音/7英寸触屏均已容纳，也不证明更高时钟可用。83号独立stress hold仅0.011ns，旧工程时序/确切die温压风险不能由本轮综合消除。

## 4. 验证过程中的失败与输出位置

最早候选先有sweep声明顺序导致Icarus编译拒绝，调整声明位置；bank_v1为调整前输入的正常综合候选，不能代替当前源码签收。测试迁移至engine/src后，旧相对HEX路径少一级导致配置/双层读表失败，修正夹具路径后重跑。故障注入脚本最初使用系统默认GBK读UTF8失败，已明确UTF8并重跑四组及两个反例。

系统盘耗尽期间出现文件截断/拼接以及写运行记录报Errno28；即使内部音乐断言或工具日志称完成，也不计为有效验证。bank_v2无完整运行记录，标NOT_ACCEPTED；当时损坏轨迹与部分日志保留在evidence/disk-full-failures，失败复制残片亦保留，不能冒充完整原始轨迹。未确定每一个破损字节的操作系统根因，不把该失败归于音频RTL。转移输出后重新生成完整轨迹并核对旧哈希，当前有效结果通过。

仅本轮生成的evidence及synthesis_*输出转移/新建在`D:/FPGA-Project/codex-builds/pitch-memory-20261018/`，项目中以NTFS目录联接保留入口；源码、备份及既有历史交付未搬移/删除。发布哈希追踪联接后的实际文件，复制项目时必须同时保留这些输出目录或重新运行验证。构建脚本为新的输出自动建联接，默认目录不得覆盖；失败与有效构建分开保存。

## 5. 交付状态与下一步

| 项目 | 状态 | 下一步 |
|---|---|---|
| 音高状态旧源对照、音乐/配置回归、公平综合 | 已验证 | 限上述数字与资源范围 |
| 新音高路径实体行为/完整联合时序 | 已实现待验证／待实现 | 建实际时钟/SDRAM音乐联合包装，约束审计后PnR与板验 |
| 断电后恢复76号及静音身份 | 已验证 | 本轮实际SRAM恢复，不是84号板验 |
| 最终回放与现场声音混音、TF块/文件、非易失配置 | 待实现 | 接真实数据链和异常恢复，不用易失SDRAM代替断电保存 |
| 完整实体显示/触控、长时运行/模拟质量 | 待验证 | 外设到手后按板级计划实施 |

下一步先做实际音乐＋SDRAM时钟/接口联合时序，保持新的逻辑余量账，再接伴奏PCM混音和文件链。不得通过减少复音/泛音或更改用户音乐规则换取通过。

功能入口check_pitch_memory.py、check_engine_compat.py、check_enabled_compat.py、check_music.py、check_envelope.py、check_phase_wrap.py；签收audit_regression.py、audit_resources.py。verify_delivery.py只读身份，不是功能重跑。notes下restore_stage76.py会真实下载SRAM，仅用于已授权的板子；普通回归不调用它。delivery.json为本轮验证完成后新增的快照，保留上游旧快照。
'''
docs=[]
report_path=P/'docs/02-技术方案'/title;report_path.write_text(report,encoding='utf-8');docs.append(report_path)
for prefix in ('38-','39-','49-'):
    p=next((P/'docs/02-技术方案').glob(prefix+'*.md'));text=p.read_text(encoding='utf-8')
    if prefix=='38-':
        marker='## 0. 最重要的发现：最新成果并不都在 main\n';assert marker in text
        text=text.replace(marker,marker+'\n'+entry+'\n',1)
    else:
        heading,rest=text.split('\n',1);text=heading+'\n\n> '+entry+'\n'+rest
    p.write_text(text,encoding='utf-8');docs.append(p)
current=f'''# 当前音高状态优化 · 84

版本{version}；整机部分实现，报告../../../docs/02-技术方案/{title}

- 仅改变82号pitch_mod状态存储，原源/GUI/调度/旧交付保持。
- 96万拍旧源对照、两个故障反例、三组完整PCM/I2S轨迹及配置/包络回归，在限定数字范围已验证。
- 完整逻辑探针{a['before']['Logic']}→{a['after']['Logic']}Logic，余{a['logic_spare']}Logic/15BSRAM；寄存器增加64。
- 无完整音乐/实际SDRAM联合PnR，新音高实体路径已实现待验证。
- 用户断电后已重载76号，COM6身份/512拍/2048零PCM通过；没有下载84号。
- 原首PCM/I2S启动未知、83号旧比较异常原因/时序边界保持。
- 系统盘耗尽的旧轨迹/bank_v2不签收；输出使用D盘目录联接，源码和旧交付不搬移。
- 最终混音、TF/文件/非易失配置仍待实现；下一步实际音乐＋SDRAM联合时序。
- 普通verify_delivery/audit_*均离线；notes/restore_stage76.py会真实操作SRAM。
'''
(R/'project/CURRENT.md').write_text(current,encoding='utf-8')
(R/'README.md').write_text(current.replace('../../../docs/','../../docs/'),encoding='utf-8')
files={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='delivery.json'}
stage={p.relative_to(P).as_posix():sha(p) for p in N.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.zip'}
delivery=dict(version=version,status='部分实现',files=files,documents={p.relative_to(P).as_posix():sha(p) for p in docs},stage_files=stage,
    backups=[dict(root=str(B),sha256=sha(B/'before.zip'),manifest_sha256=sha(B/'manifest.json'),files=len(items))],
    resource=a['after'],logic_spare=a['logic_spare'],full_system_pnr=False,new_pitch_hardware_tested=False,
    current_board='stage76 verified SRAM configuration diagnostic',stage76_restore_status=hw['status'],
    flash_read_or_written=False,tf_accessed=False,files_saved=False,final_mixer_connected=False,
    external_generated_output='D:/FPGA-Project/codex-builds/pitch-memory-20261018')
(R/'delivery.json').write_text(json.dumps(delivery,indent=2),encoding='utf-8')
print('NEW evaluated snapshot',version,len(files),'experiment identities;',len(stage),'stage files')
