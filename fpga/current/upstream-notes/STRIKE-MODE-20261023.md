# 激发模式（strike / hybrid）落地 —— 2026-10-23 夜间

> 依据：`ARTICULATION-RUNTIME-SPEC-20261022.md`（下称"规格"）
> 用户授权：`在我睡觉这段时间里 你继续负责 FPGA 侧的代码实现 不着急合并 等我醒来之后我再进行验收`
> 分支状态：**未合并**，全部改动在 `codex-builds/fpga-m1-agent-work/`

---

## §0 一句话结论

**strike 已经进 RTL、进仿真、进综合布线，但上电默认 `artic_enable=0`。**
⇒ 现在烧进去，整机行为与改动前**逐位相同**（验收第 1 条）。
⇒ 主机写 `0x38 = 0x23` 就切到 strike，写回 `0x22` 就回 sustain。

---

## §1 改了哪些文件

| 文件 | 改动 | 为什么 |
|---|---|---|
| `engine/src/note_map_owned.v` | +8 个端口、+`REL_DIV_LOG2` 参数；梯度/余音计算；`ST_LOAD` 换 `p_epar_eff`/`env_eff`；自动释放计时器 + 到期注入 | 全部核心逻辑 |
| `engine/src/tdm_top_owned.v` | +寄存器抓取 0x38–0x3F；引导序列 +8 条；接到 `note_map_owned` | 寄存器通路 |
| `engine/src/reg_bank.v` | +`initial` 里 0x38–0x3F 的 8 个默认值 | 默认值的**可读来源** |
| `engine/src/reg_bank_compact.v` | `DEFAULTS` 常量重生成（含 0x38–0x3F） | 产品真正用的默认值 |
| `sim/tb_strike.v`（新） | 17 项判据，A–F 六组 | 见 §4.1 |
| `tools/gen_strike_vectors.py`（新） | 从 Python 侧算 160 组期望值 → `sim/strike_*.hex` | 规格 §6 第 8 条 |
| `tools/gen_compact_defaults.py`（新） | 从 `reg_bank.v` 生成 `DEFAULTS` | 消灭"两处默认值"这个坑 |
| `tools/run_sims.py` | +`tb_strike`；数据文件路径改为仓库相对；解码容错 | 一条命令跑全部 |
| `tools/board_velocity_check.py` | +`strike` 子命令 | 板上验证 |

---

## §2 寄存器地址：为什么是 0x38–0x3F

### 2.1 为什么挑这一段

地址空间盘点（`tdm_top_owned.v` 里所有 `wr_addr ==` / `R[8'hXX*8]`）：

```
已用：00-03 05 0F 30-37 40-49 50-54 58-5C 60-61 63-6F 70-73
只读：74-7C（遥测，reg_write 里显式屏蔽）
回显：7D 7E（0x6F/0x6E 的逻辑侧值）  7F（协议版本 0x11）
空闲：04 06-0E 10-2F 38-3F 55-57 5D-5F 62 72
```

`0x38–0x3F` 是空闲区里**连续 8 字节**的一段，正好装下 §5.3 的 A6 短命令负载
（`[0] flags / [1:2] mask / [3] d_m+curve / [4] base / [5:7] hold`），
将来实现 A6 时可以直接把这 8 字节连发到 `0x38..0x3F`，不必再转译。

### 2.2 位分配

```
0x38  [0] artic_enable   [1] strike_auto_rel   [7:4] strike_s_lvl
0x39  artic_mask[7:0]
0x3A  artic_mask[15:8]
0x3B  [1:0] strike_d_m   [5:2] strike_d_k_curve
0x3C  [4:0] strike_d_k_base
0x3D  strike_hold_ticks[7:0]
0x3E  strike_hold_ticks[15:8]
0x3F  [3:0] strike_hold_ticks[19:16]
```

### 2.3 为什么**不**走 `regs_flat`

`regs_flat` 的**每一个切片**都会综合出一棵 128:1 读 mux。这个设计贴着布线悬崖
（加遥测时未布线一度从 86 条涨到 187 条），多 8 个切片就是多 8 棵 mux。

所以走和 `0x66 PAD_SEL` 同一条路：**直接从写总线抓进专用寄存器**。

