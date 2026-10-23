# 自定义乐器 / "编辑按钮" 实现现状盘点 · 2026-10-23

回答：成品上的"编辑按钮"（用于编辑自定义乐器、保留默认配置）现在实现到什么程度。

**一句话结论：代码约九成已存在，但没有一条通路被打开；实体"编辑按钮"完全不存在。**

---

## §0 六层状态总表

| # | 层 | 组件 | 代码状态 | 产品里是否生效 |
|---|---|---|---|---|
| 1 | 运行时音色存储 | `engine/src/instrument_table.v` | ✅ 完整（4 槽 × 2 bank × 16 泛音 × 88 位，双缓冲 + 原子 commit） | ⚠️ 在网表里，但写口 `cfg_*` **全接 0** |
| 2 | 串口上传协议 | `engine/rtl/uart_cfg_transport.v` | ✅ 完整（A5…5A + CRC16-CCITT + 176 字节 + 16 词 + commit + `0xD0–0xDF` 回读） | ❌ `CONFIG_SERIAL=0` ⇒ **不例化 ⇒ 综合时被优化掉** |
| 3 | 上位机编辑界面 | `FPGA-Music-project/experiments/config_transport_20261017/` | ✅ 约 7000 行，104 项离线测试通过 | ❌ 未发布 exe、**从未上板联调** |
| 4 | 掉电保存 | 24LC256 EEPROM | ❌ **零实现** | `i2c_master.v` 文件在、也在 `board.gprj` 列表里，但**没有任何模块例化它** |
| 5 | 实体"编辑按钮" | — | ❌ **不存在** | CST 里只有 `btn_rst`(87) + 16 个 `pad[*]` |
| 6 | 出厂默认乐器 | `preset_part.hex` | ✅ 4 预设 × 16 泛音 × 48 位 | ✅ 可用，`0x37` 选槽（需 `0x00[3]=1`） |

---

## §1 硬件存储这一层是最完整的，而且比预设表强得多

```verilog
reg [87:0] words[0:127];   // 4 槽 × 2 bank × 16 泛音
reg [15:0] written[0:3];   // 每槽 16 位，标记哪些泛音已写
```

| | `preset_part.hex`（出厂） | `instrument_table`（自定义） |
|---|---|---|
| 类型 | ROM，`$readmemh` 上电加载 | RAM，运行时写 |
| 每泛音字段 | 48 位：`ratio` / `amp` / `epar` | **88 位**：上面全部 **+ 40 位自定义包络** |
| 40 位包络内容 | 无 | `custom` 标志、起音移位、`a_inc`、释放倍率、释放移位 |
| 改一次要多久 | 改文件 → 综合 + PnR + 烧录（**400–900 秒**） | 串口命令，**约 32 ms** |

**双缓冲是已经实现的**，这是"演奏中换音色不炸音"的物理基础：

```verilog
words[{slot, !banks[slot], part}] <= word;   // 写非活动 bank
// 16 个泛音全写完（&written[slot]）才允许 commit，commit 时 banks[slot] 翻转
```

`instrument_table` 还会**主动拒绝非法写入**（置 `error`）：`word[23]` 非 0、`word[87:84]` 非 0、`ratio_q8==0`、`d_m==0`、`s_lvl>32768` 等。

---

## §2 一个总开关卡住了两件事

`tdm_top_owned.v:47`：

```verilog
parameter integer CONFIG_DUAL_SOURCE=1, CONFIG_SERIAL=0, ...
```

`tdm_ship_owned.v:101` 例化 `tdm_top_owned` 时**没有传 `CONFIG_SERIAL`** ⇒ 用默认 0。于是：

```verilog
generate if(CONFIG_SERIAL) begin: serial_configuration
    uart_cfg_transport receiver(...);      // ← 不生成
end else begin
    assign cfg_read=0; assign cfg_sandbox=0;
    assign tx_cfg_valid=0; assign tx_cfg_commit=0;   // ← 走这里
    assign tx_cfg_slot=0; assign tx_cfg_part=0; assign tx_cfg_word=0;
end endgenerate
```

**后果链**：

```
CONFIG_SERIAL=0
  → cfg_valid 恒 0
  → instrument_table.enabled 恒 0
  → custom_hold <= cfg_enabled[event_preset] 恒 0
  → pentry 永远走 part_rom（出厂 ROM）
  → 自定义音色永远不发声
```

