# M1 候选：相位写回重定时 + 两处面积修正（2026-10-22）

本文件是**改动说明与实测记录**，不是验收结论 —— **本轮没有任何时序数字**，
因为所有候选构建都没能通过布线（§5）。证据见 `evidence/m1v4-*/`；
基线证据见独立纯净副本 `D:/FPGA-Project/codex-builds/fpga-m1-baseline-ref/evidence/baseline01-*`。

**一句话结论**：−6.397 ns 有 67% 是"器件占满导致的长线"，不是逻辑深度；
把它修好需要先腾出约 **250–300 Logic**，本轮只做到 104。详见 §5.0、§5.4、§6。

## 1. 起点事实（87 号交付，未改动的原候选）

- 正常完整 PnR 退出 0、路由完成、码流生成完成；**STA 失败**：
  setup −6.397 ns / hold −0.048 ns / recovery +33.016 ns / removal +1.876 ns。
- 资源：Logic 20338/20736、**CLS 10346/10368**、Register 10760/15915、
  BSRAM 32/46、DSP 22.75/24。
- `board_tr_content.html` 总负裕量摘要：**core_clk setup TNS = −355.644 ns，
  186 个端点**（报告只列最差 25 条）。
- 这 25 条**全部**从同一个起点 `u_tdm/sl1_5_s0`（扇出 180）出发，终点只有两类：
  `phase_mem` 的 DI、`amp2`。

## 2. 关键路径逐段（`board.timing_paths`，累计到达，ns）

| 段 | 到达 | 段长 | 说明 |
|---|---:|---:|---|
| sl1_5 出发 | 2.503 | — | tC2Q 仅 0.232（另 2.271 为时钟到达） |
| physical_store RAD | 5.062 | 2.559 | 扇出 180 的布线 |
| DO[1] | 5.579 | 0.517 | RAM16SDP4 异步读 |
| n56_s1 | 10.707 | **5.128** | 双 bank 选择 mux（布线极长） |
| read_gq | 12.486 | 1.779 | 命令/物化 2:1 选择 |
| gq_sel[0] | 20.400 | **7.914** | `advance()` + 32:1 选择 + 门控，**7 个 LUT 级** |
| poff_sum | 22.791 | 2.391 | 19 位加法（进位链 0.035/位） |
| effective_poff | 28.733 | **5.942** | 限幅 + 接触表情选择（含 5.108 布线） |
| pmod_mul (DSP) | 35.035 | 6.302 | 25×18 乘法 |
| final_inc | 40.788 | 5.753 | 28 位加法（含 3.891 布线） |
| amp2 | 44.377 | 3.589 | `increment_invalid` 判定（n3872，3 级） |

一条 19 级组合链压在一个 37.037 ns 周期里，其中 27.8 ns 是 10 条 ≥1.6 ns 的布线
（CLS 100% 占用 ⇒ 布局无自由度）。不是"换布线策略"能解决的问题 —— 策略 1 实测
留下 **9945 条未布线**（见 §5）。

## 3. 改了什么（只动 2 个文件）

### `engine/src/pitch_mod.v`（+11/−1）
新增输出 `poff_pre` = 限幅【之前】的 19 位和。`poff` 的公式、位宽、组合语义
**一字未改**（专项 TB 会在时钟边沿之间改 `rd_note` 并核对组合语义）。
端口不连接时不产生任何逻辑。

### `engine/src/tdm_engine_rh.v`（+90/−9）
1. **相位写回重定时**：时隙 s 的状态读一次、写一次，然后要等 **511 拍**才会被
   再读到。原设计把写回放在"读后第 1 拍"，把整条 pmod 链压进一个周期。
   现在拆成 2 拍（P1 采样 → P2 限幅/乘法/加法 → 写回），写回落点从
   "读后第 1 拍"变成"读后第 2 拍"，余量仍有 **509 拍**。
   - 只重定时 `phase_mem` 的写回。`tab_addr/tad2`（查表读侧）、
     env/stg/inc/amp/epar/gq/gcur 的写回、装载待生效区的消费全部保持原拍。
   - 写口仍留在主 always 块内、仍是"同块同钟无写使能"，与改动前形状一致，
     以保证 `phase_mem` 继续被推断成 RAM：综合日志仍是
     `Extracting RAM for identifier 'phase_mem'`，全设计 RAM 抽取条数 49
     （基线 49）。
