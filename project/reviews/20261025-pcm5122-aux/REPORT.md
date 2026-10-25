# PCM5122 / AUX 风险核查

对象：载板 `native/pcb/PCB1.epcb2` + `native/sch/Schematic1/04_PCM5122_AUX.esch2`
产品顶层：`fpga/current/engine/src/tdm_ship_owned.v` → `tdm_top_owned.v` → `i2s_tx.v` / `audio_clk_en.v`
依据：TI SLAS763C（PCM5121/5122 数据手册，本地 `PCM5122.pdf`，121 页）

---

## 〇 结论

| # | 判断 | 后果 | 修法 |
|---|---|---|---|
| **R1** | PCM5122 被接成 **I²C 软件模式**（MODE1=GND、MODE2=DAC_3V3） | 手册规定软件模式下 **没有** BCK-PLL 自动回退；而产品 RTL 里**一个 I²C 主机都没有** | RTL 加 I²C 初始化，或改板回硬连线模式 |
| **R2** | I²S 是 32 BCK/帧、16 bit；芯片默认 24 bit | 位长不匹配，行为不确定 | 软件模式写 Reg40=0x00；硬连线模式必须把帧改成 64 BCK |
| **R3** | SCK 接地 + SREF 默认选 SCK + SCK-halt 检测默认开 | 上电即"时钟错误"→ standby → **静音** | 写 Reg13 / Reg37 |
| **R4** | `pa_en` 硬接 1（`tdm_top_owned.v:1405`） | 载板上板载 MAX98357 与 AUX **同时出声** | RTL 改 0，或做成参数 |
| **R5** | I²S 三线无串阻，且 DAC 与 FPGA 是两个独立电源域 | 先给 FPGA 上电时，电流经 U12 输入保护二极管倒灌 | 三根线各加 22–33 Ω 串阻 |
| **R6** | XSMT 只靠 R40(100k) 上拉到 3V3，FPGA 不可控 | 上电 pop，且无法软静音 | 引一根 GPIO 到 XSMT，或明确接受 pop |
| **R7** | J12 是外部插孔，ESD 未定型（原理图自注） | 静电直击 U12 输出 | 加 ESD 器件 |

**一句话**：AUX 现在**一定不出声**，卡在数字侧（R1 + R3），不是模拟链路。
模拟链路本身**是对的**（§五），不需要改。

---

## 一 证据链：引脚级映射是怎么解开的

上一轮卡在「`.esch2` 里 NET 属性与 PIN 的 `parentId` 不重合，取不到引脚级连接」。本轮换路径解决：

1. `.esch2` 里 `WIRE` 记录是空壳（`{"type":"WIRE","id":"..."}|||`），几何被剥离 → 原理图侧做不出连通性。
2. 但 `PCB1.epcb2` 的 `PAD_NET` 记录带完整信息：
   ```
   {"type":"PAD_NET","id":"[\"PAD_NET\",\"<component-uuid>\",\"<pad>\",\"<padid>\"]"}
   ||{"padNet":"GND"}
   ```
3. 再用 `COMPONENT` + `ATTR(Designator)` 把 `component-uuid` 翻成位号 → **全板 256 个网络、每个焊盘的归属全部还原**。
4. 用原理图截图 `schematic-png/04_PCM5122_AUX.png` 做视觉交叉确认，逐脚一致。

**结论：旧卡点作废，载板已经是可查询的网表。** 解析脚本思路记在 §附录。

---

## 二 U12 引脚级网络表（28 脚）

符号 `aa39f479ed69e903`（LCSC C962071，PCM5122PWR，TSSOP-28）的脚号↔脚名，与 PCB `U12` 的 pad↔net，两边对齐后**无错位**：

