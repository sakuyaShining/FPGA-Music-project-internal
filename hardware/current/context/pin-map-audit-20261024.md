# 引脚映射核对 · 2026-10-24

对象：91 号 v1 码流（`tdm_ship_owned`）+ 载板 `e098c5db`。
结论：**v1 引脚表正确；载板的「J6 pin → FPGA pin」这一层从未验证，且与官方 LED 定义冲突。**

---

## 一、v1 引脚表：已与官方 cst 逐条核对，全部正确

交叉来源：Sipeed `TangNano-20K-example` 的 `audio.cst`、`blink_leds.cst`、`Tang_nano_20K_LCD.cst`。

| 信号 | 91 号声明 | 官方来源 | 结果 |
|---|---|---|---|
| `clk` | 4 | `audio.cst` | 一致 |
| `btn_rst`（高有效） | 87 | `audio.cst` | 一致 |
| `pa_en` / `dac_din` / `dac_ws` / `dac_bck` | 51 / 54 / 55 / 56 | `audio.cst` | 一致 |
| `led[0..5]` | 15–20 | `blink_leds.cst` | 一致 |
| `pad[0..15]` | 27–42 | `Tang_nano_20K_LCD.cst`（LCD_B/G/R 数据线） | 一致 |

**附带的更正**：此前记录称「`pad[5..13]`（32–40）不在排针上，物理可达电极只有 7 路」，**该结论错误**。官方 LCD 示例把 27–42 连续 16 个脚分配给 RGB 数据线，不插屏时全部可作电极输入。**v1 的 16 电极直连物理成立。**

---

## 二、未验证的一层：`J6` 第 N 脚 ↔ FPGA 第 M 脚

`interface-references/expected-pin-nets.json` 只记录连接器级连接：

```json
"J5": { "5": "SENSE_4", "6": "SENSE_3", "7": "I2S_BCK", "8": "I2S_DIN",
        "10": "SENSE_5", "11": "I2S_LRCK", "15": "GND", "16": "3V3_IO" },
"J6": { "5": "TP_INT", "6": "BUS_MOSI", ... }
```

**不含「该脚对应 FPGA 几号」。** 该层来自 `hardware/system-candidate-20261015/nano-header-candidate.csv`，其 `status` 列自述：

```
candidate_not_for_connection_until_board_and_wrapper_check
```

### 2.1 与官方定义冲突

该 csv 把 15–20 分配给 `BUS_MOSI` / `SCAN_LATCH` / `INPUT_LOAD_N` / `LCD_VIS_CS_N` / `LCD_HARM_CS_N` / `LCD_SHARED_DC`。

但官方 `blink_leds.cst`：

```
IO_LOC "leds[5]" 20;  IO_LOC "leds[4]" 19;  IO_LOC "leds[3]" 18;
IO_LOC "leds[2]" 17;  IO_LOC "leds[1]" 16;  IO_LOC "leds[0]" 15;
```

**15–20 是板载 6 个 LED。** csv 自己的 `existing_load` 列写的就是 `onboard_LED_510ohm`——它知道这些脚挂着 LED，却仍当排针信号使用。

### 2.2 两种可能，后果都严重

| 情况 | 后果 |
|---|---|
| 15–20 引到排针但并着 LED | 做输出：LED 跟着闪，驱动被 510 Ω 分流。做**电极输入**：510 Ω + LED 形成弱上拉，干扰 `PULL_MODE=DOWN` 的放电计数，接触量读数失真 |
| 15–20 未引到排针 | 载板这 6 根线接在空脚或别的信号上，扫描链与屏接口整体错位，板子无法工作 |

### 2.3 唯一的判定方法

**万用表通断档，量「J6 第 6 脚 ↔ FPGA 15 号脚」是否导通。**

- 导通 → csv 映射成立，但 15–20 带 LED 负载，**不能用作电极输入**
- 不导通 → csv 映射错误，载板该组走线需重做

v1 码流已可烧录，板子在手，此测量约 5 分钟。**在此之前不应基于该 csv 继续扩展任何引脚规划。**

---

## 三、v1 与载板不是同一套输入方案

| | v1（`tdm_ship_owned`） | 载板 `e098c5db` |
|---|---|---|
| 电极输入 | 16 路直连 27–42 | 6 路 `SENSE_0..5` + 扫描链（6×74HC4067 → 84 节点） |
| 扫描链 | 无 | `BUS_SCK` / `BUS_MOSI` / `SCAN_LATCH` / `INPUT_LOAD_N` / `BUS_RETURN` |
| 屏 | 无 | `HARM_CS_N` / `TP_INT` / `J10` 12P |
| I²C | 无 | `I2C_SDA` / `I2C_SCL` |
| AUX | 板载 54/55/56 直出 | 走排针 `I2S_BCK` / `I2S_DIN` / `I2S_LRCK` |
| 供电 | 板载 USB-C | `J13` XH2.5 2P + 受保护电源入口 |

**结论：v1 码流可直接在裸 Nano 20K 上出声，插到载板上不工作。** 载板所需的 6 路 SENSE + 扫描链 RTL 不在 v1 中。

---

## 四、待治理层确认的两处

| # | 事项 | 说明 |
|---|---|---|
| 1 | **v1 的下载授权** | `fpga/current/README.md` 现写「`tdm_ship_owned` 是 16 路旧 pad 包装……不能因名字或路由完成而获得下载授权」；而 91 号文档给出了完整烧录步骤与 Verify Failed 判据。两者需对齐：要么治理层授权 v1 为可烧录基线，要么 91 号标注为「实验性烧录指引」 |
| 2 | **91 号的定位** | 文件名含「产品规格」，但内容实为 **v1 码流使用说明**。真正的产品规格是 `project/PRODUCT-SPEC.md`（R01–R12）。建议在 `fpga/current/README.md` 引用时注明此区别，避免与 PRODUCT-SPEC 混淆 |

---

## 五、码流身份

| 项 | 值 |
|---|---|
| 文件 | `impl_pnr_board.fs`（= 文档所称 `board.fs`） |
| 大小 | 7,264,154 B = 7,093.9 KB |
| SHA256 | `78650b34ec24cd863a40dd928fcaffb434f55c9d42453959941499d564c7b533` |
| 与 91 号声明 | 逐字符一致 |

码流不进 git（`.gitignore` 已含 `*.fs`），仅登记哈希。