2. **`increment_invalid` 改到累加入口**：原来它把 `amp2` 清零；现在改成
   `prod_g = p_invalid_d ? 0 : prod_ext`，在累加前把乘积清零。
   `prod4 = sin3 × amp3`，amp 为 0 时乘积本来就是 0 ⇒ 逐位等价，但把
   "乘法结果 → 越界判定 → amp2"这条 41 ns 的链从本拍移走。
   `p_invalid_d` 与 `prod4` 严格同拍（推导见代码注释）。
3. 限幅端点 `PMOD_CLAMP_LO/HI` 只在 `tdm_engine_rh` 定义一次，作为参数传给
   `pitch_mod` —— 避免两处常量漂移。
4. **`finger_held` 去复位循环**（M1-面积）：原来有一句
   `for(fi=0;fi<PGRP;fi=fi+1) finger_held[fi]<=0;`，它让 32×18 无法被推断成
   分布式 RAM（LUT RAM 没有复位端），退化成 576 个触发器 + 32:1×18 桶形选择器。
   去掉后综合日志出现 `Extracting RAM for identifier 'finger_held'`（RAM16 49→50），
   `u_tdm` 局部 LUT **−56**。安全性靠 `finger_held_active` 元数据门控
   （与 `pitch_mod` 的 `initialized[]` 同一套纪律），未初始化内容走不到数据通路。
5. **`first_slot` 宽 mux 修正**（M1-面积，实测 **−191 LUT**）：见 §6.1。
6. 写回地址由 `p_sl` 改为已有的 `sl2`（源码清理，网表无变化，见 §5.0.1）。

**代价（实测，全部改动累计）**：

| | 基线 | retime 单独（v1） | 全部改动（v3） |
|---|---:|---:|---:|
| Logic | 20338 | 20386（+48） | **20234（−104）** |
| CLS | 10346 | 10351（+5） | **10335（−11）** |
| Register | 10760 | 10857（+97） | 10880（+120） |
| BSRAM | 32 | 33（+1） | 33（+1） |
| DSP | 22.75 | 22.75 | 22.75 |

也就是说：**面积侧已经从"+50 LUT 进不去"变成"比基线还小 104 Logic"**，
但路由仍然失败（原因见 §5.0）。

## 4. 行为等价性证据（全部在本工作副本实跑）

| 套件 | 结果 | 说明 |
|---|---|---|
| native | PASS | 4 种深宽配置（NG=2/32/32/128，QW=8/18/20/20），各 2 万拍、78 次全地址扫描 |
| pitch | PASS | 4 配置 × 24 万拍，每个含 12 次复位；`poff` 与参考实现逐拍相同；交换读口反例仍被检出 |
| engine | PASS | 3 组黄金轨迹**逐字节相同**；`pcm_hash=29b53767` / `i2s_hash=5ef7bdeb` / `sensor pcm_hash=99cd9943` 在改动前后完全一致 |
| phase_wrap | PASS | 最大分频 + 两次回绕 |
| envelope | PASS | 5 万拍独立包络参考（在 retime 版本上跑过） |

最新一轮（含全部面积改动）为 `evidence/m1v4-*`：pitch / engine / phase_wrap / native
**四套件全部 PASS**，且 `pcm_hash`/`i2s_hash` 与前一轮逐字相同。
`suite-run.json` 的 `source_changed_from_bootstrap` 恰为
`engine/src/pitch_mod.v`、`engine/src/tdm_engine_rh.v` 两项。