| pin | 名称 | 网络 | 判定 |
|---|---|---|---|
| 1 | CPVDD | DAC_3V3 | 电荷泵供电 ✓ |
| 2 | CAPP | DAC_CAPP | ✓ |
| 3 | CPGND | GND | ✓ |
| 4 | CAPM | DAC_CAPM | ✓ |
| 5 | VNEG | DAC_VNEG | ✓ |
| 6 | OUTL | DAC_L_RAW | → R41 → AUX_L |
| 7 | OUTR | DAC_R_RAW | → R42 → AUX_R |
| 8 | AVDD | DAC_3V3 | ✓ |
| 9 | AGND | GND | ✓ |
| 10 | VCOM | **GND** | VREF 模式，原理图注记已声明 ✓ |
| 11 | SDA | I2C_MOD_SDA | 见 §三 |
| 12 | SCL | I2C_MOD_SCL | 见 §三 |
| 13 | GPIO5 | (nc) | 内部下拉 ✓ |
| 14 | GPIO4 | (nc) | 内部下拉 ✓ |
| 15 | GPIO3 | (nc) | 内部下拉 ✓ |
| 16 | **ADR2** | **GND** | 地址位 = 0 |
| 17 | **MODE1** | **GND** | **← R1 的关键** |
| 18 | **MODE2** | **DAC_3V3** | **← R1 的关键** |
| 19 | GPIO6 | (nc) | 内部下拉 ✓ |
| 20 | **SCK** | **GND** | **← R3 的关键** |
| 21 | BCK | I2S_BCK | ← J5.7 / FPGA 56 |
| 22 | DIN | I2S_DIN | ← J5.8 / FPGA 54 |
| 23 | LRCK | I2S_LRCK | ← J5.11 / FPGA 55 |
| 24 | **ADR1** | **GND** | 地址位 = 0 |
| 25 | XSMT | DAC_XSMT | 仅 R40(100k) 上拉 |
| 26 | LDOO | DAC_LDOO | 内部 LDO 输出，仅 C21 去耦 ✓ |
| 27 | DGND | GND | ✓ |
| 28 | DVDD | DAC_3V3 | ✓ |

**MODE1=GND、MODE2=DVDD 在原理图截图里肉眼可辨**，与 PCB 网表完全一致。

---

## 三 R1 + R3：为什么默认配置一定静音

### 3.1 手册的硬规定

> **8.3.6.3 Clock Slave Mode With BCK PLL to Generate Internal Clocks (3-Wire PCM)**
> "In **hardwired mode**, the device starts up expecting an external SCK input, but if BCK and LRCK start
> correctly while SCK remains at ground level for 16 successive LRCK periods, then the internal PLL starts,
> automatically generating an internal SCK from the BCK reference."
> "**In software mode, the user must set all the PLL registers and clock divider registers for referencing BCK.**"

MODE1=GND / MODE2=DVDD 按手册 §6 就是 **I²C Mode**，不是 Hardwired。
⇒ **硬件模式那条"SCK 接地也能自动从 BCK 起 PLL"的兜底，在这块板上不存在。**

### 3.2 寄存器默认值推演（全部来自手册表格，不是推测）

| 寄存器 | 位 | 默认 | 含义 | 在这块板上的后果 |
|---|---|---|---|---|
| P0/0x04 | b0 PLLE | **1** | PLL 使能 | PLL 是开的，但没给对基准 |
| P0/0x0D | b6:4 SREF | **000** | PLL 基准 = **SCK** | SCK 被接地 → 基准是死的 |
| P0/0x25 | b1 DCAS | **0** | 时钟自动配置 **开** | 自动配置也依赖有效 SCK |
| P0/0x25 | b3 IDCH | **0** | SCK 停振**视为错误** | SCK=GND 直接报时钟错误 |
| P0/0x25 | b4 IDSK | **0** | SCK/LRCK 比值**校验** | 比值=0，越界报错 |
| P0/0x02 | b4/b0 | 0 | 非 standby / 非 powerdown | 上电本身不静音 |

**推演**：上电 → PLL 使能但基准=接地的 SCK → 同时 SCK-halt 检测开着 → 判为时钟错误 → DAC 进 standby → **DAC 输出恒为静音**。
这条链上**没有任何一处**能在没有 I²C 写入的情况下自愈。

### 3.3 I²C 通路本身是通的（不是断线问题）

| 段 | 端点 | 器件 |
|---|---|---|
| FPGA 侧 | **J6.10 / J6.11** = **FPGA 25 / 26** | 见 `pin-map-audit-20261024.md` §6.1，且 §6.5 已逐条核对 csv |
| 上拉 | R33 / R34 → 3V3_IO | 100k 级 |
| ESD | U10（pad 1-4,7=GND；5=SDA；6=SCL；8=3V3_IO） | 保护阵列 |
| 电平转换 | U14：A 侧 I2C_SDA/SCL(3V3_IO) ↔ B 侧 I2C_MOD_SDA/SCL(3V3_PERIPH) | 双向 |
| 上拉 | R60 / R61 → 3V3_PERIPH | |
| 从机 | U12.11 / U12.12 | 7 位地址 **0x4C**（写 0x98） |
| 旁路 | J10.8 / J10.9（外设模块口） | |

