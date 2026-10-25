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
| **R4** | `pa_en` 硬接 1（`tdm_top_owned.v:1405`） | 载板上板载 MAX98357 与 AUX **同时出声** | ✅ 已改：`PA_EN_MODE=2` 自动门控（§10.7） |
| **R5** | I²S 三线无串阻，且 DAC 与 FPGA 是两个独立电源域 | 先给 FPGA 上电时，电流经 U12 输入保护二极管倒灌 | 三根线各加 22–33 Ω 串阻 |
| **R6** | XSMT 只靠 R40(100k) 上拉到 3V3，FPGA 不可控 | 上电 pop，且无法软静音 | 引一根 GPIO 到 XSMT，或明确接受 pop |
| **R7** | J12 是外部插孔，ESD 未定型（原理图自注） | 静电直击 U12 输出 | 加 ESD 器件 |

**一句话**：AUX 现在**一定不出声**，卡在数字侧（R1 + R3），不是模拟链路。
模拟链路本身**是对的**（§五），不需要改。

**闭环状态（2026-10-25）**：

| 风险 | 状态 |
|---|---|
| R1 / R3 | ✅ RTL 侧已解决（方案 B，码流 `build_aux_20261025d`），**待上板实测确认** |
| R2 | ✅ 已解决（`Reg0x28 = 0x00` ⇒ I²S + 16 bit） |
| R4 | ✅ 已解决（`PA_EN_MODE=2` 自动门控，见 §10.7） |
| R5 / R6 / R7 | ❌ **硬件整改，未做**（板子未投，现在改最便宜） |


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

> **先澄清一个容易误解的点：这一节的 "PLL" 是 PCM5122 芯片【内部】的音频 PLL，
> 不是 FPGA 的 PLL。**
> 本方案**不碰 FPGA 的任何时钟资源**：没有例化 rPLL/CLKDIV/DCS/CLKSEL，
> 全部逻辑仍在既有 27 MHz 单时钟域，SDC 仍只有一条 `create_clock`。
> 构建报告可自证：`PRIMARY 1/8`、`LW 5/8`、`GCLK_PIN 1/5`，与基线码流逐项相同。
> 那个 96 MHz 只存在于 U12 晶片内部，不出现在板子的任何一根线上；
> FPGA 只是用 I²C 写寄存器"告诉"它怎么从 BCK 倍频。FPGA 侧新增的动作仅是
> 用两根 GPIO 以 100 kHz bit-bang 出 I²C 波形 —— 100 kHz 是数据速率，不是时钟域。

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
- 板上**有** EEPROM：**U10 = 24LC256-I/SN**（32 KB，地址 `0x50`，LCSC `C411625`），见 §十一（**此条 2026-10-25 修正，原先误判为"没有 EEPROM"**）

**不能证明（需要上板或改版）**
- 96 MHz VCO 在本颗芯片上能否稳定锁定（手册表给的是 98.304 MHz，我们是等比缩放）
- 46875 Hz 是否能通过芯片的 FS 检测（距 48 kHz −2.3%，在 ±4% 内，但未实测）
- J12 插拔的 ESD 耐受（原理图自注"ESD protection not frozen"）
- 32 BCK/16 bit 帧在 24 bit 默认下芯片到底怎么处理（R2 只能靠 Reg40 规避，不能靠"应该没事"）
- `TCA9517` 在 `VccB = 0`（载板未供电）时是否会把 A 侧总线拉低 —— 见 §11.3 R8，**只能查手册或实测，不能靠推断**

---

## 十 实施记录（方案 B 已落地）

2026-10-25 按方案 B 实施，最终产出码流 `build_aux_20261025d`。
中间版 `build_aux_20261025c`（用常量 `PA_EN_LEVEL` 控功放）已被 d 版取代并删除，
其数据在下表保留为对照。

> 注：`fpga/current/build_*/` 被 `.gitignore` 忽略，构建目录里的 `PROGRAM-LOG.md` **不入库**
> （`git clean` 会一并清掉）。因此**可持久引用的记录以本节为准**，构建目录里的那份只是本地副本。

### 10.1 改动面（最终形态）

