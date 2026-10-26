# RTL 资产模块级索引（2026-10-27）

本页是 `SOURCE-MAP.md` 的**模块级补充**，不替代它。

- `SOURCE-MAP.md` 回答：**哪一份目录是当前候选**（目录级、来源级）。
- 本页回答：**每一个 Verilog 模块是什么、被谁例化、有没有进产品顶层、有没有测试台**（模块级、接合级）。

读序：`PRODUCT-SPEC.md` → `SOURCE-MAP.md` → **本页** → `ENGINEERING.md` → `WORK-PLAN.md`。

本页所有数字均可用文末 §11 的命令复现。

---

## 1. 远程仓库实况

| 远端名 | 仓库 | 可见性 | `main` 头 | 远端 pushedAt |
|---|---|---|---|---|
| **`internal`** | `sakuyaShining/FPGA-Music-project-internal` | **PUBLIC** | `b732de68` 2026-10-26 22:29 | `2026-10-26T14:29:31Z` |
| `origin` / `public` | `sakuyaShining/FPGA-Music-project` | **PRIVATE** | `12a4f07d` 2026-10-08 18:14 | `2026-10-26T12:29:33Z` |

**远端名与可见性相反，不要按名字推断。** 名称里的 `internal` 不表示私有。

`internal/main` vs `origin/main` = **158 领先 / 2 落后**，`git merge-base` **为空** ⇒ 两个仓库**无共同祖先**，拓扑分裂。

⇒ **唯一权威 = `internal/main`。** 取代码、比对基线、推送目标，只认它。

---

## 2. 本地基线实况

同一仓库在本机有 **21 个 git worktree**（`git worktree list`），其中 5 个是有实际内容的副本：

| 路径 | 分支 | HEAD | 落后 `internal/main` | 判定 |
|---|---|---|---|---|
| `D:/FPGA-Project/maintenance-20261026/repo` | `main` | `b732de68` | **0** | ✅ **最新权威**（Codex 维护窗口，PR#7 已合） |
| `D:/FPGA-Project/wb-sync-20261026` | `codex/workbuddy-asset-index-20261027` | `b732de68` | **0** | ✅ 本次索引分支 |
| `D:/FPGA-Project/current-design` | `main` | `c0b770e` 2026-10-23 | 落后 | 旧 clone，勿用 |
| `C:/Users/Sakuya/FPGA-Music-project` | `main` | `3824391d` 2026-10-22 | **落后 31** | ⚠️ 主 checkout，**有未提交改动**（`README.md`、`monitoring-log.md`、`monitor-state.json` + 未跟踪 `.obsidian/`） |
| `D:/FPGA-Project/authoritative-20261024` | `codex/91-spec-intake-20261024` | `1c37939c` | 落后 | 旧快照 |

**规则：谈"最新"只看 `internal/main` 的提交，不看目录日期、不看文件名版本号。**

### 2.1 仓库外的资产（不在 git 里，最容易漏）

| 位置 | 内容 | 说明 |
|---|---|---|
| `C:/Users/Sakuya/Documents/xwechat_files/wxid_zi9p6o0njyj022_9772/msg/file/2026-10/` | **`impl_pnr_board.fs`**（7,264,154 B）、`handover.zip`、`handover(1).zip`（825,074 B） | **本机唯一码流在这里**。查"本地有没有码流"必须先查这个目录 |
| `D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2/` | `实体交付当前入口.json`（**Codex 持续更新，交付口径以此为准**）、`collaboration-20261026/workbuddy-output/`（WorkBuddy 交付 00–13 号） | 交付口径与并行方案 |
| `D:/FPGA-Project/authoritative-20261024/project/reviews/20261025-handover-bitstream/` | 队友码流上板评审 `REPORT.md`（含 `selfcheck` 与 slack） | 码流实测证据 |
| `D:/FPGA-Project/maintenance-20261026/` | Codex 维护窗口脚本 `apply.py` / `apply2.py` + `repo/` 完整 clone | 门禁窗口修正的出处 |
| `D:/FPGA-Project/temp/handover-x/` | 解开的交接包（临时，可删） | 含 `构建记录-run.json` |