**地址**：手册 §8.4.1.1.2.1 地址字节 = `1 0 0 1 1 ADR2 ADR1 R/W`；ADR2=ADR1=0 → `0x98/0x99`（7 位 0x4C）。

**电源**：`J13 → F1 → 5V_PROTECTED → U17 → 5V_PERIPH → U13(LDO) → DAC_3V3`、`U18(LDO) → 3V3_PERIPH`。
**不是**靠 J10 的外设模块供电（J10.1 是往外送 5V 的），所以不插模块时 DAC 依然有电。

**产品 RTL 现状**：`fpga/current/` 下搜不到任何 I²C 主机例化。产品顶层 `tdm_ship_owned` 的端口里也没有 I²C。
⇒ **R1 的"没人配置"是字面意义上的没人。**

---

## 四 R2：I²S 帧格式不匹配

`audio_clk_en.v`：`DIV_BCK=18`、`BCK_PER_LRCK=32`
⇒ BCK = 27 MHz / 18 = **1.5 MHz**，fs = 1.5 MHz / 32 = **46875 Hz**（32 BCK/帧）
`i2s_tx.v`：`SW=24, DW=16` ⇒ **每声道 16 bit**，Philips I²S，MSB first

PCM5122 `P0/0x28` 默认 `ALEN=10` ⇒ **24 bit**。
32 BCK/帧只能装 16 bit/声道，与 24 bit 期望不符。多数 DAC 会取前 16 位不报错，但这是**未定义行为**，不能当设计依据。

- 走软件模式：写 `P0/0x28 = 0x00`（I2S + 16 bit），与现帧**精确匹配**，RTL 音频路径零改动。
- 走硬连线模式：无法改字长 ⇒ **必须**把 RTL 改成 64 BCK/帧（`DIV_BCK=9`，BCK=3 MHz，fs 仍 46875），这也正好落在手册 Table 33 的 `48 kHz / 64fs = 3.072 MHz` 那一档。

---

## 五 AUX 模拟链路核查：**结论是正确，不需要改**

```
U12.6 OUTL ──R41(100Ω)──┬── AUX_L ── C27(1nF) ── GND
                        └── J12.1 (TRS Tip)
U12.7 OUTR ──R42(100Ω)──┬── AUX_R ── C28(1nF) ── GND
                        └── J12.2 (TRS Ring)
J12.3 ── GND (Sleeve)
```

| 检查项 | 结论 |
|---|---|
| 要不要隔直电容 | **不要**。PCM5122 有片上负压电荷泵（CPVDD/CAPP/CAPM/VNEG），输出以 0 V 为中心，本来就允许直流耦合 |
| R+C 是不是音频低通 | 不是。fc = 1/(2π·100Ω·1nF) = **1.59 MHz**，只在音频带外做 EMI 抑制，20 kHz 处衰减可忽略 |
| 电平是否适配 AUX | 是。手册标称单端 **2.1 Vrms**，标准线路电平 |
| 插座 | J12 三极 TRS：Tip=L、Ring=R、Sleeve=GND，正确 |
| 与板载喇叭冲突 | 见 R4 —— 这是**唯一的**模拟侧逻辑问题 |

**所以"AUX 风险"的真正落点不在模拟，而在"数字侧根本没把 DAC 叫醒"。**

---

## 六 两条修法

| | **A. 改板：回硬连线模式** | **B. 改 RTL：加 I²C 初始化** |
|---|---|---|
| 改动 | MODE2 从 DAC_3V3 改到 GND；另需给 ATT2:1:0 定电平（硬连线下 GPIO 变增益脚，现在是 NC 悬空） | 新增 I²C 主机 + 初始化 ROM，挂到 pin 25/26 |
| 板子 | 要动（当前原理图已标 `NOT FOR FABRICATION`，本来就要改版） | 不动 |
| RTL | 必须把帧改成 64 BCK/帧（§四） | 音频路径零改动 |
| 音量 | 只能用 FPGA 数字音量（引擎已有 `GAIN_UP/SHIFT`） | 可用 DAC 内部音量（Reg 0x3D/0x3E），模拟域更好 |
| 上电 pop | 无法软静音（XSMT 不可控） | 可用 Reg 0x03 软静音 |
| 主要风险 | 46875 Hz 与 48 kHz 差 −2.3%，在 ±4% 内，但"应该在窗口内"≠"实测过" | 时钟树要手算，且**只能上板验证** |
| 工作量 | 改板 + 改帧格式 + 重测 | 约 100 行（复用现成 `i2c_master.v`，见 6.1）+ 上板调参 |

