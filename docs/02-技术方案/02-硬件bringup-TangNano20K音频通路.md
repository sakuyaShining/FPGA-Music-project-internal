# Tang Nano 20K 音频通路 bring-up 笔记

> **更正注记（2026-10-05）**：本文成文时的采样率决策为 46.875 kHz。工程实现最终采用 **fs = 52734.375 Hz（27 MHz ÷ 512，每样本 512 拍）**，BCK/WS 分频随之改变。下文凡出现 46.875 kHz 之处均属**当时的论证记录**，现行口径以本注记与 `16-板卡bringup一页卡片.md` 为准。

> 来源：Sipeed 官方例程 `github.com/sipeed/TangNano-20K-example` 的 `audio/` 目录
> 板卡：Tang Nano 20K（GW2AR-LV18QN88C8/I7）

---

## 一、板载音频硬件

| 项 | 内容 |
|---|---|
| 功放/DAC | **MAX98357A**（I2S 输入 DAC + D 类功放，单声道） |
| 接口 | 3 线 I2S：`HP_BCK`（位时钟）、`HP_WS`（左右声道）、`HP_DIN`（串行数据） |
| 使能 | `PA_EN`（功放使能，**高电平有效**） |
| 其他 | 27 MHz 板载晶振；MS5351 时钟发生器（可额外产生 3 路时钟）；BL616 作 JTAG + 串口 |

---

## 二、引脚约束（官方例程原文，可直接用作 `audio.cst` 起点）

```c
IO_LOC "PA_EN"  51;
IO_LOC "HP_DIN" 54;
IO_LOC "HP_WS"  55;
IO_LOC "HP_BCK" 56;
IO_LOC "rst"    87;   // 板载 S1 按键
IO_LOC "clk"     4;   // 27MHz 板载晶振

IO_PORT "PA_EN"  IO_TYPE=LVCMOS33 PULL_MODE=UP DRIVE=8;
IO_PORT "HP_DIN" IO_TYPE=LVCMOS33 PULL_MODE=UP DRIVE=8;
IO_PORT "HP_WS"  IO_TYPE=LVCMOS33 PULL_MODE=UP DRIVE=8;
IO_PORT "HP_BCK" IO_TYPE=LVCMOS33 PULL_MODE=UP DRIVE=8;
IO_PORT "rst"    IO_TYPE=LVCMOS33 PULL_MODE=UP;
IO_PORT "clk"    IO_TYPE=LVCMOS33 PULL_MODE=UP;
```

---

## 三、官方 I2S 时序（`audio_drive.v` 实测逻辑）

- 每个采样点占 **32 个 BCK**：`b_cnt` 0→31 循环，前 16 拍左声道、后 16 拍右声道 → **16 bit / 声道**。
- 数据请求：`b_cnt == 0` 与 `b_cnt == 16` 各拉高一次 `req`，即每声道取一个 16 bit 样本。
- 移位：`req_r1 ? idata : (idata_r << 1)`，`HP_DIN_r <= idata_r[15]` → 高位先出（MSB first）。
- `HP_WS`：`b_cnt==3` 时拉**低**（对齐到左声道），`b_cnt==19` 时拉**高**。低电平对应左声道。
  → 数据在 BCK 上升沿更新、WS 早一个 BCK 变化：**标准 I2S（Philips）格式，1 BCK 延迟**。
- `HP_BCK = clk_1p536m`，即 BCK 直接由时钟驱动。

## 四、时钟方案（重要，决定采样率）

官方做法：`27 MHz → rPLL → 6 MHz → CLKDIV÷4 → 1.5 MHz`。

推导：VCO = 27 MHz × 16 = **432 MHz**（在 Gowin rPLL 的 400–1200 MHz 范围内），ODIV=72 → 6 MHz，再 ÷4 → 1.5 MHz。

于是：

```
BCK     = 1.5 MHz
每帧    = 32 × BCK  → fs = 1.5 MHz / 32 = 46.875 kHz
```

