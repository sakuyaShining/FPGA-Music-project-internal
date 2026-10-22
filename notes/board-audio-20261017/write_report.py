from pathlib import Path
import json,hashlib
P=Path(__file__).resolve().parents[2];R=P/'experiments/board_audio_20261017'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
audit=read(R/'evidence/build-audit.json');selected=audit['profiles']['build_ready_default'];mute=audit['profiles']['build_mute']
s=selected['slack_ns'];m=selected['resource'];ms=mute['slack_ns']
assert s['Setup']>0 and s['Hold']>=0
doc_name='72-板级音频诊断准备与复位清音验证-2026-10-17.md'
report=f'''# 板级音频诊断准备与复位清音验证 · 2026-10-17

本轮交付是可供下一步实体测试的隔离工程。板级入口**已实现待验证**；限定数字仿真、内部约束布局布线及文件引脚审计**已验证**，整机继续**部分实现**。用户尚未上电，本轮没有打开实际串口、识别当前COM口、下载FPGA、读取或写入Flash，也没有听感/模拟信号证据。

## 1. 来源与保护

- main源码版本`fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12`，基线192文件；engine-safety版本`683db4834a031baca217b9e3ae7a0369644b8935`，身份清单246文件。最终校验日志纳入`evidence/identity-*.log`。
- 采用[71号](71-资源优化与逐拍等价回归-2026-10-16.md)选定的锚点共享、实例预取与触点缓存实现，未替换原产品源、GUI、71号或历史快照。
- 修改前542文件ZIP/哈希备份位于`notes/board-audio-20261017/backup-20261017-000946/`。旧main194/engine318/integration108受保护输入及71号来源在最终清单再次核对；仅本轮38/39/49入口文档允许增量更新。
- 当前源码、表、约束、主机脚本、测试与构建均在`experiments/board_audio_20261017/`，版本`board-audio-20261017-v0`。入口为`project/CURRENT.md`，交付身份见`delivery.json`。

## 2. 板级范围与引脚

真实器件须在上电前后核对为Nano20K的`GW2AR-LV18QN88C8/I7`。14个端口按既有官方原理图记录及41号板级证据固定，没有把候选滑条/显示信号接到未知排针。

| 信号 | FPGA管脚 | 用途 |
|---|---|---|
| clk | 4 | 板载27MHz |
| reset_button | 87 | S1，高有效，异步置复位/两拍同步释放 |
| UART RX/TX | 70 / 69 | USB串口，配置115200 |
| PA / DIN / WS / BCK | 51 / 54 / 55 / 56 | 板载MAX98357A音频 |
| LED[0..5] | 15..20 | 就绪、使能、演奏、绑定、故障、心跳，低有效 |

CST读回确认恰为14脚、LVCMOS33；S1配置下拉。板级工程不使用旧CST中的复位极性和未经确认的27..42排针假设。来源可追溯至`notes/hardware-closeout-20261015/evidence/nano20k-3921-rev130.*`及41号，不表示本轮重新检查过实体板版本。

输入是5ms一次的内部虚拟26端点报告，经过实际逐指绑定、双层分配与合成链；物理电容扫描和右手触摸输入不在此镜像。四槽v0表仅含频谱/比率/衰减/延音，示例使用两个槽，不是完整自定义乐器应用。

上电/复位后默认PA和DIN静音，清音完成并等待约1秒后才就绪；主机明确使能后才能出声，故障或停止会静音。WS/BCK正常运行；case6全程PA/DIN静音。每例约1秒演奏，再留约1.5秒释放；自动结束演奏不替代主机的停止清音检查。

## 3. 发现并修复的复位问题

新增“按住双层音直接复位”的测试发现：实例分配表可以已空，而时隙RAM仍留下发声参数。此前只检查活动数归零不足以检出该错误。原失败日志保留在`evidence/pre-scrub-reset-failure.log`。

只在板级副本启用`BOARD_BOOT_SCRUB=1`：复位释放后第一遍遍历512时隙关门，等待提交消费后第二遍清幅度；4096拍内挡住正常事件消费，随后恢复处理，约1秒就绪等待让固定释放包络稳定。新增参数默认关闭，原调用行为保持。启动未知的基础实现历史边界仍存在于默认关闭路径；不能把包装层静音说成基础引擎所有启动未知已修复。

测试逐项检查512时隙的门控、幅度、待写标志和最终PCM归零；禁用清音的故障副本再次触发同一断言，见`evidence/reset-fault.json`。该副本不进入构建。实际S1、电气上电和真实音频清音仍**待验证**。

## 4. 本轮数字验证

| 验证 | 结果与范围 |
|---|---|
| 板级顶层仿真 | 146064拍、284PCM、259非零、40ON/38OFF/12移动、213 UART字节；末尾复位取消仍按住的2个实例，不把ON/OFF不等直接解释为悬音 |
| 上电与复位 | 冷启动静音、未使能忽略演奏、两层按住复位、512时隙清空、解除复位后继续默认静音 |
| 实际波特率配置 | 115200配置的234拍分频下身份/使能/A4/快照/512拍采样/停止通过；仍为仿真 |
| 音频/实例 | 和弦、双层、独立滑音、释放、32组满载/抢占；诊断观察不夺走真实逐指绑定 |
| 默认参数兼容 | 三场景506645拍、985PCM，完整逐拍PCM/I²S/事件/表情TSV与71号逐字节一致 |
| 防回归反例 | 禁用板级清音修复后再现原复位错误，反例未进入正常构建 |
| 主机离线检查 | 9项：错误身份/地址回声/长度拒绝、分块2048样本捕获、符号/快照端序、削顶分析、忙帧重试等 |

加速串口仿真只捕获64样本，实体配置仍为2048个24位单声道PCM，标称采样率27MHz/512=52734.375Hz；两者不混称。完整证据与输入SHA见`evidence/validation.json`、`engine-compatibility.json`及`host-validation.json`。

## 5. 实际布局布线与限制

选定工程`build_ready_default/`使用Gowin V1.9.11.03 Education、默认布局布线策略、27MHz内部时钟约束；已生成码流并通过独立报告/引脚审计。

| 工程 | Logic | 寄存器 | BSRAM | I/O | 最差setup余量 | 最差hold余量 |
|---|---:|---:|---:|---:|---:|---:|
| 当前音频诊断 | {m['Logic']} / 20736 | {m['Register']} | {m['BSRAM']} / 46 | 14 | +{s['Setup']:.3f}ns | +{s['Hold']:.3f}ns |
| 独立静音回退 | 29 | 25 | 0 | 14 | +{ms['Setup']:.3f}ns | +{ms['Hold']:.3f}ns |

两者内部setup/hold TNS=0、违例端点0。SDC只声明内部27MHz，异步UART与按键入口排除；未签收外部I²S接收器setup/hold，工具`clk_d`通用布线警告保留。实际电气/晶振误差/功放/听感不能由上述数字推出。

当前14脚诊断工程常量化了实体前端/右手/可视化等路径，与71号完整探针19892Logic/43BSRAM口径不同；不得用诊断余量证明整机容量，也不能据此决定加板或取消功能。

`build/`和`build_final/`是复位修复前中间结果，不用于本轮测试。`build_ready/`尝试place1/route1在600秒超时，已终止本轮对应子进程，日志及失败记录保留；最终采用默认策略重新构建，未用超时结果出包。

## 6. 可操作的实体测试交付

最终包为`package/`，SHA256、模式和器件见其`manifest.json`：

- `board-audio-sram.fs`：当前音频诊断镜像。
- `mute-sram.fs`：独立静音回退镜像，PA/DIN/WS/BCK为0；不是历史完整固件的恢复副本。
- `board_check.py`：只用串口的验收脚本，不调用下载器，不读写Flash。默认只读身份/状态；显式`--case`才使能声音，结束或异常后发送停止并检查清音。

计划仅用**SRAM临时配置**。本轮未执行下载，未读取当前Flash内容；断电会结束临时配置并按原Flash启动，不能承诺原Flash里是某个特定历史程序。实际COM口须上电后确认，不沿用历史COM6。

首轮只连接开发板USB与现有3W/4Ω喇叭，暂不接外部屏幕/触控/滑条。核对器件与连接后依次检查身份、单音、和弦、双层、独立滑音、短音释放、静音32组压力、按住复位；保存`result.json`/原始PCM与听感。详细命令在实验README。串口回读仅为诊断数据，不是产品录音功能。没有numpy时频峰记null，不能当作已验证音高。

## 7. 下一步及未完成事项

下一步需要用户上电配合进行上述实体测试，真实故障应先定位并新增回归再继续叠加功能。屏幕接口/供电/绑带仍需实物核对，屏幕刷新和右手7英寸触控下一阶段再接。

完整逐层起音/释音/效果器、四层同时、设备端完整配置应用/断电保存、伴奏PCM录放与实时旋律同步/曲谱、实体电容滑条及≤10ms延迟、完整屏显/整机资源/约500元制造仍**待实现/部分实现/讨论中**，本轮不替用户裁定新音乐交互规则、不采购或打板。
'''
(P/'docs/02-技术方案'/doc_name).write_text(report,encoding='utf-8')
summary=f'''**2026-10-17板级音频准备**：用户此前未上电；新增[72号]({doc_name})及`experiments/board_audio_20261017/project/CURRENT.md`。先备份542项，隔离14脚音频诊断与静音回退，保持原源/GUI/71号及旧快照；发现按住双层音复位后时隙可残留发声，板级默认启用两遍512时隙清音/启动围栏，默认关闭路径仍与71号三组506645拍/985PCM逐字节一致。板级284PCM/40ON38OFF/12移动、实际115200配置仿真、512时隙清零及故障反例、主机9项检查在限定数字范围**已验证**。最终默认策略PnR {m['Logic']}Logic/{m['Register']}寄存器/{m['BSRAM']}BSRAM/14IO，内部27MHz setup +{s['Setup']:.3f}ns、hold +{s['Hold']:.3f}ns、TNS0；策略1超时保留，外部I²S/实体未验，诊断资源不外推完整71号/整机。交付SRAM临时镜像/静音回退/只读默认串口脚本，**已实现待验证**；未开实际串口、下载、读写Flash/采购，下一步上电核验并保存真实音频与状态证据，完整配置/录放/7英寸等缺口保持。'''
for prefix in ('38-','39-','49-'):
    path=next((P/'docs/02-技术方案').glob(prefix+'*.md'));text=path.read_text(encoding='utf-8')
    marker='**2026-10-17板级音频准备**'
    if marker in text:raise RuntimeError('already updated: '+str(path))
    if prefix=='38-':
        anchor='## 0. 最重要的发现：最新成果并不都在 main\n'
        assert anchor in text;text=text.replace(anchor,anchor+'\n'+summary+'\n',1)
    else:
        first,rest=text.split('\n',1);text=first+'\n\n> '+summary+'\n'+rest
    path.write_text(text,encoding='utf-8')
state=dict(version='board-audio-20261017-v0',status='已实现待验证',verified='限定数字仿真、内部27MHz PnR、文件引脚身份',source_main='fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12',source_engine='683db4834a031baca217b9e3ae7a0369644b8935',selected_build='build_ready_default',resource=m,slack_ns=s,hardware_tested=False,serial_opened=False,fpga_programmed=False,flash_read_or_written=False,next='用户上电后核对器件/连接/串口，SRAM临时测试')
(R/'project/state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
readme=R/'README.md';text=readme.read_text(encoding='utf-8').replace('当前仅完成记录的数字仿真与离线检查','当前仅完成记录的数字仿真、内部27MHz布局布线与文件引脚检查')
text+='\n最终选定构建为`build_ready_default/`，内部setup +%.3fns、hold +%.3fns，%dLogic/%d寄存器/%dBSRAM。`build_ready/`的place1/route1策略600秒超时，不进入交付；日志保留。\n'%(s['Setup'],s['Hold'],m['Logic'],m['Register'],m['BSRAM'])
readme.write_text(text,encoding='utf-8')
(R/'package/README.md').write_text(text,encoding='utf-8')
print('report/entry/state prepared; rerun package audit then finalize to bind document hashes')
