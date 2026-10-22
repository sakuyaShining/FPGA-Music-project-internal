# Vivado → Gowin 对照表

> **用途**：你只有 Vivado 教程可看，但项目必须用 Gowin 实现。
> 这份表告诉你：**哪些能直接搬，哪些必须换写法，怎么换。**
> 日期：2026-09-18

---

# 一、结论先行

| 内容 | 能否直接搬 |
|---|---|
| **Verilog 语法**（module / always / reg / wire / case / parameter / generate / 状态机 / 计数器） | ✅ **几乎 100% 直接搬** |
| **时序逻辑概念**（时钟、寄存器、流水线、时钟域） | ✅ 100% 直接搬 |
| **Testbench 写法**（除了仿真器命令和文件格式） | ✅ 95% 直接搬 |
| **定点数运算**（Q 格式、位宽管理） | ✅ 100% 直接搬 |
| **约束文件**（引脚绑定、时序约束） | ❌ **必须换语法** |
| **IP 核**（时钟、存储器） | ❌ 必须换 |
| **工具操作步骤**（点哪个按钮） | ❌ 必须换 |
| **开发板引脚号** | ❌ 必须换（每块板都不同） |

**一句话：语言通用，工具不通用。**

---

# 二、工程文件对照

| 概念 | Vivado | Gowin |
|---|---|---|
| 工程文件 | `.xpr` | `.gprj` |
| 物理约束（引脚） | `.xdc` | **`.cst`** |
| 时序约束 | `.xdc`（同一个文件） | **`.sdc`**（分开的） |
| 顶层模块 | 自动识别 或 `set_property top` | 工程里指定 |
| 器件型号 | `xc7z020clg484-1` | **`GW2AR-LV18QN88C8/I7`** |

---

# 三、约束文件：最需要"翻译"的部分

## 引脚绑定

**Vivado（.xdc）**
```tcl
set_property PACKAGE_PIN W5 [get_ports led]
set_property IOSTANDARD LVCMOS33 [get_ports led]
```

**Gowin（.cst）**
```
IO_LOC "led" 51;
IO_PORT "led" IO_TYPE=LVCMOS33 PULL_MODE=UP DRIVE=8;
```

**对照规律**：
| Vivado | Gowin |
|---|---|
| `set_property PACKAGE_PIN X [get_ports Y]` | `IO_LOC "Y" X;` |
| `set_property IOSTANDARD LVCMOS33 [get_ports Y]` | `IO_PORT "Y" IO_TYPE=LVCMOS33 ...;` |
| 引脚号是字母+数字（W5） | 引脚号是**纯数字**（51） |
| 每条语句以 `[get_ports ...]` 结尾 | 每条以 `;` 结尾，名字加双引号 |

> **注意**：Gowin 的引脚号是**芯片封装的物理引脚编号**（纯数字），不是 Vivado 那种"行列坐标"（如 W5）。**这两个编号体系完全不同，不能互推。**

## 时序约束

**Vivado（.xdc）**
```tcl
create_clock -period 10.000 -name clk [get_ports clk]
```

**Gowin（.sdc）**
```tcl
create_clock -name clk -period 10 -waveform {0 5} [get_ports clk]
```

→ **基本一样**（都是 SDC 标准）。区别很小。

---

# 四、IP 核对照

| 你要做什么 | Vivado | Gowin |
|---|---|---|
| **产生一个新时钟（PLL）** | Clocking Wizard (MMCM/PLL) | **rPLL**（IP Core Generator 里） |
| **时钟分频** | BUFGCE_DIV / clk_wiz | **CLKDIV** |
| **块存储器** | Block Memory Generator | **BSRAM**（IP 或让综合器推断） |
| **FIFO** | FIFO Generator | **FIFO**（IP 或自己写） |
| **乘法器** | 直接写 `a * b` 即可推断 DSP | **同样直接写 `a * b`** ✅ |
| **ROM（查表）** | 直接写 `case` 或用 IP | **同样直接写 `case` 或 `$readmemh`** ✅ |

**好消息**：我们项目**只需要 rPLL 一个 IP**。其余（ROM、乘法器、FIFO）都可以靠"写代码让综合器推断"，这部分 Vivado 教程和 Gowin **完全通用**。

---

# 五、工具操作对照