## 5. 构建结果

| 构建 | 源 | Logic | CLS | Register | BSRAM | 结果 |
|---|---|---|---:|---:|---:|---:|---|
| `build_ref_v0`（对照，本机重跑基线） | 87 基线 | **20338** | **10346** | 10760 | 32 | **exit 0，路由完成** |
| `build_m1_v0`（3 级流水线） | v0 | 20575 | 10366 | 10891 | 33 | **DesRoute failed** |
| `build_m1_v1`（2 级流水线） | v1 | 20386 | 10351 | 10857 | 33 | **DesRoute failed** |
| `build_m1_v1_s1`（place/route option 1） | v1 | 20386 | 10351 | 10857 | 33 | **9945 条未布线** |
| `build_m1_v2`（+`finger_held` 改 RAM） | v2 | 20424 | 10359 | 10880 | 33 | **DesRoute failed** |
| `build_m1_v3`（+`first_slot` 宽 mux 修正） | v3 | **20234** | **10335** | 10880 | 33 | **DesRoute failed** |
| `build_m1_exp_nofinger`（**实验**：`FINGER_EXPR=0`） | v3 − 逐指表情 | **17957** | **10155** | 10020 | 33 | **exit 0，`PASS`（setup+hold 双清）** |
| `build_m1_exp_novis`（**实验**：关视觉化整块） | v3 − 视觉化 | 17545 | 10061 | 9232 | 26 | **exit 0，setup PASS / hold −0.050（1 端点）** |

### 5.0.0 实验构建 `build_m1_exp_nofinger`：本轮第一个 PASS

把 `left_layer_music_probe.v:81` 的 `FINGER_EXPR` 临时改成 `0`（测完已还原，文件 sha256 回到
`5451b95b…`），只为测量"腾出这块面积后时序能不能闭合"，**不是产品决定**：

| 指标 | 基线 | 实验构建 |
|---|---:|---:|
| Setup slack | −6.397 | **+1.258** |
| Hold / Recovery / Removal | −0.048 / +33.016 / +1.876 | +0.003 / +33.107 / +1.795 |
| TNS / 违例端点 | −355.644 ns / 186 | **0.000 ns / 0** |
| Fmax（约束 27.000） | 23.023 MHz | **27.949 MHz** |
| Logic / CLS | 20338 / 10346 | 17957 / **10155** |

三条结论（详见 `M1-AREA-OPTIONS.md`）：

1. **−6.397 ns 是可闭合的**，代价约 150 CLS；本次实际腾出 180 CLS，换回 7.655 ns
   ⇒ 斜率 **0.0425 ns/CLS**（与 10-14 历史点的 0.057 同量级）。
2. **关键路径换人了**：新的 16 条最差路径全是 `u_renderer/py_6_s1 → u_panel/held_pixel_*`；
   音乐引擎的 setup 路径跌出前 20（> +3.686），即从 −6.397 至少改善 10 ns。
   机制不是"少算 2211 个 LOGICeq"，而是 `u_finger`（1708 LUT + 809 FF）原本压在音乐布局区里，
   移走后 TDM 引擎与它的存储块得以紧凑放置。
3. ⇒ **重写 `finger_pitch` 单独不够**：乐观只能拿回 40–65 CLS，是所需 150 CLS 的 25%–40%，
   而且不触及当前关键路径。

### 5.0.1 第二个实验 `build_m1_exp_novis`：setup 更好，hold 差 50 ps

把 `rtl/sdram_stream_probe.v:78` 的 `music_visualizer` 例化换成常量驱动（测完已还原，
sha256 回到 `74b20865…`），同样只为测量：