| 文件 | 改动 |
|---|---|
| `engine/src/pcm5122_init.v` | **新增**。I²C 初始化 FSM + 17 条 ROM，复用现成 `i2c_master.v` |
| `engine/src/tdm_ship_owned.v` | 加 `PCM5122_INIT`（默认 1）、`PA_EN_MODE`（默认 2）两个参数；加 `i2c_sda`/`i2c_scl` 两个 inout 端口；新增 `pa_en` 门控逻辑 |
| `engine/src/tdm_top_owned.v` | **无改动**。曾加过 `PA_EN_LEVEL`，后已还原为基线原样（`assign pa_en = 1'b1;`） |
| `constraints/tdm_ship_owned.cst` | 新增 `i2c_sda`=25、`i2c_scl`=26 |

音频路径（`i2s_tx` / `audio_clk_en` / `tdm_engine_rh`）**一个字节没动**。

**为什么把 `pa_en` 放在包装层而不是音频核心**：`pa_en` 是板载 MAX98357A 的 SD_MODE（引脚 51），
属于板级适配。放在 `tdm_ship_owned` 里，`tdm_top_owned.v` 才能与基线逐字节一致，
音频核心将来迭代时不会带着这个板级开关一起漂移。


### 10.2 时序实测：没有引入新瓶颈

| 码流 | Setup 最差 | Hold 最差 | 负 slack | 周期 |
|---|---|---|---|---|
| 基线 `build_ship_20261025` | +12.045 ns | +0.205 ns | 0 / 25 | 37.037 ns |
| `build_aux_20261025c`（中间版） | +10.652 ns | +0.205 ns | 0 / 25 | 37.037 ns |
| **`build_aux_20261025d`（最终）** | **+9.571 ns** | **+0.205 ns** | **0 / 25** | 37.037 ns |

- 最终版 Setup 相对基线掉 2.474 ns，仍有 **26% 周期余量**（9.571 / 37.037）
- Hold **一分没少**（三个码流都是 +0.205 ns）
- 最差 hold 路径三次构建同一族：`u_top/u_tdm/sl2_*_s0/Q → phase_mem_phase_mem_0_0_s/ADA[*]`
  （寄存器直驱 BSRAM 地址），**与新逻辑无关**
- c→d 只多了 54 个 LUT/ALU，Setup 却掉了 1.081 ns，跌幅不成比例 ⇒ 是 PnR 重新布局的抖动
  （最差 setup 路径落在 `u_top/u_nm/load_amp_*/D`，即 note_map 内部，不在新增逻辑上），
  不是逻辑深度增加导致

**为什么 I²C 对时序几乎免疫**：100 kHz 下每位有 270 个 clk 的余量。任何一条 I²C 路径哪怕跑到 20 ns，
也远小于 2.7 µs 的位周期 —— 这与音频路径"每拍都必须满足"性质完全不同。
所以即使 PnR 把 I²C 逻辑摆到最差位置，功能也不会失效；它唯一能造成的影响是把别人的路径挤走，
而实测没有发生（hold 完全未变，setup 跌幅可由布局抖动解释且余量充足）。


### 10.3 资源

| 项 | 基线 | c 版 | **d 版（最终）** | d 相对基线 |
|---|---|---|---|---|
| Logic | 12549 (61%) | 12811 (62%) | **12865/20736 (63%)** | +316 |
| LUT/ALU | 12141 | 12403 | **12457**（8893 LUT + 3564 ALU） | +316 |
| Register | 4302 (28%) | 4421 (29%) | **4424 (29%)** | +122 |
| CLS | 8298 (81%) | 8361 (81%) | **8349 (81%)** | +51 |
| BSRAM | 15/46 (33%) | 15/46 (33%) | **15/46 (33%)** | 0 |
| DSP | 10/24 (42%) | 10/24 | **10/24 (42%)** | 0 |
| I/O | 30/66 | 32/66 | **32/66 (49%)** | +2 |

ROM 落在 LUT 里（`ROM16` 仍为 0），没吃 BSRAM。

**时钟资源零变化**（构建报告 §5/§6 逐项对比，三个码流相同）：

| 项 | 基线 | c 版 | d 版 |
|---|---|---|---|
| PRIMARY | 1/8 | 1/8 | **1/8** |
| LW | 5/8 | 5/8 | **5/8** |
| GCLK_PIN | 1/5 | 1/5 | **1/5** |
| PLL / rPLL | 0（表中无此行） | 0 | **0** |

全局时钟清单里 `clk_d → PRIMARY` 唯一，其余 5 条 LW 全是基线就有的使能类网络。
**本模块没有例化任何 rPLL / CLKDIV / DCS / CLKSEL。**