**查"本地有没有某文件"的正确顺序：git 全历史 → 微信接收目录 → `D:/FPGA-Project/temp`、`downloads`、`codex-deliverables` → 最后才全盘 find（易超时）。**

---

## 3. 源码树全景

| 目录 | 内容 | 角色 | 权威性 |
|---|---|---|---|
| **`fpga/current/engine/src`** | **77** `.v` + 13 `.hex` + 1 `.vh` | **产品源码**，`build_product.py` 唯一输入 | ✅ **权威** |
| `fpga/current/engine/rtl` | 1 | `uart_cfg_transport.v` | ✅ 权威 |
| `fpga/current/sim` | **7** `tb_*` + 2 `.hex` 向量 | 产品侧仿真，入口 `tools/run_sims.py` | ✅ 权威 |
| `fpga/current/tb` | **9** `tb_*` + 4 模型 | 产品侧仿真，入口 `check_*.py` | ✅ 权威 |
| `fpga/current/tools` | 8 `.py` + `scripts/` | 板上检查/向量生成/统一仿真 | ✅ 权威 |
| `fpga/current/reference` | 12 | 黄金参考模型（`joint_timing_top.v`、`pitch_mod.v`、`rc_delta_store.v`、`mv_renderer_before.v`…） | ✅ 权威 |
| `fpga/current/rtl` | 10 | 结构探针（`joint_timing_top`、`sdram_*_probe`），**注释明确不可烧** | 探针 |
| `fpga/current/`（顶层） | 5 | `tb_compat_music`/`tb_envelope`/`tb_layers`/`tb_phase_wrap`/`tb_sensor_layers` | 探针 |
| `src/rtl` | 35 | ⚠️ **旧副本**，15 个文件与 `engine/src` 不一致 | 历史复现 |
| `src/sim` | 59 个 `tb_*` | ⚠️ 旧链测试，测的是 `src/rtl` | 历史复现 |
| `experiments/nano20k_feasibility_20261021` | 73 + 13 | 历史实验副本 | 归档 |

**产品侧测试台合计 21 个**（7 + 9 + 5），入口分两套：`fpga/current/tools/run_sims.py`（7 个）与 `fpga/current/check_*.py`（其余）。

### 3.1 `src/rtl` 与 `engine/src` 同名文件比对

**35 个同名，20 个逐字节一致，15 个不同，且 `engine/src` 侧全部更长（更新）：**

| 文件 | `src/rtl` | `engine/src` | 差 |
|---|---|---|---|
| `pad_scan.v` | 312 | **370** | +58 |
| `reg_bank.v` | 184 | **247** | +63 |
| `pitch_mod.v` | 199 | **252** | +53 |
| `tdm_top.v` | 1111 | **1157** | +46 |
| `note_map.v` | 585 | **629** | +44 |
| `tdm_engine.v` | 900 | **943** | +43 |
| `fx_delay.v` | 298 | **327** | +29 |
| `osc_env.v` | 194 | **222** | +28 |
| `vel_shape.v` | 106 | **127** | +21 |
| `i2c_master.v` | 265 | **283** | +18 |
| `osc_additive.v` | 243 | **248** | +5 |
| `pad_pitch.v` | 111 | **116** | +5 |
| `song_seq.v` | 204 | **208** | +4 |
| `tdm_ship.v` | 68 | **71** | +3 |
| `event_hold.v` | 146 | **111** | **−35**（唯一反向） |

⇒ **改 RTL 一律改 `engine/src`。`src/rtl` 只读、不改、不删。**

---

## 4. 模块级资产索引

### 4.1 出货链（唯一根，`build_product.py` 实际构建的对象）

```
tdm_ship_beacon (38)                        ← 唯一根，无父
└── tdm_ship_owned (183)                    ← build_product.py 默认 TOP
    ├── rst_gen (96)
    ├── uart_beacon (88)
    └── tdm_top_owned (1477)                ← 产品音频顶层
        ├── audio_clk_en (129)      board_diag (117)
        ├── event_hold (110)        finger_pitch (81)
        ├── fx_delay (326)          i2s_tx (95)
        ├── led_ind (117)           live_audio_monitor (139)
        ├── live_observation_filter (116)
        ├── note_map_owned (890)    pad_pitch (115)
        ├── pad_scan (369)          reg_bank_compact (61)
        ├── song_seq (207)          strip_ctrl (64)
        ├── tdm_engine_rh (1132)    uart_rx (129)  uart_tx (110)
        └── uart_cfg_transport (engine/rtl)
```