**推荐 B。** 理由：
1. 板子不改，AUX 就能工作，最快拿到可用状态；
2. 顺带解决 R2（写 Reg40）和 R6（Reg 0x03 软静音），A 方案解决不了这两个；
3. A 方案虽然"零 RTL"，但实际上因为字长问题**仍然要改 RTL**，省不掉。

### 6.1 关键：`engine/src/i2c_master.v` 可以直接复用，不用重写

之前判定它"能力不够"是指**通用 EEPROM 场景**（读 1–4 字节、写 0–2 字节、行 123 的长度限制）。
但 PCM5122 需要的两种事务它**恰好都支持**：

| 需求 | `i2c_master.v` 是否支持 |
|---|---|
| 写 1 字节数据：`START, dev|W, reg, data, STOP` | ✅ 写 0–2 字节范围内 |
| 寄存器回读：`START, dev|W, reg, RSTART, dev|R, 1 字节, NACK, STOP` | ✅ 读 1–4 字节范围内 |
| 时钟拉伸容忍（`scl_in`） | ✅ 有 |
| 总线忙/拉伸超时 | ✅ `STRETCH_TIMEOUT` |
| 开漏输出 + 外部上拉 | ✅ R33/R34/R60/R61 已在板上 |

⇒ 方案 B 的实际工作量**不是"重写一个 I²C 主机"，而是"写一个初始化 FSM + 例化现成的主机"**，约 80–100 行，加两条 cst。
它现在没人例化的原因只是"产品里没有非易失存储需求"，不是"它不能用"。

---

## 七 若走 B：寄存器序列（已按本板实际时钟算出）

### 7.1 输入条件
```
BCK = 27 MHz / 18      = 1,500,000 Hz
fs  = BCK / 32         = 46,875 Hz
BCK/fs                 = 32
```

### 7.2 PLL 计算
手册 Table 131 中 `fS=48k / RSCK=32` 那一行是：`VCO=98.304 MHz, P=1, M=64(K=32,R=2), PLL fS=2048, DSP fS=1024, NMAC=2, NDAC=16, DOSR=8, NCP=4`。
该行 **BCK/fs 也是 32**，所以整套比例可直接等比缩放到我们的 fs：

```
PLLCK = 2048 × 46875        = 96.000 MHz
      = BCK × R × J.D / P   = 1.5 MHz × 2 × 32 / 1  ✓ 吻合
DSP 时钟 = 1024 fs = 48.0 MHz → NMAC = 96/48 = 2
DAC 时钟 =  128 fs =  6.0 MHz → NDAC = 96/6  = 16
OSR 时钟 =  256 fs = 12.0 MHz → DOSR = 96/12 = 8
NCP 时钟 = PLLCK/4 = 24.0 MHz → NCP = 4
```

### 7.3 写入表（Page 0）

| 顺序 | 寄存器 | 值 | 含义 |
|---|---|---|---|
| 1 | `0x00` | `0x00` | 选 Page 0 |
| 2 | `0x25` | **`0x1A`** | b1 DCAS=1 关自动配置；b3 IDCH=1 忽略 SCK 停振；b4 IDSK=1 忽略 SCK 比值 |
| 3 | `0x0D` | **`0x10`** | SREF=001，PLL 基准改为 **BCK** |
| 4 | `0x14` | `0x00` | P = 1 |
| 5 | `0x15` | `0x20` | J = 32 |
| 6 | `0x16` | `0x00` | D 高位 = 0 |
| 7 | `0x17` | `0x00` | D 低位 = 0 |
| 8 | `0x18` | `0x01` | R = 2（写入 R−1） |
| 9 | `0x1B` | `0x01` | DSP 分频 ÷2 |
| 10 | `0x1C` | `0x0F` | DAC 分频 ÷16 |
| 11 | `0x1D` | `0x03` | NCP 分频 ÷4 |
| 12 | `0x1E` | `0x07` | OSR 分频 ÷8 |
| 13 | `0x28` | **`0x00`** | I2S + **16 bit**（对齐我们的帧） |
| 14 | `0x04` | `0x01` | PLLE = 1（默认已是 1，显式再写一次） |
| 15 | — | 轮询 `0x04` b4 PLCK | 读到 0 表示 PLL 已锁定 |
| 16 | `0x02` | `0x00` | 退出 standby（默认已是 0） |
| 17 | `0x03` | `0x00` | 解除左右声道软静音 |

