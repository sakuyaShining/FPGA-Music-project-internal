# Tang Nano 20K 硬件资料与引脚约束核查

> 2026-10-01 · **把"上板会不会出意外"从"未知"变成"已知且已处理"。**

## 一、为什么必须做这件事

综合报告里发现：**未约束的端口被自动分配到了 1.8 V bank 和全局时钟脚**：

```
（修复前）
ev_valid    | in | IOT4[A]  | -       | LVCMOS18   ← 1.8V
ev_note[0]  | in | IOT30[A] | GCLKT_1 | LVCMOS18   ← 全局时钟脚
ev_note[2]  | in | IOT27[A] | GCLKT_0 | LVCMOS18   ← 全局时钟脚
ev_vel[4]   | in | IOB30[B] | GCLKC_4 | LVCMOS18   ← 时钟脚
```

**板上的 40-pin 排针是 3.3 V** ✗ —— 把 3.3 V 信号驱入 1.8 V bank 的脚**可能损坏 FPGA** ✗

---

## 二、引脚表（每一条都有官方来源，没有一条是猜的）

来源：[sipeed/TangNano-20K-example](https://github.com/sipeed/TangNano-20K-example) 的官方 `.cst`

| 信号 | 引脚 | 电平 | 官方来源 |
|---|---|---|---|
| `clk`（27 MHz 晶振） | **4** | 3.3 V | `audio/src/audio.cst` |
| `rst_n`（按键 S1） | **87** | 3.3 V | `audio/src/audio.cst` |
| 按键 S2 | 88 | 3.3 V | `uart/src/top.cst` |
| **LED ×6** | **15,16,17,18,19,20** | 3.3 V | `led/blink_leds/src/*.cst` |
| I2S `PA_EN/DIN/WS/BCK` | **51 / 54 / 55 / 56** | 3.3 V | `audio/src/audio.cst` |
| **UART `rx / tx`** | **70 / 69** | 3.3 V | `uart/src/top.cst` |
| **40-pin 排针** | **27–42, 48, 77** | **3.3 V** | `rgb_lcd/.../tang_nano_20K_LCD.cst` |

**修正的两处历史错误：**
1. LED 索引**整体错位一位**且**少了第 6 个** ✗（旧：`led[0..4]=19,18,17,16,15`；正确：`led[0..5]=15..20`）
2. **UART 引脚此前一直未分配** ✗（现在记录在 `tdm_top.cst` 里，等参数接口建好即可启用）

**★ 一个来之不易的发现**：LED/按键都在 **bank 3/6**，而排针在 **bank 4/5** ✗ ——
**旧 `tangnano20k.cst` 把 5 个 LED 全按官方写对了** ✓ 但排针引脚此前从没查过 ✗

---

## 三、修复后的综合报告

```
端口          引脚     约束  电平        电压
clk           4/7      Y    LVCMOS33    3.3  ✓
rst_n         87/3     Y    LVCMOS33    3.3  ✓
ev_valid      38/4     Y    LVCMOS33    3.3  ✓
ev_on         39/4     Y    LVCMOS33    3.3  ✓
ev_note[6:0]  27..33   Y    LVCMOS33    3.3  ✓
ev_vel[3:0]   34..37   Y    LVCMOS33    3.3  ✓
preset[1:0]   40,41    Y    LVCMOS33    3.3  ✓
test_mode     42/4     Y    LVCMOS33    3.3  ✓
led[5:0]      15..20   Y    LVCMOS33    3.3  ✓
dac_din/ws/bck 54,55,56 Y    LVCMOS33    3.3  ✓
pa_en         51/3     Y    LVCMOS33    3.3  ✓
```

**所有具名端口都在 3.3 V bank，零个落进 1.8 V** ✓
（grep 到的 `LVCMOS18` 行端口名为 `-`，是未使用的空闲引脚，不是本设计的信号）

**时序：**
```
Setup 违例端点 0    Hold 违例端点 0    TNS 0
clk: 周期 37.037 ns / 约束 27.000 MHz
```

**资源：** Logic **4093/20736（20%）**、Register 719（5%）、BSRAM 8/46（18%）、DSP 3.25/24（14%）

---

## 四、为了塞进排针做的一处 RTL 调整

`tdm_top` 的交互端口原本需要 20 根线，排针只有 18 根 ✗

**改法：`ev_vel` 由 8 位降为 4 位**（16 级力度）✓ 内部左移 4 位补齐 ✓
**好处**：`note_map` 与所有测试台保持 8 位不变，**改动面最小** ✓

---

## 五、板卡完整参数（Sipeed 官方 wiki）

| 项 | 值 |
|---|---|
| FPGA | **GW2AR-LV18QN88C8/I7** |
| LUT4 / FF | 20736 / 15552 |
| BSRAM | 828 Kbit / **46 块**（每块 18 Kbit） |
| **乘法器 18×18** | **48 个** ⚠️ 项目显示"DSP 24" —— **每个 DSP 块含 2 个乘法器**，报告口径要写清 |
| PLL | 2 |
| **I/O Bank** | **8 个** |
| 单色 LED | **6 个**（共阳极，低电平点亮） |
| RGB LED | 1（WS2812） |
| 用户按键 | 2 |
| 时钟 | 27 MHz 晶振 **+ MS5351（3 路可编程）** |
| 功放 | MAX98357A |
| 调试器 | BL616（JTAG + USB 转串口） |

**关于 MS5351**：理论上能给出 12.288 MHz → 48000 Hz（256×）比现在的 46875 Hz 更标准 ✓
**但它由 BL616 通过串口配置** ✗ → **上电不配置就没有输出** ✗ 对"脱机演示"是风险 ✗
**⇒ 决定：不依赖它** ✓

---

## 六、复现

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\scripts\build_gowin.ps1 `
  -Project src\gowin\tdm_synth\tdm_synth.gprj -SspiAsGpio
# 然后看 src\gowin\tdm_synth\impl\pnr\tdm_synth.rpt.txt
#   搜 "BankVccio"  -> 所有具名端口都应是 3.3
#   搜 "LVCMOS18"   -> 命中的行端口名应为 "-"（空闲引脚）
```

---

## 七、还没做的

| 项 | 状态 |
|---|---|
| `$readmemh` 初始化 BSRAM 是否真生效 | ⚠️ **未验证** —— 这是"烧进去会不会静音"的关键 |
| 板级 bring-up（时钟/复位/LED/DAC 实测） | ❌ 无板子 |
| UART 端口接入 `tdm_top` | ❌ 引脚已备好，等参数接口 |
| 交互层传感器引脚 | ❌ 等交互方案定 |
| 排针剩余可用 | **48、77**（+UART 69/70） |