**测试台：4 个** —— `tb_beacon`（→ `uart_beacon`）、`tb_rst_gen`（→ `rst_gen`）、`tb_pad_chain`（→ `pad_scan` + `pad_pitch`）、`tb_pad_velocity`（→ 力度）。

**但 `tdm_top_owned` 本体（1477 行）、`tdm_engine_rh`（1132 行）、`note_map_owned`（890 行）、`tdm_ship_owned`、`tdm_ship_beacon` 全部无测试台。** 即：**叶子测了，主干没测。**

`tdm_top_owned` 端口 **44 组**，而旧版 `tdm_top` 只有 **16 组** —— 接口已扩，扩出来的部分没有覆盖。

### 4.1.1 力度链路实况（重要：链路是通的，缺的是标定）

**不是"力度是常量"。** 三个来源都汇到 `tdm_engine_rh` 的 `.in_vel`：

| 来源 | 行 | 信号 |
|---|---|---|
| UART 写入 | `tdm_top_owned.v:666` | `wire [3:0] u_ev_vel = wr_data[3:0]` |
| 曲谱序列 | `tdm_top_owned.v:1101` | `.in_vel(sq_ev_vel[7:4])` |
| **pad（电容）** | `tdm_top_owned.v:727` | `wire [3:0] pp_ev_vel` |

`pad_scan.v` 真的算力度：

```
:50   //   vel_shift 是量程归一化：ev_vel = clamp((cnt-base) >> vel_shift, 0, 15)
:51   //   **必须上板实测 base 才能定 vel_shift**（见 VELOCITY-PATH 文档 §4）
:53   //   默认 5 是 base≈500 量级（12 位计数）的估计值，不是实测值。
```

**⇒ 缺口不是"没有力度"，是：**
1. **`vel_shift` 默认 5 是估计值，必须上板实测 `base` 才能定**（`fpga/current/tools/board_velocity_check.py` 就是干这个的）；
2. **84 电极链没有力度输出** —— `rc_mux_scan` 只输出 `row_count`（每通道裸计数）+ `row_fault`，力度得在下游从 `row_count` 算；而 `pad_scan`（16 路直连）已经算好了。**换 84 电极会丢掉现成的力度实现。**

### 4.2 84 电极链

```
instrument_sensor_probe (44)          ← 只在 probe 里
├── rc_mux_scan (87)  → scan_shift595 (42)     ← 84 通道 MUX 扫描 + 595 驱动
├── rc_strip_positions (97)                    ← 重心插值
└── rc_delta_store (80)                        ← delta 存储

left_contact_bridge (190)             ← 力度 + 音符分配
   被 left_music_probe (68) / left_layer_music_probe (90) 例化
```

**测试台：3 个**（`tb_sensor` → `instrument_sensor_probe`；`tb_positions` → `rc_strip_positions` + `rc_delta_store`；`tb_delta` → `rc_delta_store`）

**接入状态：从未进产品顶层。** `tdm_top_owned` 例化的是 `pad_scan`（16 路直连 + 内部下拉），不是 `rc_mux_scan`（84 路 MUX）。

`rc_mux_scan.v:39` 的 595 字构造与板上器件逐位对应：

```verilog
wire [7:0] word_data = {2'b00, (state==CHARGE),
                        (state==DISABLE||state==ADDRESS), word_address};
```

| 位 | 595 输出 | 板上网络 |
|---|---|---|
| `bit3:0` | `QD..QA` | `ADDR3..ADDR0` ✅ |
| `bit4` | `QE` | `MUX_DISABLE` ✅ |
| `bit5` | `QF` | `RC_DRIVE` ✅ |
| **`bit7:6`** | `QG` / `QH` | **`LCD_RESET_N` / `TP_RESET_N` ← 恒 0，屏永远在复位** |