**而且这个参数同时控制第二件事。** `CONFIG_SERIAL` 被传给 `note_map_owned` 的 `SERIAL_CUSTOM_LEGACY`：

```verilog
// note_map_owned.v:458
wire [47:0] pentry = ((owned_hold||SERIAL_CUSTOM_LEGACY)&&!rf_mode)
                   ? (custom_hold ? custom_entry[47:0] : part_rom[{preset_hold,k}])
                   : part_rom[{preset,k}];
```

而 `owned_hold` 来自 `own_valid` 事件源，产品里 `own_valid(1'b0)` —— 所以 `owned_hold` 恒 0。
**⇒ 只有 `SERIAL_CUSTOM_LEGACY=1` 这一条路能让 `custom_entry` 参与发声。**

一句话：**打开 `CONFIG_SERIAL=1` 同时打开"上传协议"和"自定义音色生效"，两件事本来就该一起开。**

---

## §3 一个隐藏的坑：上电后 4 个槽是空的

`instrument_table` 的 `words[0:127]` **没有 `initial`，也没有 `$readmemh`**，`enabled` 复位为 0。

| 上电后 | 值 |
|---|---|
| `words[0:127]` | 全 0（综合后） |
| `enabled[3:0]` | `4'b0000` |
| `banks[3:0]` | `4'b0000` |

**这是刻意的安全兜底**——RAM 里是垃圾也不至于炸音，全部退回 ROM 预设。
**但它意味着：即使打开 `CONFIG_SERIAL`，上电后也必须完整上传一遍才有自定义音色。不连电脑 = 只有出厂预设。**

要摆脱这个约束，只能做 EEPROM 上电加载（§4）。

---

## §4 EEPROM：文件在，但没接线

```
engine/src/i2c_master.v         存在，且在 board.gprj 的 FileList 里
grep -rn "i2c_master" engine/src/ sim/  →  除自身外无任何结果
```

**`i2c_master` 没有被任何模块例化 ⇒ 综合器把它整个丢掉 ⇒ 网表里不存在这个模块。**

缺的四件事（与 2026-10-22 的评估一致，无变化）：

| # | 工作 | 说明 |
|---|---|---|
| P1 | 把 `i2c_master` 接进产品顶层 | 模块本身已有，含时钟拉伸容忍与超时 |
| P2 | 24LC256 时序层 | 2 字节地址、页写 64 字节边界、写周期 5 ms 需轮询 ACK |
| P3 | 上电加载 | 复位后读 → CRC 校验 → 灌进 `instrument_table` |
| P4 | 保存 | 用户点"保存" → RAM 读回 → 写 EEPROM → 回读校验 |

**容量核算**：4 槽 × 2 bank × 16 泛音 × 11 字节 = 1408 字节；24LC256 有 32 KiB ⇒ 可存 **23 套**。

**未核的风险**：24LC256 与触控 IC（FT5316 / GT911）大概率共用 I²C 总线。触摸是高频轮询、EEPROM 是低频突发，需要仲裁或严格分时。这条要在选屏定案时一起核。

---

## §5 实体"编辑按钮"：零实现

`build_decay2_v1/tdm_ship_owned.cst` 里全部 30 个引脚：

| 用途 | 引脚 |
|---|---|
| 时钟 | 4 |
| 复位（S1，**高有效**） | 87 |
| 功放使能 + I²S | 51 / 54 / 55 / 56 |
| UART | 69 / 70 |
| LED | 15–20 |
| 电容电极 `pad[0..15]` | 27–42（其中 32–40 物理不可达，见下） |

**没有任何一个引脚叫"编辑"或"模式"。** 65 号文档对实体编辑的定义原文是：

> 实体 Edit→选槽/按压旋钮和屏幕页面应明确显示所处模式、目标槽、未应用/未保存状态；**页面具体流程仍待实现/讨论中**。

所以"编辑按钮"目前是**产品规格里的一个概念，没有引脚、没有交互定义、没有状态机**。

### 顺带一个必须记着的缺陷

CST 把 `pad[0..15]` 写成引脚 27–42，但 **32–40 不在板边 J5/J6 排针上，部分接 HDMI 电路**。
`60-整机选型收尾与真实排针核对-2026-10-15.md:16` 原文：「旧 `tdm_top.cst` 中'27～42 全部为 40P 排针'的描述**不能作为接线依据**」。