| 指标 | 关逐指表情 | 关视觉化 |
|---|---:|---:|
| Logic / CLS / Register | 17957 / 10155 / 10020 | **17545 / 10061 / 9232** |
| Setup slack | +1.258 | **+1.367** |
| Setup TNS / 端点 | 0.000 / 0 | 0.000 / 0 |
| **Hold slack** | **+0.003** | **−0.050** |
| Hold TNS / 端点 | 0.000 / 0 | **−0.050 / 1** |
| 新关键 setup 路径 | `u_renderer → u_panel` | `layers/state_2_s1 → u_finger/offset[*]` |

**两条重要结论**：

1. **hold 一直在噪声底。** 三条构建的 hold 分别是 −0.048（基线）/ +0.003 / −0.050，
   其中两条违例都卡在 `scan_storage/hard_register[*] → panel/bank/*_q_10` 这同一结构上。
   **归档基线本来就是 −0.048 —— 这个项目从来没有过干净的 hold 签收。**
   ⇒ setup 修好之后，唯一剩下的阻碍是一个 50 ps、1 个端点的 hold 问题；
   它必须刻意修（一级流水/显式延迟），不能靠某次构建恰好 +0.003 就算过。
2. **在"关视觉化"配置里，`u_finger` 自己变成了关键路径**（`layers → offset[]` 的写数据路径）。
   所以重写 `finger_pitch` 的价值取决于选了哪条裁剪路线 —— 收益不稳定，不适合当主修法。

### 5.0 最重要的一条：可布线性不是由面积决定的

`build_m1_v3` 的 **Logic 比基线少 104、CLS 比基线少 11**，却仍然 `DesRoute failed`。
这直接推翻了本轮早期的判断（"CLS +5 就是墙"）：

> **基线在 10346 能布通，是布局运气；一个严格更小的设计同样可能布不通。**

变差的只有两处：Register +120、BSRAM +1（`u_tdm` 的 BSRAM 10→11，SDPB 19→20）。
起初怀疑 BSRAM +1 来自"写地址换成了另建的 `p_sl`"，但 §5.0.1 的实验否掉了这个解释
（改回 `sl2` 后网表逐项不变）。⇒ **BSRAM +1 与路由失败来自 retime 的数据通路改动本身，
目前尚未定位到具体是哪一块存储被拆分。**

**这条对 M1 的含义**：靠"改一点、试一次"推进是不可靠的 ——
必须先把面积压到有明显余量的位置（本次实测阈值在 10155 与 10335 之间），
否则每一次尝试都是在掷硬币，而且失败时拿不到任何时序数字。

**修正（2026-10-22 晚）**：CLS 与 LOGICeq 不是线性的——实验构建把 LOGICeq 降了 2211（−11%），
CLS 只降了 180（−1.7%），比例约 **12.3:1**。所以"腾 150 CLS"看起来只要降 1800 LOGICeq，
但那必须来自**同一布局区**的整块移除；分散的几百 LOGICeq 微调换不到几十 CLS。

### 5.0.1 一次被省掉的构建：`p_sl` → `sl2`

怀疑 BSRAM +1 来自"写地址换成了另建的 `p_sl`"，于是把写地址改回主 always 块里
已有的 `sl2`（`sl2 <= sl1`，且 `sl2(t) == sl1(t-1)`，逐位相同；`sl2` 在原始源码里
是**声明并赋值但从未被读**的死信号，被综合扫掉）。

结果：`synth_v4_sl2` 与 `synth_v3_gainmux` **逐项完全相同**（REG/ALU/LUT/SSRAM/LOGICeq 全 Δ=0）。
⇒ 综合器本来就把这两个等价寄存器合并了，这是**纯源码清理、对网表零影响**。
⇒ BSRAM 10→11 与路由失败**不是**写地址寄存器造成的，是 retime 的数据通路改动本身。

**方法论价值**：这次先跑 1 分 45 秒的综合、确认网表一模一样，
省掉了一次注定失败的 10 分钟构建。面积/结构问题应先过 `synth_area.py`。