第 1 行注释 `Inverting Schmitt inputs: discharged=1, charged=0` 对应 `U7 = SN74LVC14ADR`。
**这套代码是照这块板逐脚写的，不是通用代码。**

### 4.3 右手链

```
rh_performance_control (49)           ← 5 点触控 → 8 推子 + 16 增益
├── rh_fader_panel (40) → rh_fader_bank (150)
├── rh_fader_gain_map (62)
└── rh_timbre_slew (60)

tdm_top_rh (1175)                     ← 带右手的音频顶层，只在 rh_music_probe (45) 里
```

**测试台：0 个。**

**接入状态：`rh_performance_control` 被 4 个 probe 用（`compat_music_probe`/`left_layer_music_probe`/`left_music_probe`/`rh_music_probe`）；`tdm_top_rh` 从未进产品顶层。**

### 4.4 屏幕链（J11 已取消，J10 未接）

```
music_visualizer (36)
├── mv_fft1024 (150)                  ← 1024 点 radix-2 DIT + Hann 窗
├── mv_wave_capture (30)
└── mv_renderer (214)                 ← 320×240，脏矩形，无全帧缓冲
    └── mv_panel_driver (130)         ← RGB565 SPI 控制器候选
        └── mv_spi_byte (50)
```

**测试台：1 个**（`tb_renderer`）

**关键事实：**
- 这套是 **320×240 RGB565 SPI**，`mv_panel_driver` 头部原文：「Panel power/gamma settings are not qualified without the actual module's reference initialization」⇒ **未在真屏上验证过**。
- 它对应的是 **J11 实体可视化屏**，而 **J11 已被用户取消**（`PRODUCT-SPEC.md` R04、`DESIGN-CURRENT.md` §防止旧设计回流）。
- **J10 是 7 寸 RA8875 触控屏，需要 800×480，这套不能直接用。** 可复用的只有 `mv_spi_byte`（50 行，纯 SPI 位发送）和脏矩形渲染思路。
- **J10 的触摸走 I²C（FT5316），而 `i2c_master.v`（283 行）已存在且与队友构建逐字节一致。**

### 4.5 总线与按键

| 模块 | 行数 | 作用 |
|---|---|---|
| `scan_shift595.v` | 42 | 595 串行装载（`ADDR0-3`/`MUX_DISABLE`/`RC_DRIVE`/两复位） |
| `rc_mux_scan.v` | 87 | 6 路并行 SENSE 扫描状态机，状态序 `DISABLE→ADDRESS→CONNECT→DISCHARGE→CHARGE→MEASURE→PUBLISH` |
| `instrument_table.v` | 36 | 乐器槽表 |
| `layer_dispatch.v` | 136 | 四层派发（**当前限制最多两层**） |
| `board_diag.v` | 117 | 板级自检 |
| `rst_gen.v` | 96 | 复位生成 |

**SN74LV165（输入移位，8 路按键/编码器）在 Verilog 里没有对应模块** —— 搜 `165`/`key`/`encoder` 无命中。

---

## 5. 接合缺口（按严重度）

| # | 缺口 | 证据 | 影响 |
|---|---|---|---|
| **G1** | **出货链主干 0 测试台** | 叶子有 4 个 tb，但 `tdm_top_owned`(1477)/`tdm_engine_rh`(1132)/`note_map_owned`(890) 均无 | 3499 行核心逻辑改动只能上板看 |
| **G2** | **84 电极链未进产品顶层** | `tdm_top_owned` 例化 `pad_scan`（16 路），非 `rc_mux_scan`（84 路） | 84 电极硬件接上也不工作 |
| **G3** | **右手链未进产品顶层** | `tdm_top_rh` 只在 `rh_music_probe` 里 | 右手泛音功能不可用 |
| **G4** | **595 的 `bit7:6` 恒 0** | `rc_mux_scan.v:39` `{2'b00,...}`；`grep LCD_RESET\|TP_RESET engine/src/*.v` = **0 行** | 屏与触摸**永远在复位** |
| **G5** | **84 电极与 SPI 屏从未有引脚约束** | 4 个 `.cst` 全部不含 `sense`/`addr`/`rc_drive`/`mux_disable`/`scan_bus_*`/`lcd_*` | 综合不出来，只能先写 cst |
| **G6** | **力度未标定 + 84 链无力度输出** | `pad_scan.v:51-53` 原文「**必须上板实测 base 才能定 vel_shift**」「默认 5 是估计值，不是实测值」；`rc_mux_scan` 只出 `row_count`/`row_fault`，无力度 | 力度能出但量程未定；换 84 电极会丢掉 `pad_scan` 里现成的力度实现 |
| **G7** | **165 输入链无 RTL** | 搜 `165`/`key`/`encoder` 无命中 | 4 预设键 + 编辑键 + 编码器无驱动 |
| **G8** | **`layer_dispatch` 限两层** | `DESIGN-CURRENT.md` 原文 | 四层目标未达 |

