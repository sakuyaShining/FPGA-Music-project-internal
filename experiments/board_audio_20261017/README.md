# Nano20K 板级音频测试准备 · 2026-10-17

本目录为**独立的板级诊断工程**，不是最终整机固件。真实上板状态**待验证**，当前仅完成记录的数字仿真、内部27MHz布局布线与文件引脚检查。测试镜像只使用板载时钟、S1、USB串口、6个LED和MAX98357A音频，没有物理滑条、屏幕、TF/SDRAM录放、AUX或机上编辑接口。

源自71号选定的锚点/实例/触点缓存实现。原产品、GUI、71号与旧快照保持；开始前备份542文件。对原核心增加的诊断/复位清音选项默认关闭；与71号三组完整音乐轨迹逐字节比较的记录在`evidence/engine-compatibility.json`。

## 镜像与操作

最终文件、SHA256、器件与模式见`package/manifest.json`：

- `board-audio-sram.fs`：板级音频测试镜像，上电/复位默认静音，约1秒后就绪；启动测试前必须经测试页明确使能。
- `mute-sram.fs`：独立静音回退镜像，PA/DIN/WS/BCK全部为低，无音乐引擎或串口协议。
- `board_check.py`：独立验收脚本，打开指定串口，不调用下载器，不写Flash。

使用Gowin Programmer时，器件核对为GW2AR-LV18QN88C8/I7，仅选**SRAM Program/临时配置**。本轮没有执行下载或读取现有Flash。SRAM配置断电消失，随后按原Flash启动；原Flash内容本轮未识别，不能保证回到某个特定旧程序。静音回退镜像也只用于SRAM。

首轮只连接开发板USB与现有喇叭，外接屏幕、触控和滑条保持断开。不要同时运行原GUI或其他占用同一串口的程序。COM编号由上电后的实际设备确定，旧COM6仅为历史，示例COMx须替换。

```powershell
# 只读身份/状态，不使能喇叭
python experiments/board_audio_20261017/package/board_check.py --port COMx

# 按一次S1复位，等约1秒后，逐项测试；每次运行末尾自动发送停止/静音
python experiments/board_audio_20261017/package/board_check.py --port COMx --case 1 --output board-results/case1
```

脚本先核对测试页C0=0x72、ABI=1、诊断D3、范围32，身份不匹配时不发送使能命令。仅`--case`会使能和演奏，CLI默认只读。先从case1开始，按需要依次执行2～6；压力测试6的喇叭保持静音，观察内部状态/音频，不应期待听见满32组声音。

| case | 内容 |
|---|---|
| 1 | A4单音；检查活动1组、512拍采样、实际数字音频及频率 |
| 2 | C4/E4/G4和弦，活动3组 |
| 3 | 同音双层，活动2组；两个槽的持续/击发仅为诊断样例 |
| 4 | 两音，其中第一个触点来回滑动，第二个保持；诊断观察不得抢走实际绑定 |
| 5 | 约100ms短音后释放，观察尾音；捕获时可能已处在释放段 |
| 6 | 16触点×2层占满32组，再加第17触点触发抢占；喇叭静音，检查34个子ON与最终清音 |

每次演奏约1秒、再留约1.5秒释放时间，期间发送5ms间隔的内部虚拟触点帧。这是测试输入，不代表电容前端/触控延迟已验证。`C2`停止会立即关闭PA/DIN，并在后续帧释放实例；发生固件故障也关闭PA。超时自动结束演奏不代替主机的最后停止检查。

捕获为2048个原始24位单声道PCM，采样率52734.375Hz；USB串口仅回读测试数据，不是录音产品功能。`capture-s24le.bin`与`result.json`记录数字音频、状态和判断。需要pyserial；安装有numpy时额外计算频谱峰值，缺少numpy会明确记`peak_hz=null`，不会假称已验音高。电声听感、模拟输出和外部I²S接收时序仍需实测。

## 复位问题与防回归

新增“按住两层发声时直接复位”测试复现：分配表清空后，时隙存储仍可留下发声。板级选项`BOARD_BOOT_SCRUB=1`在复位释放后两次遍历512时隙：第一遍关门，待提交消费后第二遍清幅度，4096拍后恢复正常装载；约1秒的就绪等待还让固定释放包络稳定。该流程不重写基础引擎，默认关闭，原调用行为保留。

测试检查512个时隙的门控、幅度及待写标志均清空、内部PCM归零。禁用该选项的测试副本再次复现原错误；该副本不进入构建。不能仅凭分配表活动数0判定实际音频已清空。

## 构建与验证

```powershell
python experiments/board_audio_20261017/run_validation.py
python experiments/board_audio_20261017/check_engine_compat.py
python experiments/board_audio_20261017/check_reset_fault.py
python experiments/board_audio_20261017/check_host.py
python experiments/board_audio_20261017/build.py
python experiments/board_audio_20261017/build.py build_mute
python experiments/board_audio_20261017/audit_build.py
python notes/board-audio-20261017/finalize.py
```

生成源入口在`notes/board-audio-20261017/prepare.py`（会先验证并备份71号来源）；后续接口/约束与复位补丁由`finish_source.py`和`add_reset_scrub.py`处理。已建立目录后不要随意重跑prepare覆盖中间结果。实际选定构建源清单/哈希、CST、SDC、工程/Tcl、报告和镜像均纳入本轮交付。

约束仅对27MHz内部路径做时序分析，排除异步复位和UART输入；外部I²S接收器的setup/hold没有在这份SDC中签收。保留工具`clk_d`通用布线警告，不能把出码流视为所有时序/引脚电气验证已完成。历史`build/`、`build_final/`为中间构建，已知复位问题修复前的镜像不可用于本轮测试。

最终选定构建为`build_ready_default/`，内部setup +3.523ns、hold +0.214ns，15258Logic/7287寄存器/36BSRAM。`build_ready/`的place1/route1策略600秒超时，不进入交付；日志保留。
