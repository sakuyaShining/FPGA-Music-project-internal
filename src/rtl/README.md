# RTL 源码

本项目自己写的 Verilog 模块。命名：小写下划线，如 `i2s_tx.v`。
约束在 `src/constr/`，Gowin 工程与 IP 核在 `src/gowin/`。

---

## 一、调试显示模块（可复用）

**`lcd_480x272.v` —— 4.3 寸 RGB 屏（480×272）显示驱动，已上板验证。**

以后凡是需要在屏上画东西的场合（看振荡器波形、看频谱、看包络、显示调试数值），
都复用它，不要重写时序。

### 它封装了什么

- 27 MHz → rPLL → 像素时钟（9 MHz）
- PLL 未锁定前把设计保持在复位态
- 行/场时序发生（内部例化 `video_timing.v`）
- RGB 打一拍 + 消隐期强制黑色，并与 DE/HSYNC/VSYNC 严格对齐后送引脚

### 怎么用（客户模块契约只有两条）

```verilog
lcd_480x272 u_lcd (
    .clk_27m (clk_27m), .rst_btn_n (btn_rst_n),
    .pix_clk (pix_clk), .pll_locked (pll_locked),
    .px_x (px_x), .px_y (px_y), .px_de (px_de), .px_frame_tick (frame_tick),
    .px_r (my_r), .px_g (my_g), .px_b (my_b),      // ← 你的颜色，组合逻辑
    .lcd_clk (lcd_clk), .lcd_de (lcd_de),
    .lcd_hsync (lcd_hsync), .lcd_vsync (lcd_vsync),
    .lcd_r (lcd_r), .lcd_g (lcd_g), .lcd_b (lcd_b)
);
```

**契约：**

1.**组合逻辑**：给当前坐标 `(px_x, px_y)`，算出这个像素的颜色 `px_r/g/b`。
2.**不用管消隐**（驱动在 `px_de=0` 时强制输出黑）、**不用管打拍**（驱动负责）。

也就是说你的模块就是一个纯组合函数：

```
(x, y) -> (R[4:0], G[5:0], B[4:0])
```

### 最容易踩的坑

**不要用寄存后的 `de` 去门控组合逻辑算出的颜色。**两者会差 1 拍，有效区边缘错 1 个像素。
驱动已经把打拍收在一处，你只要老老实实写组合逻辑就不会错。
细节见 `video_timing.v` 里 `de_comb` 的注释。

### 参数

行场时序全部可参数化（`H_ACTIVE / H_BP / H_FP / H_SYNC_W / V_*`）。
默认值对应 4.3 寸 480×272 屏，改屏时改参数即可。
改完参数**记得跑 `tools/scripts/check_video_timing.py`**，它会把 DE 宽度、同步位置等
容易差一的地方数一遍。

---

## 二、模块清单

| 文件 | 作用 | 状态 |
|---|---|---|
| `bringup_top.v` | 顶层：显示驱动 + 图片/自检图案 + LED | 上板验证 |
| `lcd_480x272.v` |**可复用显示驱动**（见上节） | 上板验证 |
| `video_timing.v` | 480×272 行场时序发生器 | 上板验证 |
| `image_view.v` | 显示图片（8 色索引 → RGB565，地址预取抵消 BRAM 延迟） | 上板验证 |
| `image_rom.v` | 图片像素 ROM（`$readmemb`，占 24/26 块 BSRAM） | 上板验证 |
| `test_pattern.v` | 自检图案：彩条 + 白边框 + 二进制计数条 + 纯色档 | 上板验证 |
| `led_heartbeat.v` | 6 颗 LED 心跳与二进制计数，跑 27 MHz 直连 | 上板验证 |

IP 核在 `src/gowin/bringup_9k/ip/`：

| 文件 | 作用 |
|---|---|
| `gowin_rpll/gowin_rpll.v` | rPLL：27 MHz → 9 MHz。**文件头部写清了 PLL 参数公式**，改频率前先读它 |

数据文件在 `src/gowin/bringup_9k/`：

| 文件 | 作用 |
|---|---|
| `image_rom.bin` | 图片的 8 色索引数据（131072 行 × 3 bit），由 `tools/scripts/make_image_rom.py` 生成 |

>**改图片必须同时改两处**：`.bin` 数据文件 和 `image_view.v` 里的 `PAL0..PAL7` 调色板。
> 转换脚本会把新的调色板直接打印成 Verilog，粘过去即可。

---

## 三、音乐引擎（已实现，尚待上板验收）

当前主线是 TDM 合成工程，出货顶层为 `tdm_ship.v`，核心逻辑在 `tdm_top.v`。
主要模块包括：`note_map.v` 音符分配与音高映射、`tdm_engine.v` 分时振荡器、
`osc_env.v` 包络、`i2s_tx.v` 音频串行输出、`fx_delay.v` 效果器、
`song_seq.v` 定序器、`pad_scan.v` 触摸输入、`reg_bank.v` 参数寄存器及 UART 收发模块。

旧的全并行参考实现仍保留在 `osc_core.v`、`osc_additive.v`、`synth_top.v` 等文件中，
用于对照和验证，不应与当前 TDM 出货顶层混为一谈。数字仿真与 PnR 证据见
`refs/素材库/未验证与挂账清单.md`；**板上电气、真实触摸 RC 量程和实际听感仍需硬件验收**。

---

## 四、编码约定（踩过的坑，别重复踩）

| 坑 | 规则 |
|---|---|
| `cell` 是 Verilog-2001 保留字 | 不要用它当变量名（会直接报 Syntax error） |
| 除以非 2 的幂很贵 | 用级联比较代替 `x / 60`；`x >> 5` 这类才便宜 |
| 组合逻辑 + 寄存信号混用 | 见上面「最容易踩的坑」 |