### 5.1 已存在但从未使用的总装配点

`fpga/current/engine/src/instrument_owned_probe.v`（**61 行**）第 1 行原文：

```verilog
// Internal logical interfaces, not a physical GPIO allocation or shipping top.
```

它已经把**三条链全部接好**：

```verilog
left_music_probe   music(...)        // 左手 → tdm_top_owned（含 rh_performance_control）
music_visualizer   visualizer(...)   // 屏幕（FFT + 渲染 + SPI 屏驱动）
instrument_sensor_probe sensor(...)  // 84 电极（rc_mux_scan + rc_strip_positions + rc_delta_store）
```

端口 in18 / out26（44 组信号）。**它是现有代码里最接近产品顶层的东西，缺的只是物理引脚约束和上面 G1–G8。**

---

## 6. 测试覆盖错位（本索引最重要的一节）

| 链 | 产品模块数 | 测试台 | 覆盖 | 被测到的 | **没被测到的** |
|---|---|---|---|---|---|
| **出货链（音频）** | 19 | **4** | ⚠️ 叶子有、主干无 | `uart_beacon`、`rst_gen`、`pad_scan`+`pad_pitch`、力度 | **`tdm_top_owned`(1477)**、**`tdm_engine_rh`(1132)**、**`note_map_owned`(890)**、`tdm_ship_owned`、`tdm_ship_beacon`、`fx_delay`(326) |
| 84 电极链 | 5 | **3** | ✅ 有 | `instrument_sensor_probe`、`rc_strip_positions`、`rc_delta_store` | `rc_mux_scan` 单体（只在整链里间接测） |
| 右手链 | 6 | **0** | ❌ **全空** | — | `rh_performance_control`、`rh_fader_bank`、`rh_fader_gain_map`、`rh_timbre_slew`、`rh_fader_panel`、`tdm_top_rh`(1175) |
| 屏幕链 | 6 | **1** | ⚠️ 部分 | `mv_renderer` | `mv_fft1024`、`mv_panel_driver`、`mv_spi_byte`、`mv_wave_capture`、`music_visualizer` |
| 旧链 `src/rtl` | 35 | **35**（`regress_all.py`） | ✅ 充分 | `tdm_top`(1111) 及全部子模块 | — |

**⇒ 两个事实同时成立：**
1. **旧链（`src/rtl` + `tdm_top` 1111 行）测试最充分，但它不是要出货的代码。**
2. **出货链最重的三个模块（1477 + 1132 + 890 = 3499 行）一个测试台都没有。**

`regress_all.py`（1057 行）跑 **35 个** `src/sim` 里的 tb，全部针对 `src/rtl`，**不覆盖 `engine/src`**。

全仓库 `tb_*.v` 共 **135 个**（含 16 个评审目录里的历史快照），当前可用的：
`src/sim` 59 + `fpga/current/sim` 7 + `fpga/current/tb` 9 + `fpga/current/` 顶层 5 = **80 个**。

---

## 7. 约束文件实况