> 易误判：`board.rpt.txt` 里 `clk` 的站点写作 `IOL7[A]/LPLL1_T_in`、`pa_en` 写作 `IOR45[A]/RPLL2_T_in`。
> `LPLL1_T_in`/`RPLL2_T_in` 是**引脚可复用站点的命名**，不是 PLL 被占用。
> 判据只看 §5 `Clock Resource Usage Summary` 与资源表有没有 PLL 行 —— 两处都没有。


### 10.4 引脚零回归

逐脚比对 `board.pin.html`：既有 **30 个外部端口一个没动**，只新增 25/26 两个。

### 10.5 序列已做独立反算校验

用脚本从 `pcm5122_init.v` 抓 ROM，按 SLAS763C 语义解码后反算时钟树：
`PLLCK = 96.000 MHz = 2048 fs`，P/J/R/DSP/DACCK/NCP/DOSR/PLL_fS **八项与手册 Table 131 的
`48k / 32fs` 行逐项一致**；SREF/DCAS/IDCH/IDSK/ALEN 五个关键位全部 PASS。

**仍未验证**：本机无 iverilog/ModelSim，`pcm5122_init.v` 没有跑过功能仿真，
只有代码复核 + ROM 反算。PLL 是否真锁、46875 Hz 是否被接受，只能上板读 `Reg0x04 b4`。

### 10.6 码流身份（最终版）

| 项 | 值 |
|---|---|
| 目录 | `fpga/current/build_aux_20261025d/`（按 `.gitignore` 的 `build_*/` 约定不入库） |
| 文件 | `impl/pnr/board.fs` 7,264,154 B |
| SHA256 | `abaec66ea7a8a3e5b650f4b3128bdf103c1935de92485a00d119e76a1df903ff` |
| 码流头 | `//CheckSum: 0x58C8`、`//UserCode: 0x000058C8`、`//Device-package: GW2AR-18C-QFN88`、`//SecurityBit: ON` |
| 构建 | `python build_product.py build_aux_20261025d full 1 tdm_ship_owned`，184.81 s |

注：本工程 `UserCode` 与 `CheckSum` 恒等（基线 `0x000019D6`、c 版 `0x0000C09B`、d 版 `0x000058C8` 都如此），
所以"读回 UserCode 一致"等价于"校验码流本体正确装入"。
`SecurityBit: ON` 三个码流都有，是工程级设置，不是本次引入。

寄存器序列可随时用 `project/reviews/20261025-pcm5122-aux/verify_regs.py` 复检。

### 10.7 功放使能自动门控（`PA_EN_MODE`）

**要解决的问题**：载板把同一组 `I2S_BCK/DIN/LRCK` 从 J5 分给 PCM5122，
而 **J5.9（PA_EN）在载板上是 NC** —— 载板关不掉板载 MAX98357A。
不处理的话插上载板就是「板载喇叭 + AUX」两个声源同时响。

**中间版的做法有设计债**：c 版用常量 `PA_EN_LEVEL=1`，要求"插载板时记得改成 0"。
靠人记着改参数，一定会忘。而且它把板级开关塞进了音频核心 `tdm_top_owned.v`。