**顺序不能乱**：第 2 步必须先做，否则在改 SREF 的过程中 SCK-halt 检测就会把芯片打进 standby。

### 7.4 时序参数
- I²C 速率：27 MHz / 135 ≈ 200 kHz（PCM5122 支持到 400 kHz）
- 每字节 9 个 SCL（8 数据 + ACK），每笔写 = START + 0x98 + reg + data + STOP
- 上电到第一次写之间留 ≥ 10 ms

---

## 八 上板验证清单（按顺序，每步都有明确判据）

| # | 步骤 | 通过判据 | 失败说明什么 |
|---|---|---|---|
| 1 | 万用表量 `U12.17 ↔ GND`、`U12.18 ↔ DAC_3V3`、`U12.20 ↔ GND` | 均导通 | 若不符，本报告的 R1/R3 前提推翻，须重做 §二 |
| 2 | 量 `J6.10 ↔ U12.11`、`J6.11 ↔ U12.12` | 导通（经 U14） | I²C 物理链断 |
| 3 | 上电，量 DAC_3V3 = 3.3 V、3V3_PERIPH = 3.3 V | 都在 3.1–3.46 V | 电源链问题 |
| 4 | 示波器看 `J5.7/8/11` | BCK 1.5 MHz 方波、LRCK 46875 Hz、DIN 有数据 | FPGA 侧没出流 |
| 5 | I²C 写完，读 `0x04` | b4 PLCK = 0（已锁） | PLL 参数不对，回到 §7.2 重算 |
| 6 | 读 `0x28`、`0x0D`、`0x25` 回读 | 与写入值一致 | I²C 写没落地 |
| 7 | 插 AUX 线，放测试音 | 有声 | 若 5/6 都过还无声，查 §五 模拟链 |
| 8 | 拔掉 J10 外设模块再测 | 仍出声 | 若不出声，说明 3V3_PERIPH 依赖外设，需改电源 |

---

## 九 本报告能证明 / 不能证明

**能证明（有文件级证据）**
- U12 的 28 个引脚各接什么网络（PCB 网表 + 原理图截图双向确认）
- MODE1=GND、MODE2=DAC_3V3 ⇒ I²C 软件模式
- SCK 接地；ADR1=ADR2=GND ⇒ 地址 0x4C
- I²C 从 FPGA 25/26 经 U14 到 U12 的完整通路
- 产品 RTL 中不存在 I²C 主机
- I²S 是 32 BCK/帧、16 bit、46875 Hz
- AUX 模拟链路是 100Ω+1nF 到三极 TRS，且电荷泵使隔直电容不必要
- 板上**没有** EEPROM（全板搜 `24LC`/`EEPROM`/`AT24` 零命中）—— 之前的"非易失存储"需求在硬件上没有落点

**不能证明（需要上板或改版）**
- 96 MHz VCO 在本颗芯片上能否稳定锁定（手册表给的是 98.304 MHz，我们是等比缩放）
- 46875 Hz 是否能通过芯片的 FS 检测（距 48 kHz −2.3%，在 ±4% 内，但未实测）
- U14 的确切型号与使能条件（BOM 该字段为空，只能从网表推断是双向电平转换）
- J12 插拔的 ESD 耐受（原理图自注"ESD protection not frozen"）
- 32 BCK/16 bit 帧在 24 bit 默认下芯片到底怎么处理（R2 只能靠 Reg40 规避，不能靠"应该没事"）

---

## 十 实施记录（方案 B 已落地）

2026-10-25 按方案 B 实施，产出码流 `build_aux_20261025b`（详见该目录 `PROGRAM-LOG.md`）。

### 10.1 改动面

| 文件 | 改动 |
|---|---|
| `engine/src/pcm5122_init.v` | **新增**。I²C 初始化 FSM + 17 条 ROM，复用现成 `i2c_master.v` |
| `engine/src/tdm_ship_owned.v` | 加 `PCM5122_INIT`（默认 1）、`PA_EN_LEVEL`（默认 1）两个参数；加 `i2c_sda`/`i2c_scl` 两个 inout 端口 |
| `engine/src/tdm_top_owned.v` | `assign pa_en = 1'b1` → `(PA_EN_LEVEL != 0)`，默认值不变 |
| `constraints/tdm_ship_owned.cst` | 新增 `i2c_sda`=25、`i2c_scl`=26 |