| 文件 | `IO_LOC` 数 | 内容 |
|---|---|---|
| **`fpga/current/constraints/tdm_ship_owned.cst`** | **30** | `clk`=4, `btn_rst`=87, `led[0..5]`=15–20, `pa_en`=51, `dac_din/ws/bck`=54/55/56, `uart_rx/tx`=69/70, **`pad[0..15]`=27–42 `PULL_MODE=DOWN`** |
| `src/constr/bringup_top.cst` | 29 | **RGB 并口**屏：`lcd_r/g/b` + `lcd_clk/de/hsync`（4.3 寸裸屏，非 SPI） |
| `fpga/current/constraints/sdram_board.cst` | 14 | SDRAM 探针 |
| `src/constr/tdm_top.cst` | — | 旧产品 |
| `src/constr/tangnano20k.cst` | 6 | 板载音频 |
| `src/constr/osc_additive_top.cst` | 12 | 最小合成器 |

**`pad[0..15]` 的 `PULL_MODE=DOWN` 正是 `pad_scan.v` 的「16 路直连 + 内部下拉」架构所需** ⇒ 现有约束与现有产品顶层自洽，但与 84 电极 MUX 架构**不兼容**。

---

## 8. 构建与验证入口

| 入口 | 顶层 | 用途 | 备注 |
|---|---|---|---|
| `fpga/current/build_product.py` | `tdm_ship_owned`（默认，可传第 4 参覆盖） | **唯一出货构建** | `python build_product.py synth_<label>`（~1m45s）/ `build_<label> full 1`（~9–15 min）；**拒绝覆盖已有目录**；**永不烧录** |
| `fpga/current/build_board.py` | `joint_timing_top` | 结构探针 | 头部注释：**must NEVER be programmed** |
| `fpga/current/tools/run_sims.py` | — | **产品侧统一仿真**，157 行，跑 7 个 tb | `tb_beacon tb_decay2 tb_pad_chain tb_pad_velocity tb_rst_gen tb_strike tb_vel_shape` |
| `fpga/current/check_*.py`（13 个） | — | 逐模块仿真（`check_sensor`/`check_positions`/`check_delta`/`check_renderer`/`check_pitch`…） | 对应 `fpga/current/tb` |
| `fpga/current/tools/board_velocity_check.py` | — | **板上力度实测**，用来定 `vel_shift` | 对应 G6 |
| `tools/scripts/regress_all.py` | `src/rtl` + `src/sim` | 35 个 tb | **不覆盖 `engine/src`** |
| `tools/scripts/accept_all.ps1` | — | 88 行，调 `check_timing.py` | |
| `tools/scripts/design_governance.py` | — | 门禁（`review_sha256` + `reviewed_at` 双锁） | |
| `tools/scripts/tdm_compare.py` | — | 黄金参考比对 | |
| `tools/scripts/music_profiles.py` | — | 音乐档位（新增，299 行） | |

Gowin 命令行：`D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe`，用法 `gw_sh.exe build.tcl`。

---

## 9. 码流实况

- **仓库内 `.fs` = 0 个。**
- 本机唯一码流在微信接收目录：`C:/Users/Sakuya/Documents/xwechat_files/wxid_zi9p6o0njyj022_9772/msg/file/2026-10/impl_pnr_board.fs`（7,264,154 B）。
- 该码流顶层是 **`tdm_product_top`**，**本地不存在这个文件**（`git log --all` 全历史无）。

队友构建记录 `构建记录-run.json`：

| 字段 | 值 |
|---|---|
| `status` / `returncode` | `ok` / `0` |
| `mode` / `strategy` | `full` / `1` |
| **`top`** | **`tdm_product_top`** |
| `seconds` | 97.49 |
| `hardware_programmed` | **`false`** |

上板实测（`project/reviews/20261025-handover-bitstream/` 外部报告）：`GW2AR-18C` ID `0x0000081B`、SRAM 烧录 100%、`selfcheck.ps1` PASS、SETUP 最小 **+10.413 ns** / HOLD 最小 **+0.205 ns** / 负 slack **0**。

**⇒ 那份码流证明的是「音频链路 + 16 路旧 pad 通」，不证明 84 电极、不证明屏。**

### 9.1 PnR 崩溃风险（已定位，未修）

`project/reviews/20261024-router-crash-diagnosis/review.json`：