### 2.4 回读与生效值为什么必然一致

两条路吃的是**同一次写**：

```
wr_en/wr_addr/wr_data ──┬──> reg_bank_compact 的 mem[]      （回读用）
                        └──> tdm_top_owned 的专用寄存器      （逻辑用）
```

这正是 0x6F 那个坑的反面。当时的错法是"回读走 mem[]、逻辑走 regs_flat，
而 regs_flat 只镜像 `FLAT_MASK` 选中的字节" ⇒ 回读 0x05 全绿、逻辑恒 0。
这次两条路都由同一次写驱动，**不存在中间层**。

另外把 `DEFAULTS` 也补上了 0x38–0x3F（`tools/gen_compact_defaults.py` 生成），
所以**上电第一个周期**开始，回读值就等于专用寄存器的复位值。

---

## §3 三处 RTL 逻辑

### 3.1 梯度：`d_k(k) = base − (k·curve)>>4`

```verilog
wire [7:0]  k_curve_mul  = k * strike_d_k_curve;
wire [3:0]  k_curve_off  = k_curve_mul[7:4];
wire [4:0]  strike_d_k   = (strike_d_k_base > k_curve_off)
                         ? (strike_d_k_base - k_curve_off) : 5'd0;
```

**规格 §7.3 的头号风险（`k` 被综合成 16 份并行）不存在**：
`k` 在 `note_map_owned.v` 里是 `reg [$clog2(P)-1:0] k`（装载序列的计数器），
不是展开的常量。所以这里**只有一份 4×4 乘法器**。
综合结果也印证了：整个 strike 特性只让 Logic 涨了 1045（含 456 个 FF），
如果乘法器被展开 16 份，光乘法就要 16×15 ≈ 240 LUT 以上，远不止这个数。

### 3.2 余音：只给 `k < 4`

```verilog
wire [15:0] strike_s_lvl_q15 = {1'b0, strike_s_lvl, 11'd0};   // n*2048
wire        has_tail         = (k < 4) && (strike_s_lvl != 4'd0);
```

`k ≥ 4` 的泛音仍然衰减到无声 —— 真实钟的"嗡嗡"来自低次模态，高次是"叮"。
16 个泛音全留余音会变成"嗡嗡一片"，像加混响而不是钟。

**注意 `s_lvl=0` 和 `k≥4` 走的是同一个分支**（都给 0），所以两种情况下
`s_lvl` 字段的行为完全一致，不会出现"设 0 和设非零在 k≥4 上表现不同"。

### 3.3 env 词：只把 DEC 段的 shift 清零

```verilog
wire [39:0] env_eff = strike_sel ? {env_base[39:15], 4'd0, env_base[10:0]}
                                 : env_base;
```

`[14:11]` 是 DEC 段的 `shift`（`tdm_engine_rh.v:394`）。不清它，音色自带的
`d_shift` 会把衰减时长放大 `2^shift` 倍（最大 32768 倍）—— 340 ms 会变成 3 小时。

只清这 4 位，ATK/REL/custom/a_inc/r_m/r_k 全部原样。

> **这条在今天的构建里是"死路径"**：产品顶层 `OWNED_EVENTS=0` 且
> `CONFIG_SERIAL=0` ⇒ `owned_hold=0` ⇒ `env_base` 恒为 `40'd0`，
> 也就是 `load_env` 永远是全 0。逻辑仍然写对了（tb_strike 的 F 组专门测它），
> 因为一旦将来打开运行时音色表（`INSTRUMENT_ENV`），这条就是必需的。

### 3.4 自动释放：为什么不是 32 个 20 位倒计数器

**问题**：strike 的 `s_lvl` 会降到 0，而 `osc_env` 的判定是
`lvl <= s_lvl ⇒ ST_SUS` —— **电平到 0 后停在 SUS，不是 IDLE**。
于是"听不见，但状态机认为还在响"。占时隙的唯一依据是 `gact`，
`gact` 只由 note-on/note-off 驱动 ⇒ 按住 32 个 strike 音就把 512 个时隙占满，
第 33 个键**完全没声**。这是资源泄漏，不是音色问题。

