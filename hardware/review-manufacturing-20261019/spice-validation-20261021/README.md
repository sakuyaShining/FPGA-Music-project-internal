# 实际 SPICE 证据 · 2026-10-21

本目录为 ngspice 真实执行输出，包含网表、逐工况波形、进程结果和判据。它补充上一轮 `reassessment-20261021` 的解析计算，不代表整板、热设计或制造放行。PCB/原理图/产品 RTL 未修改。

## 引擎和模型身份

- 引擎：conda-forge Windows ngspice 41，便携目录 `D:/FPGA-Project/codex-tools/ngspice-condaforge-41`，调用 `Library/bin/ngspice_con.exe`。包来源和校验见 `ngspice-download-source.json`。未改变全局 PATH 或用户 SPICE 配置。
- 厂商原包：[TI 官方下载](https://www.ti.com/lit/zip/slvm425)，保存为 `TI-TPS2553-SLVM425.zip`；虽然产品页及另一个版本化 URL 使用 B 后缀，实际下载的两个包内容均为 **SLVM425A / TPS2553_TRANS Final 1.00 / 2011-10-19 / PSpice 16.2**。原库保持原样。
- 原库 SHA256：`7e40f58d8c69445d15f9f153c9624a945191cb83b113f7651a20a7b44df289d8`。
- 独立适配库 `tps2553_ngspice41_compat.lib` SHA256：`6c1f4d13f4fe9bdeca09d898cbaf465825dd42046decdf1951e8abe33fb2582c`。
- 旧 PSpice 库的 XNOR 中 `^` 在本 ngspice 下解释不同，原始真值表 00/01/10/11 得到 1/1/1/0，使能行为错误。原结果拒绝用于判断硬件。仅在副本中把一个布尔 XOR 表达式换成加括号的不等式；器件参数未变。最小差异见 `ngspice-compatibility.diff`。
- 适配后 XNOR/AND/OR 共 12 个静态逻辑向量通过；禁止输出、正常使能、欠压、限流四个功能校准通过。此校准没有证明与 PSpice 或实物完全等效。独立动态校核见 `dynamic-model-checks.json`。
- 每个 `cases/*` 自带 `.spiceinit`，仅设置 `ngbehavior=ps`。运行器删除该工况旧波形后再执行，检查返回值、有限数值及完整终止时间，避免把残留文件当新结果。

## 已执行范围

矩阵共 **16 个 I²C + 32 个电源工况**，另有原库/适配库逻辑检查、4 个基础功能校准、1 个数据手册条件时序校核和 2 个输入塌陷步长复查。矩阵成功执行表示数值输出完整、预设判据得到检查，**不表示每个负载均能工作**。

I²C：单一总线段内 1/2/3 组 4.7kΩ 并联，50/100/200/400/600pF 假设电容，共 15 组；另加 0.1Ω 卡低负对照。开漏为 Ron=2Ω 的开关。上升时间测量 30%–70%，与解析计算偏差均小于 1.5%；卡低无法越过阈值被正确识别。1000/300ns 标记只判断 Standard/Fast 上升时间，不代表完整协议符合性或固件恢复验证。TCA9517 主动行为未包含；A/B 两侧不可跨缓冲器并联计算。

电源：使用 TPS2553 厂商模型适配副本，输入电容 2.2µF、R67=23.7kΩ、输出泄放 10kΩ；输出电容总量假设 4.4/104.4/1004.4µF、ESR=0.05Ω。上游 0.25/0.35/0.5/0.75Ω 是电缆/PTC/PMOS 的合并电阻情景，没有替代这些器件的完整模型。负载包含电阻与恒流两种；恒流使用 `I*tanh(Vout/0.05)` 在零电压附近平滑，因此 1.2A 是需求目标，并非在崩溃电压下实际抽取 1.2A。

覆盖输入先到/EN 先到的 18 个启动组合、6 个输入压降、2 个 R67±1%、2 个负载模型对照，以及 4 个动态情景。动态事件全部位于 60ms，预事件 55–59ms 输出必须已高于假定 4.5V，仿真到 100ms。输入断开使用理想隔离开关；输入强制拉至 0V 另列为 `power_input_collapse`。后者出现的反向电流另做步长复查，不能把强制输入塌陷当物理拔插。

4.5V 仅是用于比较的示意门槛，**尚无具体屏幕 SKU 的最低供电规格支撑**。大电容启动与负载模型对照延长到 80ms，防止 40ms 尚未稳定时错报终值。所有时间均从网表仿真 t=0 起算。

## 数据与边界

- `spice-validation-summary.json`：汇总、遗漏项、PCB 前后哈希和 `manufacturing_release=false`。
- `model-calibration.json`、`dynamic-model-checks.json`：独立校准与步长检查，不与矩阵工况计数混淆。
- `i2c-spice-results.csv`、`power-spice-results.csv`：具体假设和测量值；`final_*` 是末 10% 时间窗口平均值，不自动证明已达物理稳态。
- `spice-transients.png`：部分代表工况图；每个完整波形见 `cases/<case>/waveform.txt`。
- `calibration-tps2553`、`calibration-logic-original` 是早期未适配探索，已拒绝。`cases/gates_original` 为特意保留的兼容性失败负对照。
- 动态条件校核得到 EN 50% 至输出 90% 约 2.00ms、EN 50% 至输出 10% 约 1.60ms，均在所查数据手册 3ms 上限内；这里只覆盖该轻载条件。塌陷最大步长 100/50ns 的反向峰值接近。另一次 20ns 尝试超过 90s 超时而终止，明确排除，不计为完成或通过。
- `final-verification.json` 核验 19 个原生文件未变、48 个矩阵工况和另外 9 个进程完整完成（含特意失败的原库逻辑负对照）；`evidence-sha256.json` 索引证据文件。源文件未变的检查不替代重新运行 DRC。

未覆盖 PTC 热/动作、真实 DMP2035U 反接与栅极瞬态、AP2112 稳定性/热耗、实际屏幕 UVLO/启动/内部电源、PCB 提取寄生、器件工艺与温度角落、系统固件超时恢复。强制输入塌陷峰值还受实际线缆电感、供电输出阻抗与 PMOS 行为影响，不能作为额定值或实物峰值发布。

## 复现

在本目录依次运行（Python 需 numpy、matplotlib）：

```powershell
$env:PYTHONIOENCODING = 'utf-8'
& 'D:\anaconda\python.exe' .\calibrate_models.py
& 'D:\anaconda\python.exe' .\run_validation_matrix.py
& 'D:\anaconda\python.exe' .\check_dynamic_model.py
& 'D:\anaconda\python.exe' .\finalize_evidence.py
```

更换机器时先按已记录包 SHA256 准备引擎，再调整 `spice_runner.py` 引擎绝对路径及矩阵中的项目位置。不得跳过原库负对照、适配校准或源文件身份检查。所有脚本写入本证据目录，不写入原生工程。