### 5.1 对照构建证明了什么

`build_ref_v0` 是**未改动的 87 号源**，走同一个 `build_board.py`、同一个工具链，
在**另一台工作副本**（`fpga-m1-baseline-ref`）里重建。它把归档基线**逐项复现**：

| 指标 | 归档基线（`validation/archived-baseline-audit.json`） | `build_ref_v0`（本机） |
|---|---|---|
| Setup / Hold / Recovery / Removal | −6.397 / −0.048 / +33.016 / +1.876 | **完全相同** |
| 最差 setup 路径 | `sl1_5_s0/Q` → `phase_mem.../DI[23]`，到达 42.899 ns | **完全相同** |
| Logic / Register / CLS / BSRAM / DSP | 20338 / 10760 / 10346 / 32 / 22.75 | **完全相同** |
| 路由 | 完成 | 完成，exit 0，510.2 s |

⇒ 工具链与构建脚本在本机可复现。**因此后续所有候选的失败都不能归因于环境差异。**
（注意：这并不等于"失败可归因于候选面积变大"——§5.0 的 `build_m1_v3` 比基线更小，
同样失败。对照构建证明的是"工具链可信"，不是"面积是唯一变量"。）

## 5.2 为什么这条路径修不动：67% 是线延迟

把 `state/setup-critical-path.csv` 的 88 个节点按类型求和（本工作副本实算）：

| 组成 | 数值 | 占比 |
|---|---:|---:|
| 逻辑单元延迟（19 级 LUT + 2 条进位链） | 14.05 ns | 33% |
| **纯线延迟（`tNET`）** | **28.84 ns** | **67%** |
| 合计 | 42.89 ns | 100% |

而 28.84 ns 线延迟里，**25.1 ns 集中在 8 条线上**：

| 线延迟 | 扇出 | 落点 | 说明 |
|---:|---:|---|---|
| 5.128 | 1 | `u_pmod/n56_s1` | 分布式 RAM 输出 → 后续逻辑，跨 8 个列距 |
| 5.108 | 1 | `effective_poff_9_s2` | 加法器 → 限幅/选择，跨 6 个列距 |
| 3.891 | 2 | `final_inc_6_s` | **DSP 输出 → 增量加法器** |
| 2.559 | 4 | `physical_store/.../RAD[1]` | `sl1[5]`（扇出 180）→ RAM 地址，跨 22 行 |
| 2.542 | 54 | `pmod_mul_42_s0/A[9]` | 限幅结果 → **DSP 输入** |
| 2.428 | 2 | `ph_n_21_s` | 增量 → 相位加法器 |
| 1.758 | 1 | `gq_sel_1_s1` | 组选择 |
| 1.665 | 1 | `gq_sel_0_s42` | 组选择 |

**结论：这不是逻辑深度问题。** 进位链 16 级总共才 0.56 ns；19 级 LUT 全是
0.035–0.57 ns 的廉价级。真正的问题是这些单元被**撒在芯片两端**——
DSP 在 `DSP_R37`，周边算术在 `R22C34`/`R25C46`，分布式 RAM 在 `R33C37`，
起点寄存器在 `R11C32`。DSP 那一段（进 2.542 + DSP 出 3.760 + 出 3.891）
单独就占 **10.19 ns = 全路 24%**，其中 6.4 ns 是线。

成因是 **CLS 100% 占满**：布局器没有空余 CLS 可以拿来缩短连线，
只能把相连的单元摊在有空位的地方，于是每条线都绕远。

这也直接解释了 retime 为什么失败：**加流水线寄存器 = 加面积 = 布局器更没地方放
= 线更长**。在这个占满的器件上，retime 是反向操作。

## 5.3 25 条最差路径其实只有 2 条逻辑路径

从 `board_tr_content.html` 的 Path Slacks Table 提取全部 25 条：