**做法**：计时器到点后，把该组当"演奏者松手"处理 —— 走**和真实 note-off
完全相同的那条路径**（`ST_IDLE → ST_GLIDE(on_cur=0, match_r=1) → ST_LOAD`），
清 `gact`、`gtab=FREE`、16 个时隙写 `gate=0` ⇒ 引擎进 REL。
不直接清 `gact`，因为那样只是"标记为不响"，包络会停在当前电平，
下次复用时从旧电平起音 —— 会听到咔哒。

**成本控制**（这是本轮唯一一处为了面积改设计的地方）：

| 方案 | FF | 组合逻辑 | 结论 |
|---|---|---|---|
| 32 个 20 位倒计数器 | 640 | 32×(20 位减法 + 20 位零比较) ≈ 1280 LUT | 付不起（CLS 已 74%） |
| 32 个 20 位"到期时刻" + 32 个 20 位比较 | 640 | ≈ 640 LUT | 还是太大 |
| **32 个 10 位"到期格" + 32 个 10 位相等比较**（采用） | **352** | **≈ 350 LUT** | CLS 74%→80% |

采用的做法是"共享自由运行计数 + 每组存到期格"：

```verilog
localparam REL_W  = 20 - REL_DIV_LOG2;          // 10
localparam TDIV_W = 9 + REL_DIV_LOG2;           // 19（fs = clk/512）
wire       rel_tick = (rel_div == {TDIV_W{1'b1}});
assign rel_due[g]   = rel_arm[g] && (rel_exp[g] == rel_now);
```

**代价写清楚**：`strike_hold_ticks` 的低 10 位被舍去，
一格 = 1024 拍 = **19.42 ms**。方向是**向上取整**（`hold_cells` 最小取 1），
所以"请求 5 ms"会得到 19.42 ms，而不是"永不触发"。
默认值 79102 拍 ⇒ `[19:10] = 77` 格 ⇒ 实际 78848 拍 = **1.495 s**（请求 1.500 s，误差 0.34%）。

> 这类"静默截断"本项目栽过三次（EX3791 / EX2526 / 组号 4 位），
> 所以这里不是隐式截断，而是**显式写成参数 + 在 tb 的 B9 项里用算术核对产品配置**。

---

## §4 验证

### 4.1 仿真：6 个测试台全绿

```
python tools/run_sims.py
汇总: PASS (6/6)
```

| 测试台 | 判据 | 覆盖 |
|---|---|---|
| `tb_rst_gen` | 2 组 RESULT | 复位（本轮未动，回归） |
| `tb_beacon` | 2 组 RESULT | UART 心跳（本轮未动，回归） |
| `tb_pad_velocity` | 26 项 | 力度（本轮未动，回归） |
| `tb_vel_shape` | 13 项 | 力度→音色（本轮未动，回归） |
| `tb_pad_chain` | 4 项 | 电极→音符端到端（本轮未动，回归） |
| **`tb_strike`** | **17 项** | 本轮新增 |

`tb_strike` 的 17 项：

| 组 | 判据 | 内容 |
|---|---|---|
| **A** | 1 项（内部 160 项） | 160 组 `(base,curve,d_m,s_lvl,k)` 的 `d_k` / `s_lvl_q15` 与 **Python 侧逐位一致** |
| **B** | 1 项（内部 160 项） | 把 A 得到的 epar 灌进**真的 `osc_env`**，数拍到 `s_lvl` 的拍数，与 Python `exp_steps` 一致 |
| B9 | 1 项 | 产品配置（`REL_DIV_LOG2=10`）的时间常数算术核对：524288 拍/格、77 格、1.495 s |
| **C** | 2 项 | `enable=0` 时 16 个泛音的 epar 与 `preset_part.hex` **逐位相同**；且对照证明比的是真原值 |
| **D** | 3 项 | `mask=0` ≡ `enable=0`；`mask=0x0003` 只改 k=0,1；`s_lvl=0` 全部无余音 |
| **E** | 6 项 | 32 音占满 → 到点自动清零 → 第 33 音仍响；`auto_rel=0` 不回收；sustain 音不误伤；手动 note-off 立即回收 |
| **F** | 4 项 | 88 位音色词通过 `instrument_table` 校验；commit 后 `enabled` 置起；`enable=0` env 原样；`enable=1` 只清 DEC shift 4 位 |

