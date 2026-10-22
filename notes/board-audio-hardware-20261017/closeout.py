"""Publish new hardware evidence; keep the frozen preparation artifacts intact."""
from pathlib import Path
import datetime,hashlib,json,shutil,subprocess,sys
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent;R=P/'experiments/board_audio_20261017';S=Path((N/'LATEST.txt').read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
old=read(R/'delivery.json');preflight=read(S/'preflight.json')
assert sha(R/'delivery.json')==preflight['source_delivery_sha256']
for group in ('source_files','evidence'):
    for rel,digest in old[group].items():assert sha(R/rel)==digest,(group,rel)
backup=read(S/'backup-manifest.json')
for rel,digest in old['design_documents'].items():assert backup[rel]==digest and sha(P/rel)==digest,rel
program=read(S/'program-result.json');assert program['operation']==2 and program['bitstream_sha256']==sha(R/'package/board-audio-sram.fs')
cases={i:read(S/('case'+str(i))/'result.json') for i in range(1,7)}
for i,c in cases.items():
    assert c['status'].startswith('PASS') and c['audio']['samples']==2048
    assert c['after']['active']==0 and not c['status_after']['armed'] and not c['status_after']['fault']
    assert c['during']['period_min']==c['during']['period_max']==512
    if i in (1,2,3,4,6):assert bin(c['during']['active']).count('1')=={1:1,2:3,3:2,4:2,6:32}[i]
assert ((cases[6]['stress_after_capture']['on']-cases[6]['baseline']['on'])&0xffff)==34
release=read(S/'short-note-windows/result.json');assert release['status'].startswith('PASS')
assert release['windows'][0]['audio']['nonzero']>0 and release['windows'][-1]['audio']['peak']==0
reset=read(S/'physical-reset-s2/result.json');assert reset['status'].startswith('PASS') and reset['post_reset_audio']['peak']==0
assert reset['post_reset_snapshot']['ack']==reset['post_reset_snapshot']['active']==0
post=read(S/'post-reset-case1/result.json');assert post['status'].startswith('PASS') and post['audio']['nonzero']>0
feedback=dict(recorded_at=datetime.datetime.now().astimezone().isoformat(),source='direct human replies in this chat',speaker='能听到，暂未发现异常',physical_button='已按S2',limitations='brief subjective observation; no analog instrumentation or quantitative listening test')
(S/'human-feedback.json').write_text(json.dumps(feedback,ensure_ascii=False,indent=2),encoding='utf-8')
prior_current=N/'CURRENT.md';shutil.copyfile(prior_current,S/'notes-current-before.md')
name='73-板级音频实测与复位按键更正-2026-10-17.md'
rows=[]
titles={1:'A4单音',2:'C/E/G和弦',3:'同音双层',4:'两音/单指滑音',5:'短音自动释放',6:'静音满载/抢占'}
for i,c in cases.items():
    a=c['audio'];rows.append('| %d %s | %d | %d | %d | %d |'%(i,titles[i],bin(c['during']['active']).count('1'),a['nonzero'],a['peak'],c['after']['active']))
transition=release['windows'][1]['chunk_rms']
report='''# 板级音频实测与复位按键更正 · 2026-10-17

本轮在用户上电并恢复USB数据连接后，完成板载音频诊断的首轮实体检查。该限定范围**已验证**，完整产品继续**部分实现**。只执行Gowin操作2的SRAM临时配置，没有读写Flash；测试结束设备处于未使能、未演奏、无活动绑定/音符、无故障状态。

## 1. 重要更正：87脚对应S2

当前约束和实际码流的`reset_button`位于FPGA87脚，官方Nano20K rev1.30原理图将其标为`PIN87_MODE1_KEY2 → KEY_S2 → S2`；88脚对应S1。72号及较早记录将87脚文字标成S1，是编号错误。RTL连接和高有效极性未改变，本轮无需重编音频镜像；操作时应按**S2**。

起初按S1后的回读仍为case3、ack192，未观察到复位。失败记录保留在`after-user-reset/result.json`，没有把静音PCM误报为复位通过。更正为S2后，监听捕获计数/状态清空及2048个零PCM；用户回复“已按S2”。旧准备包与72号保留为历史快照，后续操作使用本轮修正说明/包。

## 2. 来源、连接与配置身份

- main `fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12`，engine-safety `683db4834a031baca217b9e3ae7a0369644b8935`，源自71/72号隔离音频诊断，原引擎/GUI/71号/准备交付不变。
- 13:40、13:43两次检查没有USB串口/下载器；13:54重试识别COM5/COM6，FTDI 0403:6010，A/B序列号`2025030317A/B`。本轮实际UART为COM6/B，未向COM5发送串口控制。
- JTAG扫描1个器件，Family GW2AR，ID `0x0000081B`；Gowin操作2“SRAM Program”成功，UserCode `0x94CB`，Status `0x6020`。实际码流SHA256为`7384acdf9fb51f887dc20d1d63ed01a8dc69cb36d78305fc77d9e6a8df8ca246`。
- 实际UART读取profile `0x72`、ABI1、诊断`0xD3`、范围32；使能前ready=true、armed/running/bound/fault=false、活动0。不能仅凭下载器退出0判定正确固件运行。
- 前置583个源/证据文件及包/文档哈希逐项一致；本轮另备份12个交付/入口/包文件，ZIP逐项校验。主机脚本和记录在`notes/board-audio-hardware-20261017/`，具体会话`20261017-135414/`。

## 3. 六项板上检查

每项通过实际UART捕获2048个24位单声道PCM，停止后检查清音；这不是主机合成音频。初轮数字结果如下：

| 测试 | 采样时活动组 | 非零PCM数 | 绝对峰值 | 停止后活动组 |
|---|---:|---:|---:|---:|
'''+ '\n'.join(rows)+f'''

所有采样间隔观察值均为512个FPGA时钟；A4频谱峰约{cases[1]['audio']['peak_hz']:.2f}Hz（以标称27MHz、52734.375Hz采样率换算，未外部校准晶振）。2048样本窗口约38.8ms，FFT补零不增加原始频率分辨率，不能把小数位当绝对音准精度。

压力测试观察活动掩码`0xffffffff`（32组），先16触点×2层，再增加第17触点使子ON增量34；最终ON/OFF相等、活动0、无故障。该例硬件PA/DIN按设计保持静音；主机回读没有外部功放引脚测量，不能独立签收模拟静音电平。

捕获中没有样本命中±24位满量程端点；这只是该检查结果，不等于证明所有混音情况下无溢出/模拟削顶。case3证明两组同时分配及非零音频，采样较晚，未单独定量分离两个音色贡献；case4证明两组运行和音频回读，逐指隔离完整规则还结合71号数字回归阅读。

`fingers`字段来自`finger_pitch.expr_active=enabled`，释放时保留偏移供尾音使用，不是物理手指数。停止后该掩码可以保留；当前清音检查使用分配表active、触点bound、使能与PCM，不能将其非零误判为仍按住。

## 4. 短音补测与实体复位

初轮case5延后捕获时已全部为零，仅足以说明该时刻静音；因此另做三个完整捕获窗口。起音2048样本全非零；释放窗口256样本分块RMS从约{transition[0]:.0f}降到{transition[-1]:.0f}；最终2048样本全零。每次只有一次ON和一次OFF、停止后活动0。触发由Windows/UART控制、偏移为近似，未测精确起音/释音延迟。

S2监听中，复位前最近一次观察有2组活动；按键期间出现一次预期的UART无回应，恢复身份后case/ack/on/off/active/fingers均归零，ready恢复且未使能，无故障，2048个PCM全零。前后快照间隔约{reset['held_sample_age_seconds']:.3f}s，其中包含3秒UART等待；这是抽样观察与用户操作反馈，未用仪器捕获按键边沿或逐一读出512个时隙RAM。512时隙的逐项清空仍以72号仿真为证。

随后重新演奏A4成功，2048样本非零、谱峰约{post['audio']['peak_hz']:.2f}Hz，再停止后active0、armed/running/bound/fault=false。不是只有复位成功、无法恢复演奏的单向检查。

用户对本轮扬声器短音的反馈为“能听到，暂未发现异常”。这补充了真实功放/喇叭路径的基本发声观察，没有示波器、模拟录音或系统听感评测，外部I²S setup/hold和模拟质量仍**待验证**。

## 5. 当前交付与下一步

新入口`notes/board-audio-hardware-20261017/CURRENT.md`，修正包`package/`含相同音频SRAM镜像、静音回退镜像、原校验脚本及S2说明；本轮未下载静音回退镜像。哈希、主机脚本、原始PCM、成功/失败记录与文档状态由新`delivery.json`绑定，旧72号准备快照不覆盖。

本轮没有修改音乐RTL/参数/约束或新增合成配置。测试工程的15258Logic/36BSRAM/14IO与27MHz内部PnR来自72号，不代表包含左手扫描、右手触控和可视化的完整整机容量。临时SRAM配置断电消失，Flash内容未检查。

下一步转向真实屏幕接口/供电/绑带确认、屏幕显示与物理触控小样验证；完整逐层包络/配置应用、四层同时、断电保存、录制伴奏＋实时旋律/曲谱、7英寸界面、完整资源/延迟及约500元制造仍**待实现/部分实现/讨论中**。本轮不减少既定功能或裁定未决音乐交互。
'''
(P/'docs/02-技术方案'/name).write_text(report,encoding='utf-8')
summary=f'''**2026-10-17板级实测**：[73号]({name})与`notes/board-audio-hardware-20261017/CURRENT.md`为最新实体入口。USB恢复后识别COM6/B、GW2AR ID81B，操作2临时SRAM下载成功，实际UART profile72/ABI1/D3正确；六项2048PCM回读、512拍采样、32组满载/34子ON抢占和停止清音在限定板上范围**已验证**。短音另捕获起音/释放下降/最终零PCM；实际复位后计数/绑定归零、2048零PCM，重新A4演奏成功；用户反馈能听到且暂未发现异常。重要更正：约束87脚对应**S2**，旧72/40/41等“S1/87”是文字编号错误，按S1的失败记录保留；码流连接未改。原源/GUI/71/72准备包及旧快照保留，新证据另存，不读写Flash。实体引脚边沿/外部I²S时序/模拟质量、屏幕/触控/完整整机及配置/存储/录放缺口仍待验证/实现；不把短诊断检查外推整机完成。'''
for prefix in ('38-','39-','49-'):
    path=next((P/'docs/02-技术方案').glob(prefix+'*.md'));text=path.read_text(encoding='utf-8');assert '**2026-10-17板级实测**' not in text
    if prefix=='38-':
        anchor='## 0. 最重要的发现：最新成果并不都在 main\n';assert anchor in text;text=text.replace(anchor,anchor+'\n'+summary+'\n',1)
    else:
        first,rest=text.split('\n',1);text=first+'\n\n> '+summary+'\n'+rest
    path.write_text(text,encoding='utf-8')
current=f'''# 当前入口 · 板级音频已完成首轮实体检查

版本`board-audio-hardware-20261017-v1`。限定音频诊断范围**已验证**，整机**部分实现**；详见`docs/02-技术方案/{name}`。原72号准备交付保留，不能把其中“未下载/无听感”和错误的S1文字用于描述本轮最新结果。

## 已完成

- 会话`20261017-135414/`：实际COM6/B，GW2AR ID81B；只执行SRAM Program操作2，无Flash操作。
- 六项板上回读、短音三窗口、S2复位/零PCM、复位后重新演奏；最终未使能、无活动音符/绑定、无故障。
- 物理按键是**S2/87脚**，S1/88脚不触发当前复位。S1失败记录保留，S2成功记录另存。
- 用户反馈“能听到，暂未发现异常”；模拟质量、精确时钟/延迟和外部接收时序仍未验。

## 冻结与下一步

音乐源码/表/约束、GUI、71号和72号包不变。本轮新包在本目录`package/`；源/证据/文档与更正由本目录`delivery.json`绑定。旧准备检查脚本校验的是当时文档快照，入口文档本轮已允许增量更新；后续请使用本轮交付检查入口，不为消除文档漂移覆盖旧快照。

下一步核对真实屏幕接口/供电/绑带并接合显示与物理触控；完整配置/包络、四层同时、非易失、伴奏录放/曲谱、7英寸与500元制造仍待实现/讨论，不宣布整机完成。
'''
prior_current.write_text(current,encoding='utf-8')
package=N/'package';package.mkdir(exist_ok=True)
for rel in ('board-audio-sram.fs','mute-sram.fs','board_check.py'):shutil.copyfile(R/'package'/rel,package/rel)
(package/'README.md').write_text('''# 板级音频实测交付

仅用于Nano20K/GW2AR-LV18QN88C8/I7，profile72/ABI1音频诊断，不是完整产品固件。

**复位按键为S2（87脚），按下高有效**。旧准备说明“S1/87”有编号错误；本轮未改码流的实际引脚。

只采用Gowin操作2 SRAM Program临时配置。该音频镜像本轮已下载并完成限定板上检查，Flash未读写。静音回退镜像本轮未下载。当前硬件测试结束后已停止/静音，断电结束临时配置。

同一台设备本轮UART为COM6、FTDI序列号2025030317B，重新连接须以实际枚举为准。先读身份，再指定测试；脚本不会下载FPGA。

```powershell
python notes/board-audio-hardware-20261017/package/board_check.py --port COM6
python notes/board-audio-hardware-20261017/package/board_check.py --port COM6 --case 1 --output board-results/retest1
```

本轮六项回读、短音补测、实体S2复位及恢复演奏通过，用户能听到且暂未发现异常；不等于完整整机、模拟音质、外部I²S边沿、屏幕/传感或持久录音已验。请看73号报告与父目录CURRENT/delivery。
''',encoding='utf-8')
(package/'manifest.json').write_text(json.dumps(dict(version='board-audio-hardware-20261017-v1',device='GW2AR-LV18QN88C8/I7',profile=0x72,abi=1,reset_button='S2 / FPGA pin87 / active high',mode='SRAM only',audio_image_tested=True,mute_image_tested=False,flash_read_or_written=False,files={p.name:sha(p) for p in package.iterdir() if p.is_file() and p.name!='manifest.json'}),ensure_ascii=False,indent=2),encoding='utf-8')
res=subprocess.run([sys.executable,'tools/scripts/project_baseline.py','--check','notes/baselines/main-2026-10-09-board-diag.json'],cwd=P,capture_output=True,text=True,encoding='utf-8',errors='replace');(S/'identity-main-final.log').write_text(res.stdout+res.stderr,encoding='utf-8');assert res.returncode==0
engine=Path(old['source_engine']['root']);res=subprocess.run([sys.executable,'tools/scripts/project_version.py','check','project/versions/engine-safety-20261014-01.json'],cwd=engine,capture_output=True,text=True,encoding='utf-8',errors='replace');(S/'identity-engine-final.log').write_text(res.stdout+res.stderr,encoding='utf-8');assert res.returncode==0
doc_paths=[next((P/'docs/02-技术方案').glob(prefix+'*.md')) for prefix in ('38-','39-','49-','73-')]
data=dict(version='board-audio-hardware-20261017-v1',status='已验证：限定板载音频诊断；整机部分实现',session=S.relative_to(P).as_posix(),source_main='fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12',source_engine=old['source_engine'],preparation_delivery_sha256=sha(R/'delivery.json'),verified_preparation_files=sum(len(old[g]) for g in ('source_files','evidence')),before_document_hashes=old['design_documents'],current_document_hashes={p.relative_to(P).as_posix():sha(p) for p in doc_paths},hardware_tested=True,serial_opened=True,fpga_programmed=True,programming_operation=2,flash_read_or_written=False,external_i2s_timing_verified=False,analog_instrumented=False,reset_button='S2 / FPGA pin87 / active high',speaker_feedback=feedback['speaker'],final_status=post['status_after'],final_snapshot=post['after'],case_status={str(i):c['status'] for i,c in cases.items()},historical_failures_preserved=['20261017-134049 no USB','20261017-134350 no USB','physical-reset deadline without reset','after-user-reset S1 did not reset'],files={p.relative_to(N).as_posix():sha(p) for p in N.rglob('*') if p.is_file() and p.name!='delivery.json' and '__pycache__' not in p.parts},preflight_script=dict(path='notes/board-audio-20261017/hardware_preflight.py',sha256=sha(P/'notes/board-audio-20261017/hardware_preflight.py')))
(N/'delivery.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status=data['status'],tracked_files=len(data['files']),cases=6,reset_button=data['reset_button'],flash=False),ensure_ascii=True))
