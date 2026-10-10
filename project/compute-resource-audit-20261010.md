# 计算资源审计：只使用Tang Nano 20K FPGA

2026-10-10，用户明确要求不使用其他MCU，唯一应用计算平台为Tang Nano 20K的FPGA。触控扫描、坐标提取、触点追踪、音乐合成、演奏轨迹、波形分析、频谱及实体显示计算全部落在该FPGA。不能靠电脑、外部触控算法控制器、其他开发板或更大FPGA补算后宣布完成。

结论：当前音乐合成链在FPGA中，当前构建未发现MCU固件或CPU软核；项目确实有电脑计算工具及历史MCU方案。全FPGA实体触控和音乐可视化尚未实现，因此目前不能签收“整机全部计算已在Nano 20K”。

## 实际计算与未实施方案

| 位置 | 发现 | 当前判定与处置 |
|---|---|---|
| `src/rtl/tdm_engine.v`、`note_map.v`、`finger_pitch.v`、`osc_env.v`、`fx_delay.v`、`i2s_tx.v` | 声部分配、合成、音高表情、包络、效果与数字输出均为HDL | 当前音乐计算由FPGA承担；本版数字板测证据保留 |
| `src/rtl/pad_scan.v`等旧输入模块；`i2c_master.v` | 旧输入逻辑及独立I²C主机存在 | 不代表新面板满通道坐标/身份追踪已实现；当前诊断板测使用电脑UART模拟触点 |
| `tools/scripts/synth_engine.py`的`cmd_play`、`sounddevice` | 电脑软件合成、键盘演奏、电脑声卡输出 | 确实使用电脑计算；保留为参考/开发工具，不能用作最终FPGA发声的替代证据 |
| `tools/scripts/test_board_hardware.py`、`additive_tool.py` | NumPy FFT、频率/幅度计算及验收断言 | 电脑上的验证计算，分析FPGA样本；不是实体可视化实现 |
| `project/evidence/music-visualization-20261010/plot_actual.py` | 电脑FFT与绘图，数据来自已归档FPGA内部样本 | 图中的声音样本由FPGA产生，但频谱和画图由电脑完成；不能称全FPGA可视化 |
| `tools/host/dsp_gui.py`、配置编辑器、`serial_link.py` | 电脑GUI、配置编辑、UART控制；SimLink可模拟寄存器应答 | 已有上位机功能使用电脑计算；离线模拟不是真实板测。最终实体演奏/分析不能依赖它补算 |
| PSoC/CY8CKIT-041S-MAX历史触控方案 | 曾建议外部MCU扫描、滤波、提取触点 | 用户未下单；当前源码未见其固件/已接顶层。退出方案及采购，数量0 |
| IQS9150等输出坐标/ID的触控控制器建议 | 把触点算法放在外部芯片 | 不满足最新约束，不作为当前备选。原始测量模式若另有候选，须逐器件核实功能边界 |
| `reg_bank.v`注释“将来换成CPU/软核” | 未来接口扩展设想 | 只有注释，未发现CPU软核实例；不是已用算力，也不是后续授权 |
| Primer20K换板、更大FPGA建议、历史9K显示代码 | 历史研究或示例 | 当前平台固定Nano20K；不自动升级或拼接另一块板解决资源不足 |
| 构建/仿真/表生成脚本 | 电脑编译、仿真、生成固定查表数据 | 开发工具计算明确记录，不等于运行时外部协处理器；不能用软件参考结果冒充实体实现 |

## 板上本身有MCU：BL616

Nano20K实物含BL616 MCU。[Sipeed官方说明](https://wiki.sipeed.com/hardware/en/tang/tang-nano-20k/nano-20k.html)列其板载调试器用于FPGA下载和UART通信；项目`tdm_top.v`也标明串口经BL616。这里确实存在MCU，不能描述成“整块板上没有MCU”。当前使用的是下载/串口桥接角色，未发现项目让它承担触控、合成或可视化算法的实现。

本次没有审计BL616原厂固件内部所有行为，以上角色依据官方资料与本项目连接。用户要求的应用计算边界已固定：不为BL616增加乐器功能算法。若按“任何物理MCU芯片都不存在”的字面要求，Nano20K本身也不符合；这个硬件事实需要与“乐器计算只在FPGA”区分。

电极、原始模拟感测/转换、DAC、功放、屏幕接口及存储是电气外围候选，不能以“外围”名义藏入坐标追踪、FFT或音乐算法。最终型号尚未冻结，不把候选自动视为获准采购。

## 检查范围与证据

检查当前`src`、`tools/host`、`tools/scripts`、项目状态/设计/采购/实验计划及技术文档中的相关路径；解析实际`tdm_board_test.gprj`启用文件，与当前04完整源清单核对。当前构建文件列表未发现MCU固件或CPU核；`src`与`tools`未发现C/C++/Arduino/ELF固件输入，`.hex`为音乐查表数据。本结论不是对旧ZIP、厂商固件和所有第三方二进制的穷尽审计。

机器记录与检索原文：[evidence/compute-resource-audit-20261010/record.json](evidence/compute-resource-audit-20261010/record.json)。源码身份仍为`integration-20261010-04`，本次仅改约束、状态和文档，不改变已验RTL、GUI或测试脚本，不删除软件参考和失败证据。

修正文档中仍把PSoC当当前原型、IQS当当前备选、建议升级FPGA及旧采购询价当可执行指令的入口。N-10与N-12保留未实现；当前资源紧张，能否全部装入Nano20K需真实实现、联合综合与PnR证明，不擅自裁掉最新需求或已验32组。