A 和 B 是**跨语言闭环**：`>>4` 或"钳到 0"任一处写错，GUI 说 340 ms、
板子发 1.9 ms，而两边的单元测试各自都是绿的。这两项把它们钉在一起。

### 4.2 反向对照：证明判据有牙

| 故意改坏 | 结果 |
|---|---|
| `k_curve_off = k_curve_mul[7:4]` → `[7:3]`（`>>4` 写成 `>>3`） | **113 条 `[A]` 差异**，A/B 判据 FAIL |
| `has_tail = (k < 4)` → `(k < 8)` | **28 条 `[A]` 差异**，A/B 判据 FAIL |

两次都在改回后恢复全绿。

### 4.3 静态检查：3 个工具全绿

```
python tools/check_live_mask.py       → PASS（36 个地址全活，无 DEAD READ，tb 常量与 RTL 同步）
python tools/check_boot_contract.py   → PASS（AT RISK 无、MISMATCH 无）
python tools/gen_compact_defaults.py --check → 一致（29 个非零字节）
python tools/gen_strike_vectors.py --check   → 一致（160 条）
```

`check_boot_contract.py` 上一版会报 8 条 MISMATCH（0x38–0x3F 的
`initial=0x00` vs `引导=0x22`…）。本轮把 `reg_bank.v` 的 `initial` 和
`reg_bank_compact.v` 的 `DEFAULTS` 都补齐后归零 —— 顺带把"两处默认值"
这个长期风险变成了**生成关系**（`DEFAULTS` 由 `reg_bank.v` 生成）。

### 4.4 资源与时序（产品顶层，策略 1）

| 项 | `build_prod_v5`（改动前） | `build_strike_v1`（改动后） | Δ |
|---|---|---|---|
| Logic | 11612 / 20736 (56%) | 12657 / 20736 (**62%**) | +1045 |
| Register | 3824 / 15750 (25%) | 4280 / 15750 (28%) | +456 |
| **CLS** | 7622 / 10368 (74%) | 8275 / 10368 (**80%**) | +653 |
| BSRAM | 14 / 46 | 14 / 46 | 0 |
| DSP | 9.75 / 24 | 10 / 24 | +0.25 |
| Setup slack | +9.810 ns | **+11.858 ns** | 更好 |
| Hold slack | +0.205 ns | +0.205 ns | 0 |

**时序通过**（27 MHz 约束，setup 余量 11.858 ns ≈ 32% 周期）。

**CLS 从 74% 涨到 80%**，涨幅几乎全部来自 §3.4 的 32 组计时器
（352 FF + ~350 LUT）。这是为了让"第 33 个键不哑"付的钱，我认为值得；
如果后续功能需要更多余量，把 `REL_DIV_LOG2` 从 10 调到 11
（计时格 38.8 ms、误差 2.6%）能省约 64 CLS，再往上就只能牺牲精度了。

### 4.5 板级：**待你醒来跑**

本轮所有 RTL 都在仿真里验过，但**板级只做到"能编译、时序过"**，
还没有烧到板子上读寄存器。原因：`build_strike_v2` 是最后一份码流，
烧录需要一个明确的人工动作（且 Flash 里还留着 10-15 的旧固件，不想动它）。

你醒来后跑这两条即可：

```bash
# 1) 烧 SRAM（掉电即失，不动 Flash）
#    用 Gowin Programmer 打开 build_strike_v2/impl/pnr/board.fs，选 SRAM 下载

# 2) 读回 8 个字节 + 打印预测的 16 泛音表
python tools/board_velocity_check.py --port COM6 strike
```

期望输出（`strike` 子命令的第一段）：

```
0x38 = 0x22  期望 0x22  [OK ]     ← enable=0 / auto_rel=1 / s_lvl=2
0x39 = 0xFF  期望 0xFF  [OK ]
0x3A = 0xFF  期望 0xFF  [OK ]
0x3B = 0x2B  期望 0x2B  [OK ]     ← d_m=3, curve=10
0x3C = 0x0E  期望 0x0E  [OK ]     ← d_k_base=14
0x3D = 0xFE  期望 0xFE  [OK ]
0x3E = 0x34  期望 0x34  [OK ]
0x3F = 0x01  期望 0x01  [OK ]     ← hold = 79102 拍 = 1500 ms
```