- 17 次 PnR：**9 次 access violation（`0xC0000005`）**，7 次完成，1 次不确定
- 根因：**数据输入 min-delay 覆盖 + 自动 hold 修正联合触发**，厂商内部机制未证明
- 反例：保留全部原约束、关掉 hold 修正 → 能跑完，但最差 hold **−1.402 ns**
- 已排除的绕法：`registered shell inputs` / `explicit bus-bit spelling` / `alternate place/route strategy`
- **范围：只发生在隔离单元外壳（`note_event_router`），产品顶层 `tdm_ship_owned` 未复现**

⇒ **这不是产品顶层的阻塞，但是新增单元的已知工具坑。动新模块时要预期这个失败。**

---

## 10. 分支管理规则

| 分支 | 内容 | 状态 |
|---|---|---|
| **`internal/main`** | 唯一权威 | `b732de68` |
| `codex/workbuddy-asset-index-20261027` | 本页 | 基于 main 新建 |
| `codex/workbuddy-selection-sync-20261026` | 13 提交：`project/` 755、`hardware/` 95、`experiments/` 67、`notes/` 9、`tools/` 5、`docs/` 1 —— **产品 RTL（`engine/src`、`src/rtl`）零改动** | 保留 |
| `codex/maintenance-window-20261026` | Codex 门禁窗口修复 | 已合 PR#7 |
| `codex/e3-electrical-20261025` | PCB 电气（42 项未连通） | 未合 |
| `codex/pcb-sync-plan-20261025` / `codex/pcb-independent-review-20261025` / `codex/pcb-paused-status-20261025` | PCB 并行 | 未合 |
| `codex/preserve-*`（16 条） | 不可删 —— `verify-entry` 硬依赖 | 冻结 |

**六条硬规则：**

1. **只推 `internal`。永不推 `origin` / `public`**（私有、落后 155 提交、无共同祖先）。
2. 每次推前 `gh repo view <owner>/<repo> --json visibility` 确认可见性。
3. 新建分支一律 `git checkout -b <name> internal/main`。
4. **不删 `codex/preserve-*`**（16 条），`verify-entry` 硬依赖；`AGENT-BOARD.md` 还引用 `codex/current-engineering-sources-20261023`、`codex/main-design-authority-20261023`。
5. 文档类改动单独分支，**不与 RTL 混提**。
6. **动 RTL 前先 `python build_product.py synth_<label>` 确认基线能过**，不要先改后验。

---

## 11. 复现命令

```bash
# 远端可见性（远端名与可见性相反，必须实测）
gh repo view sakuyaShining/FPGA-Music-project          --json visibility,isPrivate,updatedAt
gh repo view sakuyaShining/FPGA-Music-project-internal --json visibility,isPrivate,updatedAt

# 拓扑分裂
git rev-list --left-right --count internal/main...origin/main   # → 158  2
git merge-base internal/main origin/main                        # → 空

# 本地基线
git worktree list

# 同名文件比对
comm -12 <(ls src/rtl/*.v | xargs -n1 basename | sort) \
         <(ls fpga/current/engine/src/*.v | xargs -n1 basename | sort)

# 84 电极是否进产品顶层
grep -n "pad_scan\|rc_mux_scan" fpga/current/engine/src/tdm_top_owned.v

# 屏复位位是否被清零
grep -n "word_data" fpga/current/engine/src/rc_mux_scan.v
grep -rn "LCD_RESET\|TP_RESET" fpga/current/engine/src/*.v      # → 0 行

# 引脚约束是否含 84 电极 / SPI 屏
grep -lE "sense|addr[0-3]|rc_drive|mux_disable|scan_bus|lcd_" fpga/current/constraints/*.cst src/constr/*.cst

# 码流
find . -name "*.fs" -not -path "./.git/*"                       # → 0
```

---

## 12. 维护本页

- 本页由 WorkBuddy 于 2026-10-27 生成，数据基线 `internal/main` = `b732de68`。
- **任何 RTL 接合（G1–G8 中任一项关闭）都必须同步更新 §4、§5、§6。**
- 本页**不替代** `SOURCE-MAP.md`；目录级来源关系仍以它为准。