- **起点 100% 是同一个节点**：`u_tdm/sl1_5_s0/Q`（扇出 180）
- 终点：13 条 → `phase_mem.../DI[*]`，12 条 → `amp2_*_s0/RESET`

所以 TNS −355.644 ns / 186 个端点**不是 186 个独立问题**，最差的那一批是
"一个寄存器位 → 两个目的地"按位切片重复计数。

同时 `board_tr_content.html` 的汇总说明违例域是单一的：

| 时钟 | Setup TNS | 端点 |
|---|---:|---:|
| `sys_clk` | 0.000 | 0 |
| `sdram_forward` | 0.000 | 0 |
| **`core_clk`** | **−355.644** | **186** |

`core_clk` 约束 27.000 MHz，实测 **Fmax 23.023 MHz**（逻辑级数 23）。
需要 1.173× 提速。

## 5.4 斜率：占用率每多 1 个 CLS，setup 掉约 0.057 ns

交接包 `docs/38`、`docs/39` 的版本流水里保存了同一器件、同一 27 MHz 下的历史
(Logic, CLS, slack) 三元组。把它们和本轮基线并排，第一次得到可用的斜率：

| 版本 | Logic | CLS | setup slack | 说明 |
|---|---:|---:|---:|---|
| 2026-10-14 `engine-safety-stage1` | 18796 | **10066** | **+9.643**，TNS 0 | 视觉化尚未并入 |
| 2026-10-19 86 号 | 20478 | 10357 | 无有效余量 | DesRoute / PR0004 |
| 2026-10-22 87 号（当前基线） | 20338 | **10346** | **−6.397** | 能路由 |

**CLS +280（Logic +1542）⇒ setup 从 +9.643 ns 掉到 −6.397 ns，共掉 16.04 ns。**
即约 **−0.057 ns / CLS**（−0.0104 ns / Logic）。

这条斜率有两个用处：
1. **证明"降面积能闭合时序"不是猜测**，而是这台器件上的实测规律；
2. **把"要腾多少"变成一个数**：要拿回 6.397 ns，需要腾出
   **约 110–150 CLS ≈ 250–300 Logic**。这也解释了为什么 10 号的建议目标
   "≤10250" 是对的（10066 时是 +9.6 ns，10250 时按斜率约 −1 ns 到 0）。
3. 同时说明**噪声带必须被跨过**：实测 ±10 CLS 的综合重排噪声对应 ±0.6 ns，
   而目标收益是 6.4 ns —— 所以改动必须一次砍 ≥250 Logic，否则量不出来。

## 6. 结论与下一步（重要：这改变了 88 号的阶段顺序）

88 号把 M1 写成"先修关键路径、同时测资源余量"。本轮的实测表明顺序必须反过来：

1. **先降面积，而且必须是"大块"降面积。**
   本轮试了两类面积改动，结论不同：
   - `finger_held` 去复位循环、恢复 RAM 推断：`u_tdm` **局部 LUT −56**、
     RAM16 +1（49→50），确实生效；但全局 LOGICeq **+40**，
     因为综合器同时把 `positions`(+97)、`u_finger`(+49)、`layers`(+35)
     重新铺了一遍，`slew` 反而 −123。
   - ⇒ **≤200 LUT 的局部改动会被 ±100 量级的全局重排噪声吃掉。**
     这个设计处在"噪声主导的局部最优"上，微调无效。
     要可测量的收益，必须一次性砍 ≥500 LUT。
2. **retime 本身是对的，但它不是杠杆。**
   本轮的 v1 改动行为已逐字节证明等价（5 个套件 PASS），代价仅 +50 LUT / +5 CLS；
   然而在 CLS 100% 的器件上加寄存器会**加剧**布局拥挤，把 5.128 ns 的绕行线变得更长。
   所以它必须建立在"已经腾出面积"之后，而不是之前。