它随后会写 `0x38=0x23` 打开 strike、打印预测的 16 泛音衰减表、再恢复成 `0x22`。

**听感验证（只有你能做）**：把 `0x38` 写成 `0x23` 后弹一下 —— 应该听到
"敲一下、低频拖尾、高频一瞬间就没"的钟/马林巴质感，而不是风琴。
再把 `0x39/0x3A` 写成 `0x00`（mask=0）应该立刻回到原来的风琴感。

---

## §5 怎么用

### 5.1 三种模式 = 同一个寄存器的三种取值（规格 §3.3）

| 模式 | `artic_enable` | `artic_mask` | 写什么 |
|---|---|---|---|
| sustain（上电默认） | 0 | 任意 | `0x38 = 0x22` |
| strike（全 16 泛音） | 1 | 0xFFFF | `0x38 = 0x23` |
| hybrid（前 3 保音高） | 1 | 0x0007 | `0x38 = 0x23` + `0x39=0x07, 0x3A=0x00` |

### 5.2 调音色的两个旋钮

- `0x3C d_k_base`：整体快慢。越大越慢（14 ≈ 340 ms 基频，10 ≈ 40 ms）。
- `0x3B[5:2] d_k_curve`：梯度强度。0 = 16 个泛音同步衰减（不像打击乐）；
  10 = 基频 262 ms / 第 16 泛音 1.9 ms，跨度约 140 倍。
- `0x38[7:4] s_lvl`：余音。0 = 马林巴（无余音）；2 = 钟（12.5%，默认）；4 以上已接近 sustain。

改完不用重启，**下一次按键**就生效；已经按住的音不受影响
（`epar_mem` 在 note-on 时已装载副本）。

### 5.3 时间预算

`0x3D–0x3F` 的 `hold_ticks` 决定"按住不放多久自动回收时隙"。
默认 1500 ms 是"有余音时留出尾巴"的值。改成 680 ms（`0x3D=0xA8, 0x3E=0x02, 0x3F=0x00`）
就是"无余音、衰减完就回收"，能省一半时隙。

---

## §6 已知限制 / 没做的

| 项 | 状态 | 说明 |
|---|---|---|
| `strike_hold_ticks` 低 10 位 | 被舍去 | 一格 19.42 ms；向上取整；误差 0.34%（1.5 s） |
| 自动释放的触发条件 | `artic_enable && mask != 0` | hybrid 只要有一个泛音是 strike 就会挂计时器 |
| 刷新（0x63 / 谱变化）时的 strike | **会重算** | 刷新是显式动作，会把当前 mask 重新应用到在响的音；与"改 mask 不影响已响音符"不冲突（那说的是不刷新） |
| UART 的 A6 短命令 | **未实现** | 现在只能用单字节写 `0x38–0x3F`（8 次）。规格 §5.3 的 10 字节包还没接 |
| `articulation_v2.compile_articulation` | 已有、自测全绿 | 但**没有接到**上位机 → 板子的通路上 |
| 双段衰减 | 未做 | 要扩 88 位词宽 |
| EEPROM 持久化 | 未做 | `24LC256` |
| 合并 | **按你的要求没做** | 全部在 `codex-builds/fpga-m1-agent-work/` |
| Flash | **仍是 10-15 的旧固件** | 刻意没覆盖（`tdm_live_test.fs`，460800） |

---

## §7 下一件可做的事（按依赖排序）

1. **你验收 + 试听** —— 决定 `base/curve/s_lvl` 的默认值是否要调
2. **A6 短命令** —— 演奏中切模式要低延迟，8 次单字节写 ≈ 2.8 ms，其实也够；
   真正的理由是让上位机一次发完，避免中间态（比如 mask 已改、enable 还没改）
3. **接 `compile_articulation` 到上位机** —— 音色文件里写 `articulation` 段，
   打开音色时自动把这 8 个字节写下去
4. 双段衰减 / EEPROM