音频路径（`i2s_tx` / `audio_clk_en` / `tdm_engine_rh`）**一个字节没动**。

### 10.2 时序实测：没有引入新瓶颈

| 码流 | Setup 最差 | Hold 最差 | 负 slack | 周期 |
|---|---|---|---|---|
| 基线 `build_ship_20261025` | +12.045 ns | +0.205 ns | 0 / 25 | 37.037 ns |
| 本版 `build_aux_20261025b` | **+10.652 ns** | **+0.205 ns** | 0 / 25 | 37.037 ns |

- Setup 掉 1.393 ns，仍有 **71% 周期余量**
- Hold **一分没少**
- 最差 hold 路径两版同一族：`u_top/u_tdm/sl2_*_s0/Q → u_top/u_tdm/phase_mem/ADA[*]`（寄存器直驱 BSRAM 地址），**与新逻辑无关**

**为什么 I²C 对时序几乎免疫**：100 kHz 下每位有 270 个 clk 的余量。任何一条 I²C 路径哪怕跑到 20 ns，
也远小于 2.7 µs 的位周期 —— 这与音频路径"每拍都必须满足"性质完全不同。
所以即使 PnR 把 I²C 逻辑摆到最差位置，功能也不会失效；它唯一能造成的影响是把别人的路径挤走，
而实测没有发生。

### 10.3 资源

| 项 | 基线 | 本版 | 增量 |
|---|---|---|---|
| LUT/ALU | 12141 | 12403 | +262 |
| Register | 4302 (28%) | 4421 (29%) | +119 |
| CLS | 8298 (81%) | 8361 (81%) | +63 |
| BSRAM | 15/46 (33%) | 15/46 (33%) | 0 |
| I/O | 30/66 | 32/66 | +2 |

ROM 落在 LUT 里（`ROM16` 仍为 0），没吃 BSRAM。

### 10.4 引脚零回归

逐脚比对 `board.pin.html`：既有 **30 个外部端口一个没动**，只新增 25/26 两个。

### 10.5 序列已做独立反算校验

用脚本从 `pcm5122_init.v` 抓 ROM，按 SLAS763C 语义解码后反算时钟树：
`PLLCK = 96.000 MHz = 2048 fs`，P/J/R/DSP/DACCK/NCP/DOSR/PLL_fS **八项与手册 Table 131 的
`48k / 32fs` 行逐项一致**；SREF/DCAS/IDCH/IDSK/ALEN 五个关键位全部 PASS。

**仍未验证**：本机无 iverilog/ModelSim，`pcm5122_init.v` 没有跑过功能仿真，
只有代码复核 + ROM 反算。PLL 是否真锁、46875 Hz 是否被接受，只能上板读 `Reg0x04 b4`。

### 10.6 码流身份

| 项 | 值 |
|---|---|
| 目录 | `fpga/current/build_aux_20261025b/`（按 `.gitignore` 的 `build_*/` 约定不入库） |
| 文件 | `impl/pnr/board.fs` 7,264,154 B |
| SHA256 | `c410accd7999624c6042e2be2579e1092af7997cfb3b5174ea9492ffc6172625` |
| UserCode | `0x0000C09B` |
| 构建 | `python build_product.py build_aux_20261025b full 1 tdm_ship_owned`，179.86 s |

同目录 `PROGRAM-LOG.md` 记录了烧录步骤与能证明/不能证明的边界（本地保留，不入库）。
寄存器序列可随时用 `project/reviews/20261025-pcm5122-aux/verify_regs.py` 复检。

---

## 附录：网表解析方法（可复用）

```
.esch2  →  WIRE 记录为空壳，几何被剥离，原理图侧做不出连通性
         →  只能取符号脚号↔脚名（PIN + ATTR 'Pin Number'/'Pin Name'）
.epcb2  →  PAD_NET 记录 id = ["PAD_NET", <component-uuid>, <pad>, <padid>]
            payload = {"padNet": "..."}
         →  COMPONENT + ATTR(Designator) 把 component-uuid 翻成位号
         →  得到 全板 (位号, 焊盘) → 网络
```
本报告所有网络结论均来自 `.epcb2`，`.esch2` 只用来取符号引脚名与设计注记。