3. **本轮实际拿到的面积成果（都已逐位证明等价）**：

   | 改动 | 综合 LUT | 等价性证据 | 风险 |
   |---|---:|---|---|
   | `first_slot` 宽 mux 修正（§6.1） | **−191** | pitch/engine/phase_wrap/native 四套件 PASS，`pcm_hash`/`i2s_hash` 与改前一致 | 无（可代数证明） |
   | `finger_held` 去复位循环、恢复 RAM 推断 | `u_tdm` −56（RAM16 49→50） | 同上 | 极低 |
   | retime（v1 主体） | +50 | 同上 + 三组黄金轨迹逐字节 | 低 |
   | **合计 vs 基线** | **Logic −104 / CLS −11** | | |

   但 **`build_m1_v3` 仍然 `DesRoute failed`**（见 §5.0）。

4. **还差多少、以及为什么微调无效。**
   历史斜率（§5.4）要求 CLS ≲10250，即再腾 **约 100–150 CLS ≈ 250–300 Logic**。
   而本轮实测的"综合重排噪声"是 ±10 CLS（±100 LUT）—— 目标收益必须显著大于它。
   已经找到并做掉的低风险来源（−191 −56）只够 1/3。
   **剩下的量级只能来自结构重写或功能取舍**，两者都需要先做决定：

   | 方向 | 预期收益 | 代价 / 风险 |
   |---|---:|---|
   | `finger_pitch.v` 的 32 路线性搜索（`owner[i]==finger`、`mine[g]`、`offset[i]` 三处逐元素比较） | ≈400–600 LUT ≈ 200–300 CLS | 需重写为"反查表 + 单地址比较"；涉及 allocator 复用与命令竞争语义（源码注释里明确打过这些竞态），风险高 |
   | 视觉化子树（`u_renderer`+`u_fft`+`u_wave`+`u_panel`+`u_spi`） | ≈2695 Logic ≈ 1350 CLS | 与音乐路径无关，但属产品功能取舍，**需用户决定** |
   | 接受当前状态，把 M1 结论定为"器件容量不足" | — | 诚实但放弃时序闭合 |

### 6.1 `first_slot` 宽 mux（可立即做，零行为风险）

```verilog
wire [PART*10-1:0]    gain_use = first_slot ? timbre_gain_q8    : gain_frame;   // 80 位 2:1
wire [NSLOT/PART-1:0] mask_use = first_slot ? timbre_voice_mask : mask_frame;   // 64 位 2:1
wire [9:0] raw_gain = gain_use[(sl1 % PART)*10 +: 10];
assign rh_amp_eff = mask_use[sl1/PART] ? boosted : amp_eff;
```

`first_slot` 就是 `sl1 == 0`，此时 `sl1 % PART == 0`、`sl1 / PART == 0`。
也就是说那两个宽 mux **在 `first_slot` 那一拍只用到第 0 片**，
剩下 70 位和 63 位是白送的组合逻辑。改成按片选：

```verilog
wire [9:0] raw_gain = first_slot ? timbre_gain_q8[9:0]
                                 : gain_frame[(sl1 % PART)*10 +: 10];
wire mask_bit = first_slot ? timbre_voice_mask[0] : mask_frame[sl1/PART];
assign rh_amp_eff = mask_bit ? boosted : amp_eff;
```

逐位等价：`first_slot` 时两边都取第 0 片；`!first_slot` 时两边都取 `frame` 的对应片。
静态估算省 70 + 63 = 133 LUT，**实测省 191 LUT**（`synth_v2` LUT 17305 → `synth_v3` 17114，
ALU +1 抵消 1 个），比估算更好 —— 因为省掉的宽 mux 同时也松开了布局拥挤。
而且 `mask_bit` 正好在 `amp2` 那条 −5.176 ns 路径上。

### 6.2 尚未做、但必须先回答的问题