**为什么不用标准 48 kHz**：48 kHz 需要 BCK = 48k×32 = 1.536 MHz，而 27 MHz ÷ 1.536 MHz = 17.578125，非整数，rPLL 凑不出精确值（VCO 需落在 400–1200 MHz 且 ODIV 为整数）。

**结论：采用 fs = 46.875 kHz。** 依据：
1. MAX98357A 支持 8–96 kHz 采样率，46.875 kHz 完全在范围内；
2. 音高由**相位增量按实际 fs 计算**（`Δφ = f_note / fs × 2^N`），采样率不是 48k 不会造成音准问题；
3. 46.875 kHz > CD 的 44.1 kHz，无音质顾虑；
4. 时钟干净整数分频，**无抖动**——正好服务赛题「确定性无抖动延迟」的拓展要求。

> 备选（后续再评估）：用板载 **MS5351** 产生精确 1.536 MHz 或 12.288 MHz，可得标准 48 kHz。但需先解决 MS5351 的配置通道（BL616 固件侧或 FPGA 侧 I2C），增加复杂度，不建议在 P1 阶段做。

---

## 五、官方例程文件清单（参考实现）

`audio/audio.gprj` 的 FileList：

| 文件 | 作用 |
|---|---|
| `src/top.v` | 顶层；PLL 27M→6M、CLKDIV÷4、ROM 地址扫描 |
| `src/audio_drive.v` | **I2S 发送器本体**（b_cnt / req / 移位 / WS 生成） |
| `src/rom_wave_sine.v` | 256 点正弦波表 ROM（10 bit 地址 / 16 bit 数据） |
| `src/gowin_rpll/gowin_rpll.v` | Gowin rPLL IP |
| `src/gowin_clkdiv/gowin_clkdiv.v` | Gowin CLKDIV IP |
| `src/audio.cst` | 引脚约束（见上） |

**可直接复用**：`audio_drive.v` 的 I2S 时序可以作为我方 I2S 发送器的参考/基线，但**要改造**：
- 改为**由混音器供给样本**（而非固定 ROM 扫描），带请求/应答或 FIFO 握手；
- 支持**双声道独立数据**（后续做立体声效果）；
- 参数化位宽与采样率，便于切换。

**不要直接照搬的部分**：官方例程是"ROM 循环播放单音"，形式上接近"播放预录音频"。赛题**严禁播放预录 PCM**——我们的样本必须由振荡器实时算出。ROM 只允许用作**波表**（单个振荡器查表，按赛题规则只计 1 个振荡器），绝不能当作成品音频流回放。

---

## 六、P1 阶段第一步验收清单

- [ ] 建立 Gowin 工程，器件选 `GW2AR-LV18QN88C8/I7`，导入上表引脚约束
- [ ] 跑通官方 audio 例程 → 扬声器有正弦声（验证板子与 DAC 通路）
- [ ] 用自写 I2S 发送器 + 自写相位累加器发 440 Hz 正弦 → 示波器/频谱确认频率准确
- [ ] 测出"音符触发 → 音频输出"的实际延迟（示波器双通道：触发信号 vs HP_DIN 模拟输出）
- [ ] 记录资源占用（LUT/FF/BSRAM/DSP），作为 32 复音的容量基线

---

## 七、风险记录

| 项 | 说明 |
|---|---|
| MAX98357A 是单声道 | 板载只有 1 个功放，立体声效果（合唱/混响的宽度感）需外接或接受单声道混音 |
| 音量 | 官方 README 注明 "A bit loud" —— 调试时先降低幅度，避免烧喇叭/扰民 |
| Nano 20K 无 ADC | 若做模拟量力度感应，需外部 ADC（I2C/SPI）或用 RC 充放电时间测量（纯数字法，FPGA 擅长） |
| 无 SDRAM 大缓冲 | 只有 64 Mbit SDRAM；效果器延迟线优先用片内 B-SRAM（828 Kbit） |