**最终做法**：`PA_EN_MODE`（0/1/**2=自动，默认**），逻辑放回包装层：

```verilog
assign pa_en = (PA_EN_MODE == 2) ? (pa_en_core & ~pcm_locked)
             : (PA_EN_MODE != 0);
```

`pcm_locked` 来自 PCM5122 的 `Reg0x04 b4 PLCK` 回读。三条路径互斥且完备：

| 场景 | `pcm_locked` | `pa_en` | 结果 |
|---|---|---|---|
| 裸 Nano（无 I²C 从机，全部 NACK） | 0 | 1 | 板载喇叭出声，**与改动前完全一致** |
| 载板在位 + 配置成功 | 1 | 0 | 板载喇叭静音，AUX 独占 |
| 载板在位 + 配置失败 | 0 | 1 | 退回板载喇叭 |

设计意图：自动判定失败时**降级到已知可用的状态**，而不是降级到静音 ——
不存在"配错了导致整机没声"的死路。

### 10.8 烧录记录（SRAM）

```
programmer_cli.exe -d GW2AR-18C -r 2 \
  --fsFile "D:\FPGA-Project\authoritative-20261024\fpga\current\build_aux_20261025d\impl\pnr\board.fs"
```

| 项 | 结果 |
|---|---|
| Target Device | GW2AR-18C (0x0000081B) |
| Operation | SRAM Program |
| Programming | 100% |
| **User Code 读回** | **0x000058C8** ✅ 与码流头一致 |
| Status Code | `0x00006020`（预期，见下） |
| 耗时 | 5.84 s |

**`Status Code 0x00006020` 不是失败。** 成因是构建时 `-use_sspi_as_gpio 1`：
本产品把 I²S 三线放在引脚 54/55/56，与 MSPI 复用，MSPI 被当 GPIO 用，
SRAM 模式下回读校验通路走不通，必然报这个码。**判据看 User Code 读回值，不看状态码。**

`-r 2` 写 SRAM，**断电即丢**；`-r 9` 才写外部 flash（Erase + Program + **Verify 真校验**）。
当前外部 flash 里**仍是旧的静音版 `0x000039A6`**，尚未覆盖。


---

## 十一 更正：板上**有** EEPROM（2026-10-25 补）

### 11.1 原先的结论是错的

本报告 §九 原写「板上**没有** EEPROM（全板搜 `24LC`/`EEPROM`/`AT24` 零命中）」。
**这条是错的，已改。**

错因：我只搜了 `04_PCM5122_AUX.esch2` 这一张图纸，而 EEPROM 在**另一张图纸**
`02_Shift_and_memory.esch2` 上。一张图纸搜不到就下了"全板没有"的结论 —— 搜索范围与结论范围不匹配。

实际上 `24LC256` 一直在这两个地方写着：

| 位置 | 内容 |
|---|---|
| `native/sch/Schematic1/02_Shift_and_memory.esch2` | 器件 `24LC256-I/SN`、注记「256K I²C串行EEPROM」 |
| `context/purchase-preparation-20261021-r1/jlc-bom-current-DRAFT-NOT-FOR-ORDER.csv` | `24LC256-I/SN,U10,SOIC-8,C411625` |
| `context/purchase-preparation-20261021-r1/jlc-bom-217-DRAFT-NOT-FOR-ORDER.csv` | 同上 |

另外 `project/reviews/20261025-eeprom-test/REPORT.md` §4.1 早已确认过型号与地址。
所以这不是新发现，是**我漏查**。

> 那份报告里有一句「手上只有裸 Nano 20K，**没有 24LC256**」，指的是
> **实物还没有**（载板未投产），不是**设计上没有**。两件事别混。

### 11.2 U10 引脚级连接（网表实测）

| U10 脚 | 24LC256 定义 | 实际网络 |
|---|---|---|
| 1 | A0 | **GND** |
| 2 | A1 | **GND** |
| 3 | A2 | **GND** |
| 4 | VSS | GND |
| 5 | SDA | `I2C_SDA` |
| 6 | SCL | `I2C_SCL` |
| 7 | WP | **GND** ⇒ 写保护关闭，**可写** |
| 8 | VCC | **3V3_IO**（Nano 供电，不是载板 LDO） |

⇒ 7 位地址 **`0x50`**（写 `0xA0`），32 KB，页 64 B，写周期 5 ms。

**U10 的供电是 `3V3_IO`，来自 J5.16（Nano）**，所以只要 Nano 插着 USB，
即使载板 J13 没供电，EEPROM 也是活的 —— 这对"标定数据存哪"是个可用的落点。

### 11.3 I²C 总线拓扑：两个器件、一条总线、中间一个缓冲器

```
FPGA 25/26 ──┬── R33/R34 4.7k ↑3V3_IO
             ├── U10  24LC256      @ 0x50   ← 3V3_IO 侧（Nano 供电）
             └── U14  TCA9517DGKR  ──┬── R60/R61 ↑3V3_PERIPH
                                      ├── U12  PCM5122  @ 0x4C   ← 3V3_PERIPH/DAC 侧
                                      └── J10.8（外接模块）
```

U14 = **TCA9517DGKR**（I²C 双向缓冲/电平转换）。引脚：1=VccA(`3V3_IO`)、
2/3=A 侧 SCL/SDA、4=GND、5/8=VccB(`3V3_PERIPH`)、6/7=B 侧 SDA/SCL。

### 11.4 对我们这套 RTL 的影响

| 问题 | 结论 |
|---|---|
| 地址冲突？ | **没有**。EEPROM 在 `0x50`，PCM5122 在 `0x4C`，`pcm5122_init.v` 只发 `0x4C`，碰不到 EEPROM |
| 总线上多了个器件，初始化会误写 EEPROM 吗？ | **不会**。I²C 从机只响应自己的地址，`0x4C` 的写不会落到 `0x50` |
| 100 kHz 会不会太快？ | 不会。EEPROM 支持 400 kHz，TCA9517 支持 400 kHz 以上，4.7 kΩ 上拉在 100 kHz 下余量充足 |
| 上拉会不会重复？ | 两侧各有 4.7 kΩ，被 TCA9517 隔开，**不是并联**，各自独立，没问题 |
| 能不能用 EEPROM 存标定/预设？ | **可以**，32 KB 可写。注意页 64 B、跨页要拆、每次写后等 5 ms |

### 11.5 新风险 R8：TCA9517 在 VccB 掉电时的行为

**这是本次核对顺带发现的，之前没人提。**

| 项 | 情况 |
|---|---|
| 现象 | `VccA = 3V3_IO` 由 Nano 供；`VccB = 3V3_PERIPH` 由载板 LDO 供。**两个域无时序控制** |
| 场景 | 只插 Nano USB、J13 未接 ⇒ `VccA = 3.3 V`、`VccB = 0 V` |
| 担心 | TCA9517 这类带偏移的 I²C 缓冲器，在**单侧掉电**时可能把另一侧总线钳在低电平（业界多款同类器件有此已知行为） |
| 若成立 | 此时 **EEPROM 也读不到**（EEPROM 本身是活的，但总线被钳住） |
| 影响面 | 只影响"仅 Nano 供电"这个调试场景，不影响载板正常供电后的使用 |
| 处置 | **必须查 TCA9517 数据手册的 Power-Up/Power-Down 章节确认**，不能靠推断。若确实会钳低，则调试 EEPROM 必须同时给 J13 供电 |

**没有实测就不能下结论**，所以这里只登记为待核实项，不写成结论。

---

## 附录：网表解析方法（可复用）

```
.esch2  →  WIRE 记录为空壳，几何被剥离，原理图侧做不出连通性
         →  只能取符号脚号↔脚名（PIN + ATTR 'Pin Number'/'Pin Name'）
         →  也只适合取设计注记（TEXT 记录）
.epcb2  →  PAD_NET 记录 id = ["PAD_NET", <component-uuid>, <pad>, <padid>]
            payload = {"padNet": "..."}
         →  ATTR(key='Designator', parentId=<component-uuid>) 翻位号
         →  得到 全板 (位号, 焊盘) → 网络
```

本报告所有网络结论均来自 `.epcb2`，`.esch2` 只用来取符号引脚名与设计注记。

**已封装成工具**：`netlist_query.py`（同目录）

```bash
python netlist_query.py stats          # 227 器件 / 1038 焊盘 / 256 网络
python netlist_query.py part U12       # 某器件全部焊盘
python netlist_query.py net I2S_BCK    # 某网络全部焊盘
python netlist_query.py grep DAC       # 模糊查网络名
```

### 附录 A 解析 `.epcb2` 的四个坑（都踩过）

1. **不能用 `.esch2` 做连通性**：`WIRE` 记录是空壳（`{"type":"WIRE","id":"..."}|||`），
   几何被剥离，取不到端点坐标。
2. **位号不在 `COMPONENT` 里**：`COMPONENT.attrs` 只有
   `Reuse Block / Group ID / Channel ID / Unique ID / DeviceName`，**没有 Designator**。
   位号在独立的 `ATTR` 记录里，`key="Designator"`。
3. **`ATTR` 必须过滤 `parentId`**：`parentId` 为空的是**库符号定义**，
   `value` 形如 `U?` / `C?`，是模板不是实例。不过滤会把 286 条算进来（实际实例 227 个）。
4. **记录有双重编码**：部分 `payload` 本身是一个 JSON 字符串，
   一次 `json.loads` 得到的是 `str` 而不是 `dict`，要再解一次。
   （这一条是 `U10` 那次才暴露出来的：`attrs` 有时是字符串，直接 `p["attrs"]["DeviceName"]`
   会报 `TypeError: string indices must be integers`。）

### 附录 B 一条方法论教训

§九 原来那条「全板没有 EEPROM」的错误，本质不是解析技术问题，是**搜索范围 ≠ 结论范围**：
只在 1 张图纸里搜，却下了"全板"的结论。载板有 4 张图纸，器件分散在
`01_…` / `02_Shift_and_memory` / `03_…` / `04_PCM5122_AUX` 里。

**以后凡是要下"全板有没有 X"的结论，必须走 `.epcb2` 的器件清单**
（`netlist_query.py` 可扩展一个 `parts` 子命令列出全部 227 个位号+型号），
而不是在某一张原理图里 grep。