**"腾出多少 CLS 才能闭合 −6.397 ns？"** 目前没有任何实测数据点回答它。
本轮拿到的唯一斜率信息是：基线 CLS 10346 能路由、10351 不能 —— 那是**可布线性**的墙，
不是时序的斜率。下一轮应做一次受控实验：在**未改动的 87 号源**上临时移除视觉化子树
（或其它整块），构建一次，得到 (CLS, slack) 的第二个数据点，
再据此决定是"砍 700 LUT"还是"换更大器件"。**这是产品决策的输入，不是 RTL 问题。**

## 7. 已排除的怀疑（省得下一轮重查）

| 怀疑 | 结论 | 证据 |
|---|---|---|
| `materialized_mem`（32×18 影子表）在浪费面积 | **已被扫掉**，不是浪费 | `impl/gwsynthesis/board.vg` 中 `grep -c materialized` = **0** |
| `gq[]` 调试影子数组在浪费面积 | 同上，随 `materialized_mem` 一起被扫掉 | 同上 |
| 综合目标频率设成 100 MHz 导致过度优化 | **不影响**：SDC 覆盖了全部端点，`-global_freq` 只作用于未被 SDC 覆盖的路径 | `board_tr_content.html` 里 sys_clk/sdram_forward 的 TNS 均为 0，全部违例都在 `core_clk` |
| 换 PnR 策略能救 | **不能**：`-place_option 1 -route_option 1` 直接 9945 条未布线 | `build_m1_v1_s1` |
| `pitch_mod` 两个 bank 合并成一个 RAM | **不可行**：合并会产生双写口数组，无法推断成 RAM | 源码注释 + `pitch_native_store` 的单写口结构 |

## 8. 未覆盖 / 边界

- 新流水线没有独立 TB。等价性由 engine 黄金轨迹（逐字节）+ pitch + phase_wrap 兜住。
- `pclr` 路径无测试（全工程接 `1'b0`）；重定时后 `pclr` 释放时会多写回一笔在途值，
  属未使用端口的已知偏差。
- `finger_held` 去复位后，**仿真**里未写过的项读到 X；它被 `finger_use` 门控
  （`eff_poff = fuse ? fing : poff`），X 不会传播到数据通路。硬件里 LUT RAM 初始为 0。
  三个回归套件（含 `sensor` 的 `moves=1` 与 `independent_pitch`）已实跑 PASS。
- 结构探针 `joint_timing_top` 仍 `bench_gate=false`，禁止下载。

## 9. 本轮新增的工具

`synth_area.py`（本工作副本根目录，**只跑综合，不布局不布线不生成比特流**）：

```powershell
python synth_area.py synth_<label> --ref synth_<previous>.json
```

面积只由综合决定，而完整 `build_board.py` 要 9 分钟（因为含 PnR）。
这个工具把面积迭代从 9 分钟降到 **1 分 43 秒**，并输出分模块 LUT/REG 增量表。
已验证它精确复现已知结果（`synth_v1_check` 对 `build_m1_v1`：REG/ALU/LUT/SSRAM 全部 Δ=0，
RAM16 提取数 49 一致）。

## 10. 复现命令

```powershell
# 基线（纯净副本）
python tools/run_checks.py --workspace D:/FPGA-Project/codex-builds/fpga-m1-baseline-ref --suite engine --run-id baseline01
# 候选回归
python tools/run_checks.py --workspace D:/FPGA-Project/codex-builds/fpga-m1-agent-work --suite pitch  --run-id m1v3
python tools/run_checks.py --workspace D:/FPGA-Project/codex-builds/fpga-m1-agent-work --suite engine --run-id m1v3
# 面积（快，1m43s）
cd D:/FPGA-Project/codex-builds/fpga-m1-agent-work
python synth_area.py synth_<label> --ref synth_cand_v1.json
# 完整构建（慢，~9min）
python build_board.py build_m1_v2 nominal 0
python tools/audit_build.py --workspace . --label build_m1_v2 --output evidence/m1v2-audit.json
```