**物理可达的电极只有 7 路**：27(J6-8)、28(J6-9)、29(J6-12)、30(J6-13)、31(J6-14)、41(J5-6)、42(J5-5)。

---

## §6 出厂默认乐器：这一层是好的

`preset_part.hex` = 4 预设 × 16 泛音 × 48 位，**可用**。

切换方式（不需要改 RTL，现在就能做）：

```
0x00 bit3 = 1      → preset_src = 寄存器（默认 0 = 引脚，而引脚 own_preset 硬接 0）
0x37[1:0] = 0..3   → 选第 N 号预设
```

**但产品里没有实体按键切预设。** 目前只能用串口写。

---

## §7 打开这条路要付多少

### 7.1 面积（估算，未综合验证）

`uart_cfg_transport` 的规模：

| 项 | 量 |
|---|---|
| `buffer[0:255]` 8 位 | **1 BSRAM**（当前 15/46，有 31 块余量） |
| `word_shift[87:0]` | 88 FF |
| `crc[15:0]` + `sequence_id` + `revision` | 48 FF |
| 状态机 + 计数器（`state`/`count`/`age`/`quiet` 等） | ≈ 60 FF |
| CRC16 组合逻辑（8 次迭代） | ≈ 100–150 LUT |
| **合计** | **≈ +200 FF、+1 BSRAM、+200 LUT** |

叠加 `SERIAL_CUSTOM_LEGACY=1` 带来的几处 mux（`pentry` / `env_base` / `amp_src`），估计 **+300 CLS 以内**。
当前 8265/10368 CLS（80%），加到约 83% —— **可以接受，但会吃掉四层预留的一部分余量。**

> ⚠️ 这是估算。要准确数字必须真跑一次 `CONFIG_SERIAL=1` 的 PnR（400–900 秒）。

### 7.2 真正的成本不在面积，在**验证**

| 要做的事 | 为什么贵 |
|---|---|
| 上板联调上传协议 | 需要一个 host 脚本模拟 A5…5A 全流程 + CRC，且要和 `quiet` 检测、`sandbox` 隔离对上 |
| 验证"演奏中换音色不炸音" | 要在**正响着的和弦上**做 commit，判据只能靠听感 + 波形 |
| 验证非法写入被拒 | 要构造 6 类非法 88 位字，逐条确认 `error` 置起 |
| EEPROM 掉电保存 | 整个 I²C 从机时序 + 页写边界 + 5ms 轮询，**零基础** |

---

## §8 11-04 之前的三个可选深度

| 方案 | 内容 | 能做到 | 代价 |
|---|---|---|---|
| **A 最小可用** | `CONFIG_SERIAL=1` + 一个 host 上传脚本 + 4 个出厂预设 | **"连电脑就能换自定义音色"**，掉电丢 | 小（1–2 天） |
| **B A + 预设切换实体化** | A + 用现有按键/pad 切 4 个预设 | 不连电脑也能在 4 个默认音色间切 | 中 |
| **C 完整产品** | A + EEPROM 掉电保存 + 实体编辑按钮 + 屏幕编辑页 | 用户自己捏音色并保存 | **大**，11-04 前不可能 |

**我的判断**：11-04 前能交付的是 **A**（如果只做 RTL + 脚本，甚至能更快）。B 看按钮资源。C 不是时间问题，是 EEPROM 和触控屏都还没定案。

---

## §9 复现命令

```bash
P=D:/FPGA-Project/codex-builds/fpga-m1-agent-work

# 总开关
grep -n "CONFIG_SERIAL=0" $P/engine/src/tdm_top_owned.v
grep -n "cfg_valid(1'b0)" $P/engine/src/tdm_ship_owned.v

# 存储层
sed -n '1,35p' $P/engine/src/instrument_table.v

# 上传协议
sed -n '1,20p' $P/engine/rtl/uart_cfg_transport.v

# EEPROM 是否接线（应为空）
grep -rn "i2c_master" $P/engine/src/ $P/sim/ | grep -v "^$P/engine/src/i2c_master.v"

# 实体引脚
cat $P/build_decay2_v1/tdm_ship_owned.cst
```