| 步骤 | Vivado | Gowin |
|---|---|---|
| 新建工程 | Create Project | New Project |
| 加源文件 | Add Sources | 工程里 Add Files |
| 加约束 | Add Constraints | 同上（.cst 归为 Constraint 类型） |
| 综合 | Run Synthesis | **Synthesize** |
| 实现 | Run Implementation | **Place & Route** |
| 生成码流 | Generate Bitstream | **Program Device**（会自动生成） |
| 下载 | Hardware Manager | **Gowin Programmer** |
| 在线逻辑分析 | **ILA** (Integrated Logic Analyzer) | **GAO** (Gowin Analyzer Oscilloscope) |
| 资源报告 | `report_utilization` | 综合/布线报告里的 **Resource** 页 |
| 时序报告 | `report_timing_summary` → 看 **WNS/WHS** | Timing Analysis Report → 看 **WNS**（同样叫 WNS）|
| 仿真 | Vivado Simulator (xsim) | Gowin 自带仿真 / 或 Icarus Verilog |

> **WNS（Worst Negative Slack）两边都这么叫** —— 这个术语可以完全通用。

---

# 六、看 Vivado 教程时，这样"翻译"

## ✅ 可以直接吸收的章节

- Verilog 语法讲解
- `always @(posedge clk)` 与时序逻辑
- 阻塞/非阻塞赋值
- 状态机设计
- 计数器、分频器
- testbench 结构与激励写法
- 定点数与位宽管理
- 流水线思想
- 时序收敛的基本概念

## ⚠️ 看到这些要"打标记，回来换"

| 教程里出现 | 换成 |
|---|---|
| `.xdc` 文件 | `.cst` |
| `set_property PACKAGE_PIN` | `IO_LOC` |
| Clocking Wizard | rPLL |
| IP Catalog | IP Core Generator |
| Run Synthesis / Implementation | Synthesize / Place & Route |
| Hardware Manager | Gowin Programmer |
| ILA | GAO |
| 任何 Xilinx 原语（`IBUF`, `BUFG`, `ODDR`...） | 先跳过（我们用不到） |
| 具体引脚号（W5、P4…） | 用 Tang Nano 20K 的引脚号 |

## ❌ 可以跳过的章节

- Xilinx 专用 IP（AXI、Zynq PS 配置、MicroBlaze）
- 7 Series 专用原语
- Vivado 的 Tcl 脚本流程
- HLS / Vitis（另一个工具）
- 器件规划（Floorplanning）高级内容

---

# 七、Tang Nano 20K 的关键引脚（备用）

来源：Sipeed 官方例程 `audio/src/audio.cst`（已验证）

| 信号 | 引脚 |
|---|---|
| 系统时钟（27 MHz） | **4** |
| 板载按键 S1 | **87** |
| 音频：功放使能 PA_EN | **51** |
| 音频：I2S 数据 HP_DIN | **54** |
| 音频：I2S 左右声道 HP_WS | **55** |
| 音频：I2S 位时钟 HP_BCK | **56** |

> 完整引脚图见 Sipeed wiki 的 Tang Nano 20K 页面（`pinlabel` 图）。

---

# 八、Gowin 中文学习资源（不需要 license）

| 资源 | 地址 |
|---|---|
| **高云官方 B 站线上课程** | `space.bilibili.com/1930822744` |
| 高云官网视频教程 | `gowinsemi.com.cn/video_complex.aspx?FId=n15:15:26` |
| **Sipeed Tang 系列中文教程** | `wiki.sipeed.com/hardware/zh/tang/` |
| Tang Nano 20K 官方例程 | `github.com/sipeed/TangNano-20K-example` |
| Gowin 云源软件快速入门指南 | 本地：`D:\FPGA-Project\Gowin\...\IDE\doc\CN\SUG918-2.0_Gowin云源软件快速入门指南.pdf` |
| Gowin 本地全部官方手册（20+ 份） | `D:\FPGA-Project\Gowin\...\IDE\doc\CN\` |

> **本地那 20 多份官方中文手册是个宝库**，而且已经装在硬盘上了——不需要联网、不需要申请。

---

# 九、如果还是遇到具体的"翻译"问题

**看完一个 Vivado 教程章节后，直接告诉我：**
> "教程里用了 XXX 做 YYY，Gowin 里怎么做？"

我会给你**对应的 Gowin 做法 + 可直接用的代码/约束**。

这样你就能**用 Vivado 的教程学，用 Gowin 的工具做**——两边的好处都拿到。

---

# 十、一句话

> **Verilog 不是 Vivado 的语言，它是硬件的语言。**
> 学它用什么工具都行；实现它，只能用能认识你芯片的那个工具。
