# 激发模式作为音符属性 —— 落地方案（2026-10-22）

> 目标：把「激发模式（sustain / strike / hybrid）」从**音色配置**里拿出来，变成**演奏时的音符属性**。
> 本文给出 RTL 改动点、寄存器位定义、配置模型 schema-2、编译器改动、迁移路径与验收清单。

---

## §0 一句话结论

**硬件代价很小（约 50 LUT + 45 寄存器），但「用偏移量继承音色衰减梯度」这条路实测不可行，必须用绝对参数。**
原因见 §1.2 —— 这是本轮新测出来的，推翻了我上一轮给的 `p_d_k - offset` 建议。

---

## §1 三个实测发现（先看这个，它改变了方案）

### 1.1 预设 1 不是「衰减很慢」，而是「掉 8.4% 然后不动」

```
preset1  s_lvl=30000 d_m=3 d_k=20 -> 2768 steps = 52.5 ms  (91.6% of 32768)
```

`d_k=20` 时 `(lvl×3)>>20 ≈ 0.09`，被 `max(1, …)` 钳成 1 —— 于是**每拍减 1**，从 32768 减到 30000 需要 2768 拍 = **52.5 ms**，然后停在 91.6%。

听感：起音后 52 毫秒内掉 8.4%，之后**完全静止**。这就是"加法合成听着像风琴、不像钢琴"的第一号原因，比之前判断的"衰减到 92% 所以不动"更准确 —— 它是**先快速掉一点再彻底不动**。

### 1.2 `d_k` 偏移方案在 `d_k ≥ 14` 时完全失效

`exp_steps` 有 32768 步的硬上限（`n > 32768 → raise`），而 `shift=0` 时每步最少减 1，所以**任何 `d_k ≥ 14` 都饱和在 621.4 ms**：

```
base d_k=20  off0:k20=621.4ms  off2:k18=621.4ms  off4:k16=621.4ms  off6:k14=340.0ms  off8:k12=122.5ms
base d_k=17  off0:k17=621.4ms  off2:k15=517.8ms  off4:k13=208.1ms  off6:k11= 70.4ms  off8:k 9= 22.1ms
base d_k=14  off0:k14=340.0ms  off2:k12=122.5ms  off4:k10= 39.7ms  off6:k 8= 12.1ms  off8:k 6=  3.5ms
```

四个预设 `d_k` 全在 10–20 区间，**偏移量要 ≥ 6 才开始起作用**；而偏移 6 之后不同音色的结果从 340 ms 到 0.9 ms，跨度 380 倍，根本没法用一个全局旋钮控制。

**结论：strike 的 `d_k` 不能是"在音色 `d_k` 上减多少"。**

> ⚠️ **这里要澄清一个说法**：上一版写"必须用绝对参数"，容易被读成"16 个泛音全用同一个 `d_k`"——那是错的，也和你说的"应该做梯度"矛盾。
> 准确的意思是：**基准值不继承音色**，但**每泛音的差异由序号 `k` 生成**（§2.3）。两者不冲突。
>
> 而且偏移方案失败不只是**数值饱和**，**语义也是错的**：`d_k` 的差异在音色里代表"这个音色的高次泛音比基频衰减快多少"（音色选择），而 strike 的梯度代表"模态阻尼随阶次增加"（物理规律）。用前者去派生后者，等于让音色的设计偏好改写物理规律，方向从一开始就反了。见 §1.4。

### 1.3 `shift` 只在 `custom=1` 时生效

`tdm_engine_rh.v:392-396` 原文：

```verilog
wire [3:0] shift = (stg1==1) ? eff_env[34:31]      // ATK
                 : (stg1==2) ? eff_env[14:11]      // DEC
                 : (stg1==4) ? eff_env[10:7]       // REL
                 : 4'd0;
wire [14:0] mask  = ~(15'h7fff << shift);
wire tick         = (phase_read & mask) == 0;
wire hold_level   = custom && !tick && !trig_on && !trig_rel;
assign env_n = hold_level ? env1 : env_calc;
```

`custom` 就是 `eff_env[35]`。**`custom=0` ⇒ `hold_level` 恒 0 ⇒ 每拍都推进 ⇒ `shift` 完全不起作用。**

两条路径的实际差别：

| 路径 | `env` 来源 | `custom` | 可用参数 | 最长衰减（shift=0） |
|---|---|---|---|---|
| 预设表 `preset_part.hex` | `load_env <= 40'd0` | 恒 0 | 只有 `s_lvl`/`d_m`/`d_k` | 621 ms |
| 运行时表 88 位词 | `[87:48]` 40 位 | 由 `[35]` 决定 | 加 `a_inc`/`a_shift`/`d_shift`/`r_m`/`r_k`/`r_shift` | `621 ms × 2^shift`（shift≤15） |

这解释了为什么 `config_adapter.py::fit_exp` 要搜 `shift` —— 它编译的是运行时表路径，`custom=1`，`shift` 有效。而 `preset_part.hex` 路径恒 `shift=0`，只能靠 `d_k` 调速度，上限 621 ms。

### 1.4 泛音结构与激发方式是**耦合**的（这条决定梯度按什么排序）

你的判断是对的：泛音结构同时影响音色和激发方式的效果。

| 泛音结构的哪一面 | 影响音色 | 影响激发方式 |
|---|---|---|
| 有哪些泛音（`ratio`） | 决定谐波/非谐、明亮度、金属感 | 决定"能不能听出衰减差异" |
| 各泛音幅度（`amp`） | 决定频谱重心 | 决定"衰减梯度是否可闻" |
| 泛音数量（有效非零个数） | 决定厚度 | 决定梯度跨度：只有 3 个泛音时，梯度几乎无从展开 |

所以**不能把两者当正交**。但实现上必须选一个"谁提供什么"的切法：

```
音色（88 位词）  →  ratio、amp            （静态：频谱长什么样）
激发方式（寄存器）→  s_lvl、衰减速率       （时间：频谱怎么演化）
```

**关键推论：梯度必须按泛音序号 `k` 排序，不能按音色的 `d_k` 排序。**

理由：高次泛音衰减更快是**模态阻尼**的物理规律，与具体音色无关。用序号 `k` 做梯度还有个好处——它天然自适应泛音结构：一个只有 3 个泛音的音色，`k` 只到 2，梯度自然收敛到很小，不会出现"给不存在的泛音分配衰减速率"这种荒谬情况。

这正是上一版偏移方案的第二个错误：它让"音色设计者的选择"去决定"物理规律该多强"。

---

## §2 硬件方案

### 2.1 设计原则

| 项 | 决定 | 理由 |
|---|---|---|
| 音色表存几套包络 | **1 套**（sustain 版） | 88 位词放不下第二套 23 位 epar + 4 位 shift |
| strike 参数放哪 | **寄存器（演奏态）** | 用户原话：不跟音色绑定、是全局性的音符属性 |
| strike 的 `d_k` 基准 | **绝对值，不继承音色** | §1.2：偏移在 `d_k≥14` 时饱和 |
| strike 的每泛音差异 | **按序号 `k` 生成梯度** | §1.4：物理规律，且自适应泛音数量 |
| strike 的 `shift` | **强制 0，不占寄存器** | strike 要短；`d_k=1,shift=0` 已达 0.3 ms，够短 |
| strike 的 `s_lvl` | **固定 0，不占寄存器** | 打击乐衰减到无声是定义，不需要可调 |
| 生效时机 | **note-on 时捕获** | `epar_mem[0:NSLOT-1]` 每时隙一份，装载后该音符持有副本；改寄存器不影响已响的音符 |
| 与 `hybrid` 的关系 | `hybrid` = `artic_mask` 的一个取值 | 不再是音色属性，见 §3.3 |

### 2.2 寄存器定义（共 53 位）

```
artic_enable            1 bit    0 = 全部走音色自带 epar（向后兼容）
artic_mask[15:0]       16 bit    1 = 该泛音用 strike 版
strike_d_m[1:0]         2 bit    1–3（0 非法，与校验规则一致）
strike_d_k_base[4:0]    5 bit    基频（k=0）的 d_k，0–31
strike_d_k_curve[3:0]   4 bit    梯度强度，0–15
strike_s_lvl[3:0]       4 bit    余音电平，n/16 满幅；只作用于 k<4（见 §2.7）
strike_auto_rel         1 bit    1 = strike 音自动限时释放（见 §2.6）
strike_hold_ticks[19:0] 20 bit   自动释放时长，按拍计（fs=52734.375）
                     ─────
                       53 bit
```

两处相对上一版的修正：

| 字段 | 上一版 | 现在 | 原因 |
|---|---|---|---|
| `strike_hold_ms` | 16 位 | **20 位** | 16 位只有 **1243 ms**，装不下 1.5 s 的余音尾巴。实测踩到：请求 1500 ms 被截到 1243 ms |
| `strike_s_lvl` | 无 | **4 位** | Q3 决定加余音，见 §2.7 |

`strike_d_shift` 已在上一轮换成 `strike_d_k_curve`（strike 的 `shift` 固定 0）。

### 2.3 梯度公式与实测效果

```verilog
// 每泛音的 strike d_k：基准减去按序号递增的量，钳到 0
wire [3:0] k_curve_off = (k * strike_d_k_curve) >> 4;        // 0..14
wire [4:0] strike_d_k  = (strike_d_k_base > k_curve_off)
                       ? strike_d_k_base - k_curve_off
                       : 5'd0;
```

`k` 是 0–15 的泛音序号（`P=16`）。`>>4` 相当于"第 16 个泛音减 `curve`"，所以 `curve` 就是**整个 16 泛音跨度上的总降幅**，直观可调。

实测（`d_m=3, shift=0`）：

```
base=14 curve= 8 | k00:340.0ms  k03:208.1ms  k06:70.4ms  k09:39.7ms  k12:12.1ms  k15: 6.6ms
base=14 curve=12 | k00:340.0ms  k03:122.5ms  k06:39.7ms  k09:12.1ms  k12: 1.9ms  k15: 0.5ms
base=12 curve= 8 | k00:122.5ms  k03: 70.4ms  k06:22.1ms  k09:12.1ms  k12: 3.5ms  k15: 1.9ms
base=10 curve= 8 | k00: 39.7ms  k03: 22.1ms  k06: 6.6ms  k09: 3.5ms  k12: 0.9ms  k15: 0.5ms
```

`base=14, curve=10` 的完整 16 泛音表（**推荐默认值**）：

```
k= 0  d_k=14  340.0 ms      k= 8  d_k= 9   22.1 ms
k= 1  d_k=14  340.0 ms      k= 9  d_k= 9   22.1 ms
k= 2  d_k=13  208.1 ms      k=10  d_k= 8   12.1 ms
k= 3  d_k=13  208.1 ms      k=11  d_k= 8   12.1 ms
k= 4  d_k=12  122.5 ms      k=12  d_k= 7    6.6 ms
k= 5  d_k=11   70.4 ms      k=13  d_k= 6    3.5 ms
k= 6  d_k=11   70.4 ms      k=14  d_k= 6    3.5 ms
k= 7  d_k=10   39.7 ms      k=15  d_k= 5    1.9 ms
```

基频 340 ms、第 16 泛音 1.9 ms，**跨度 183 倍**。这就是钟/马林巴的频谱演化：低频拖尾、高频一瞬间就没了。

### 2.3.1 Q1 的结论：不做硬件自适应，改成上位机查表

你选了"curve 随泛音数量自适应（+10 LUT）"。实测下来**这个补丁不该做**，原因不是面积，是它会帮倒忙。

先看固定 `curve=10` 时，不同泛音数下"最高泛音相对基频"的衰减倍率：

```
泛音数= 2  →  倍率   1.0     泛音数= 8  →  倍率   8.6
泛音数= 4  →  倍率   1.6     泛音数=12  →  倍率  28.1
                              泛音数=16  →  倍率 183.0
```

看起来"泛音少的梯度太弱"，于是自然会想到按泛音数归一化。我试了两种归一化：

| 方案 | 2 泛音 | 4 泛音 | 8 泛音 | 16 泛音 |
|---|---|---|---|---|
| 固定 curve=10 | 1.0× | 1.6× | 8.6× | 183× |
| `curve*16/(span+1)` | 15× | **52×** | **96×** | 183× |
| `>>clog2(span+1)` | 15× | **52×** | **96×** | 183× |

**4 泛音时倍率从 1.6 跳到 52** —— 第 4 个泛音 6.6 ms 就没了，听起来只剩一根正弦，比原来更不像打击乐。而物理上，马林巴的第 4 个模态阻尼只有基频的 3–5 倍，不是 52 倍。

**结论：泛音少的音色梯度弱，是物理正确的。** 归一化等于把"这个音色做不出打击感"这个真问题，伪装成"梯度不够强"。

正确做法是**让 `curve` 的默认值随泛音数变**，而不是改归一化公式：

```python
def default_curve(span):          # span = 最高有效泛音序号
    return max(0, min(15, round(112.0 / (span + 1))))
```

实测这个公式与逐点反解的最优值吻合（`span=7→14, 11→9, 15→7`），**0 LUT，纯上位机**。已在 `articulation_v2.py::default_curve` 实现并测试。

一个数学限制要记住：**泛音数 ≤ 2 时梯度恒为 0**（`(1*15)>>4 = 0`），因为 2 个泛音本来也谈不上"频谱演化"。

### 2.4 RTL 改动：只有 3 处

**位置 1 —— `note_map_owned.v` 端口列表**

```verilog
input              artic_enable,
input  [15:0]      artic_mask,
input  [1:0]       strike_d_m,
input  [4:0]       strike_d_k_base,
input  [3:0]       strike_d_k_curve,
input  [3:0]       strike_s_lvl,        // 余音电平 n/16，见 §2.7
```

**位置 2 —— `note_map_owned.v` 字段切片后（约 `:442` 之后）**

```verilog
// ── 激发模式：音符属性覆盖（不影响已响的音符，只在 note-on 装载时生效）
wire strike_sel = artic_enable & artic_mask[k];

// 按序号 k 生成梯度：高次泛音衰减更快（模态阻尼，§1.4）
wire [3:0] k_curve_off = (k * strike_d_k_curve) >> 4;
wire [4:0] strike_d_k  = (strike_d_k_base > k_curve_off)
                       ? strike_d_k_base - k_curve_off
                       : 5'd0;

// 余音：只给前 4 个泛音，高次仍然衰减到无声（§2.7）
wire [15:0] strike_s_lvl_q15 = strike_s_lvl << 11;          // n*2048
wire        has_tail         = (k < 4) && (strike_s_lvl != 0);
wire [15:0] p_s_lvl_eff      = has_tail ? strike_s_lvl_q15 : 16'd0;

wire [22:0] p_epar_eff = strike_sel ? {p_s_lvl_eff, strike_d_m, strike_d_k}
                                    : p_epar;
```

**位置 3 —— `note_map_owned.v` `ST_LOAD` 段（`:684` 附近）**

```verilog
// 原：
//   load_epar <= p_epar;
//   load_env  <= ((owned_hold||SERIAL_CUSTOM_LEGACY)&&!rf_mode&&custom_hold)
//                ? custom_entry[87:48] : 40'd0;
//
// 改：
wire [39:0] env_base = ((owned_hold||SERIAL_CUSTOM_LEGACY)&&!rf_mode&&custom_hold)
                     ? custom_entry[87:48] : 40'd0;
// strike 强制 shift=0（否则音色的 d_shift 会把 strike 时长放大 2^shift 倍）
wire [39:0] env_eff  = strike_sel
                     ? {env_base[39:15], 4'd0, env_base[10:0]}
                     : env_base;

load_epar <= p_epar_eff;
load_env  <= env_eff;
```

### 2.5 面积估算：加了梯度，只多 20 LUT

| 项 | 估算 | 依据 |
|---|---|---|
| 23 位 2:1 mux | ≈ 23 LUT | 1 LUT/位 |
| 40 位 2:1 mux（实际只动 4 位） | ≈ 4 LUT | 只有 `[14:11]` 变化 |
| **梯度乘法 `k × curve`** | **≈ 15 LUT** | 4×4 位，`k` 只到 15 而 `curve` 只到 15 |
| 减法 + 钳位 | ≈ 6 LUT | 5 位比较 + 5 位减法 |
| **余音选择（`k<4` + 16 位 mux）** | **≈ 5 LUT** | 4 位比较 + 2:1 选择 |
| 寄存器 | 53 FF | §2.2 |
| 总线/译码（挂到现有配置寄存器组） | ≈ 20 LUT | 与 `spec_*` 同风格 |
| **合计** | **≈ 73 LUT / 53 FF** | |

对比上一版（无梯度）的 50 LUT，**梯度 + 余音一共多 23 LUT**。在 CLS 余量 41 格的背景下这不算轻松，但也不至于过不去——真正的风险是：`k` 若被综合器展开成 16 份并行，梯度乘法会变成 16 份。

> **必做的验证**：综合后看 `note_map_owned` 的 LUT 增量。若远大于 73，说明 `k` 被展开了，此时把 `k_curve_off` 改成**在 note-on 时算一次存进寄存器**（每组 4 位 × 32 组 = 128 FF），用寄存器换 LUT。见 §6 验收第 3 条。

### 2.6 `strike_auto_rel` 是什么

**一句话：它不改变音色，它回收时隙。**

拆成三步看。

**第一步：什么叫 release（释放）**

包络有五个状态：`IDLE → ATK → DEC → SUS → REL → IDLE`。`SUS` 是"按住不放时的保持电平"，`REL` 是"松手后从当前电平降到 0"。

在真实乐器上，`note-off` 对应：钢琴松手 → 制音器落下 → 声音停。马林巴没这回事，敲完自己就没了，按不按键都一样。

**第二步：strike 模式下不松手会发生什么**

strike 的 `s_lvl = 0`，所以 `DEC` 段会一路把电平减到 0。到 0 时 `osc_env.v` 的判定是：

```verilog
else if (lvl_i <= s_lvl) begin lvl_o = s_lvl; stg_o = ST_SUS; end
```

`lvl=0 <= s_lvl=0` ⇒ **停在 `ST_SUS`**，不是 `ST_IDLE`。

于是出现一个荒谬状态：**听不见，但状态机认为这个音还在响**。而"这个音还占着时隙"的唯一依据是 `gact`：

```verilog
reg [NG-1:0] gact;              // note_map_owned.v:227，该组是否正在发声（gate=1）
assign active = gact & gact_q;  // :247
if (!found_free && !gact[n])    // :331，找空闲组时只看 gact
```

`gact` **只由 note-on / note-off 驱动**，包络归零不会清它。所以：

```
按住 32 个 strike 音 → 32 组 × 16 泛音 = 512 时隙 = NSLOT → 复音数归零
第 33 个键按下去，没有任何声音，因为一个空闲时隙都没有了
```

而实际上前 32 个音早就静音了。**这是资源泄漏，不是音色问题。**

**第三步：`auto_release` 做什么**

在 strike 音装载时启动一个 **20 位**倒计数器（初值 `strike_hold_ticks`），减到 0 时**由 `note_map` 主动把该组 `gact` 清 0**，等价于"替演奏者松手"。

```verilog
// 判定条件：artic_enable & strike_sel & strike_auto_rel
// 倒计时初值取 strike_hold_ticks（20 位，约 19.9 s 上限）
```

> **为什么是 20 位而不是 16 位**：16 位最多 65535 拍 = **1243 ms**。加了余音之后 `hold` 默认要 1500 ms（79102 拍），会被静默截断到 1243 ms —— 实测踩过这个坑，`articulation_v2.py` 的自测第 5 组就是为它写的。

**为什么叫"自动释放"而不是"自动停止"**：它走的是 note-off 同一条路径（清 `gact`、进 `REL`），不是强行把电平清零。所以不会有咔哒声。

**副作用与取值**

| `strike_hold_ticks` 取值 | 效果 |
|---|---|
| 太短（< 衰减时长） | 声音还在响就被截断，能听到不自然的断口 |
| **有余音时 ≥ 1500 ms（推荐）** | 截断点落在尾巴自然消失的位置 |
| **无余音时 = 2 × 基频衰减（680 ms）** | 声音早就没了，只是回收时隙 |
| 太长 | 回收不及时，长按时仍会吃满时隙 |
| 关闭（`strike_auto_rel=0`） | 物理上最"诚实"（敲一下就是一下），但用户按住不放会吃满时隙 |

默认值由编译器自动定（`articulation_v2.py::compile_articulation`）：

```python
if s["s_lvl"] > 0:
    hold_ms = max(1500.0, 3.0 * base_ms)   # 有余音：留出尾巴
else:
    hold_ms = 2.0 * base_ms                # 无余音：衰减完就回收
```

如果用户嫌"按住 1.5 秒就断"，说明他在用长按做特殊演奏——那应该把 `artic_mask` 设成全 0（即 sustain 模式），而不是关掉 `auto_release`。

### 2.7 Q3：余音感要不要加 —— 加，而且它不额外占时隙

先回答你的反问：**"是否要加入真实乐器中的余音感"** 这件事有一个反直觉的结论。

**关键事实：一个音固定占 16 个时隙，不管几个泛音在响。**

`PART=16`，note-on 时分配 16 个连续时隙，`gact=1` 期间一直占着。所以：

- 16 个泛音全衰减到 0 → 占 16 个时隙
- 只有 2 个泛音留余音 → **还是占 16 个时隙**

**余音不增加时隙占用。** 真正决定占用时长的是 `strike_hold_ticks`，跟 `s_lvl` 无关。

所以"加余音"的代价只有一处：**为了让余音可闻，必须把 `hold` 从 680 ms 拉到 1500 ms 以上**，于是每个 strike 音多占 0.8 秒的时隙。按每秒按 4 个音算，同时最多 6 个音在响 → 96 时隙，在 512 里完全够。

**实现：`strike_s_lvl[3:0]`，只作用于 k < 4**

```
s_lvl = n * 32768 / 16        n = 0..15
n=0 → 0%（无余音）      n=2 → 12.5%（默认）      n=4 → 25%
```

只给前 4 个泛音留余音，因为：

1. 真实钟的"嗡嗡"来自低次模态，高次是"叮"（一瞬间就没）
2. 如果 16 个泛音全留余音，听感是"嗡嗡一片"，像加了混响而不是钟

```verilog
wire [15:0] strike_s_lvl_q15 = strike_s_lvl << 11;      // n/16 * 32768 = n*2048
wire        has_tail         = (k < 4) && (strike_s_lvl != 0);
wire [22:0] p_epar_eff = strike_sel
                       ? {has_tail ? strike_s_lvl_q15 : 16'd0, strike_d_m, strike_d_k}
                       : p_epar;
```

成本：**4 FF + 约 4 LUT**（一个 4 位比较 + 一个 16 位选择）。比梯度便宜得多。

**听感对比**（`base=14, curve=10, hold=1500ms`）：

| `s_lvl` | 听感 |
|---|---|
| 0 | 敲一下，340 ms 后彻底静音。像马林巴/木琴 |
| 2（12.5%） | 前 4 个泛音衰减到 12.5% 后悬停，形成一个很轻的"嗡"，1.5 s 后被 `auto_release` 切断。像钟/音叉 |
| 4（25%） | 余音太明显，已经接近 sustain 模式，失去打击感 |

**建议默认 2。** 想纯打击感就把 `s_lvl` 设 0，此时 `hold` 自动降回 680 ms。

---

## §3 配置模型 schema-2

### 3.1 现状的问题

`instrument_config.py:31-38` 现在长这样：

```python
"articulation": {
    "mode": mode,                       # ← 演奏属性，却存在音色文件里
    "attack_ms": 5,
    "decay_ms": 300,
    "sustain_level": 192,
    "release_ms": 200,
    "hybrid_parts": ["sustain"]*8 + ["strike"]*8,   # ← 演奏属性，却存在音色文件里
},
```

`config_adapter.py:74` 在**编译期**把 `hybrid_parts[i]` 展开进 88 位词：

```python
mode = art['hybrid_parts'][i] if art['mode']=='hybrid' else art['mode']
sustain = 0 if mode=='strike' else round(art['sustain_level']*32768/255)
decay = fit_exp(art['decay_ms'], sustain)
```

**这跟"激发模式是音符属性"直接冲突**：编译时不知道演奏者会按哪个键，一旦把 `strike` 烘进词里，这个音色就永远是那个分组了。

### 3.2 新结构

```json
{
  "schema_version": 2,
  "name": "钟琴 A",
  "preset": 0,
  "spectrum_mode": "replace",
  "spectrum": [255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],

  "tone": {
    "attack_ms": 5,
    "decay_ms": 1200,
    "sustain_level": 192,
    "release_ms": 200
  },

  "articulation": {
    "mode": "hybrid",
    "strike": {
      "d_m": 3,
      "d_k_base": 14,
      "d_k_curve": null,
      "s_lvl": 2
    },
    "hybrid_parts": ["sustain","sustain","sustain",
                     "strike","strike","strike","strike","strike",
                     "strike","strike","strike","strike","strike",
                     "strike","strike","strike"],
    "auto_release": true,
    "auto_release_ms": null
  },

  "vibrato": {"enabled": false, "rate_millihz": 5500, "depth_cents": 0},
  "effects": {
    "dry_enabled": true,
    "delay":  {"enabled": false, "time_ms": 30, "feedback_q8": 96},
    "chorus": {"enabled": false, "rate_millihz": 500, "depth_ms": 1},
    "reverb": {"enabled": false, "feedback_q8": 128, "damping": 3}
  }
}
```

关键变化：

1. **`tone` 与 `articulation` 分开**。`tone` 是音色（进 88 位词），`articulation` 是演奏属性（进寄存器）。
2. **`decay_ms` 从 300 提到 1200**。默认 300 ms 是"风琴感"的主要来源之一；钟/钢琴的基频衰减在 1–3 秒量级。这是**听感改善最直接的一个数字**，跟激发模式无关，建议一并改。
3. **`strike` 用 `d_k_base` + `d_k_curve` 两个旋钮**，不继承音色的 `d_k`（§1.2）。`d_k_curve` 就是梯度强度，0 = 16 个泛音同步衰减。
4. **`strike.decay_ms` 不再直接暴露**。因为 `(base, curve, m)` 已经唯一确定每泛音的时长，再给一个 `decay_ms` 会自相矛盾。GUI 想给"打击衰减 80ms"这种直观输入，由上位机反解 `base`（`solve_dk_base`，curve 固定），**编译期反解，不落进文件**。
5. **`strike.s_lvl` = 余音电平**，0 = 无余音（马林巴），2 = 12.5%（钟）。只作用于前 4 个泛音（§2.7）。
6. **`hybrid_parts` 默认前 3 sustain + 后 13 strike**（Q2 决定）。它只是 `artic_mask` 的一个预设值，演奏中可以整体换掉。
7. **`auto_release_ms: null`** = 让编译器按衰减时长自动定（有余音时 `max(1500, 3×基频)`，无余音时 `2×基频`）。填数字则强制覆盖。

### 3.3 三种模式 = 同一个寄存器的三种取值

| 模式 | `artic_enable` | `artic_mask` |
|---|---|---|
| `sustain` | 0 | 任意（被忽略） |
| `strike` | 1 | `16'hFFFF` |
| `hybrid` | 1 | 由 `hybrid_parts` 编码 |

`hybrid_parts` 编码：`mask[i] = (hybrid_parts[i] == "strike")`。

**注意 `sustain` 用 `artic_enable=0` 而不是 `mask=0`**：`enable=0` 时 RTL 走 `p_epar` 原值，逐位等于改动前，保证行为等价性回归可过。

### 3.4 演奏中的实时切换

`artic_mask` 是普通寄存器，写一次立即影响**之后触发的音符**，已响的音符因为 `epar_mem` 已装载副本而不受影响。这正是用户要的语义。

上位机侧只需一个 16 位掩码控件（16 个复选框）或三个按钮（全 sustain / 全 strike / 前后 8 分）。

---

## §4 编译器改动（`config_adapter.py`）

### 4.1 `compile_tone` 只编 `tone`

```python
def compile_tone(document, preset_words=None):
    doc = validate_config(document)          # schema-2 校验
    tone = doc["tone"]                       # ← 只读 tone，不读 articulation
    attack  = fit_attack(tone["attack_ms"])
    release = fit_exp(tone["release_ms"], 100)
    sustain = round(tone["sustain_level"] * EPAR_FULL / 255)
    decay   = fit_exp(tone["decay_ms"], sustain)
    parts = []
    for i in range(PART):
        base = preset_words[doc["preset"] * PART + i]
        amp  = doc["spectrum"][i] if doc["spectrum_mode"] == "replace" \
               else min(255, doc["spectrum"][i] + ((base >> 24) & 255))
        parts.append(dict(
            ratio_q8=(base >> 32) & 65535, amplitude=amp,
            sustain_q15=sustain,
            decay_m=decay["m"], decay_k=decay["k"], decay_shift=decay["shift"],
            attack_inc=attack["inc"], attack_shift=attack["shift"],
            release_m=release["m"], release_k=release["k"],
            release_shift=release["shift"]))
    return encode(parts), {...}
```

**16 个泛音的 `s_lvl` 全部相同**（都等于 `sustain_level`），不再有 `strike` 的 0。`decay` 也全局一份——泛音间的衰减差异现在由 `strike.d_k_curve` 在运行时生成，不再烘进音色。

### 4.2 新增 `compile_articulation` 产出寄存器值

**完整可运行版本在 `articulation_v2.py::compile_articulation`**，自测覆盖。这里只列关键逻辑：

```python
def compile_articulation(document):
    doc = validate_config(document)
    a = doc["articulation"]
    mode = a["mode"]
    if mode == "sustain":
        enable, mask = 0, 0x0000
    elif mode == "strike":
        enable, mask = 1, 0xFFFF
    else:
        enable = 1
        mask = sum(1 << i for i, p in enumerate(a["hybrid_parts"]) if p == "strike")

    s = a["strike"]
    base_ms = part_ms(s["d_k_base"], s["d_k_curve"], s["d_m"], 0)
    if a["auto_release_ms"] is not None:
        hold_ms = a["auto_release_ms"]
    elif s["s_lvl"] > 0:
        hold_ms = max(1500.0, 3.0 * base_ms)     # 有余音：留出尾巴
    else:
        hold_ms = 2.0 * base_ms                  # 无余音：衰减完就回收

    # 20 位拍数。16 位只有 1243 ms，装不下 1.5 s 的余音尾巴（实测踩过）。
    hold_ticks = min(0xFFFFF, round(hold_ms * FS / 1000))

    return dict(
        artic_enable=enable,
        artic_mask=mask,
        strike_d_m=s["d_m"],
        strike_d_k_base=s["d_k_base"],
        strike_d_k_curve=s["d_k_curve"],
        strike_s_lvl=s["s_lvl"],
        strike_auto_rel=1 if a["auto_release"] else 0,
        strike_hold_ticks=hold_ticks,
    )


def default_curve(span):
    """按泛音跨度给出 curve 默认值（§2.3.1）。0 LUT，纯上位机。"""
    return max(0, min(15, round(112.0 / (span + 1))))


def solve_dk_base(target_ms, curve=10, d_m=3, span=15):
    """GUI 反解：想让最高泛音在 target_ms 消失，d_k_base 该取多少。

    curve 决定梯度形状不动，只动基准值（决定整体快慢）。
    """
    best = None
    for base in range(32):
        ms = part_ms(base, curve, d_m, span)
        cand = (abs(ms - target_ms), base)
        if best is None or cand < best:
            best = cand
    return best[1]


def part_ms(base, curve, d_m, k, shift=0):
    """单个泛音在 strike 下的衰减时长（毫秒）。"""
    d_k = max(0, base - ((k * curve) >> 4))
    return exp_steps(0, d_m, d_k) * (1 << shift) * 1000 / FS
```

`solve_dk_base` 与 `part_ms` 必须和 RTL 的公式**逐位一致**（`(k*curve)>>4`、钳到 0、`shift=0`），否则 GUI 显示 80 ms、板子发出 340 ms。`articulation_v2.py` 自测第 8 组就是这条的一致性检查。

### 4.3 `fit_exp` 的两个已知缺陷（顺手修）

**缺陷 1：`s_lvl = 32768` 时 jitter 爆表**

```
decay_ms=300, sustain_level=255 → m=1 k=0 shift=14, nominal=310.7ms, jitter=310.67ms
```

`exp_steps(32768, 32768)` 立刻返回 1，于是 `shift` 被选到最大。`sustain_level=255` 意味着"衰减到满幅"= 无衰减，此时应直接返回 `shift=0, steps=1` 并标注 `degenerate=True`，而不是报一个 310 ms 的 jitter。

**缺陷 2：`fit_exp` 不暴露 `steps`，无法判断是否撞 32768 上限**

`exp_steps` 在 `n > 32768` 时抛异常，但正常路径下饱和在 32768 步（621.4 ms）是**静默**的。建议返回 `saturated=True`，让上层能提示"请求 3 秒，实际 621 毫秒，请加大 shift"。

---

## §5 迁移与兼容

### 5.1 老配置文件（schema-1）怎么读

| schema-1 字段 | schema-2 去向 | 规则 |
|---|---|---|
| `articulation.attack_ms` | `tone.attack_ms` | 直接搬 |
| `articulation.decay_ms` | `tone.decay_ms` | 直接搬 |
| `articulation.sustain_level` | `tone.sustain_level` | 直接搬 |
| `articulation.release_ms` | `tone.release_ms` | 直接搬 |
| `articulation.mode` | `articulation.mode` | 直接搬 |
| `articulation.hybrid_parts` | `articulation.hybrid_parts` | 直接搬 |
| （无） | `articulation.strike` | **新增**，默认 `{d_m: 3, d_k_base: 14, d_k_curve: null, s_lvl: 2}`（null = 按频谱自动） |
| （无） | `articulation.auto_release` | **新增**，默认 `true` |
| （无） | `articulation.auto_release_ms` | **新增**，默认 `null`（编译器按衰减时长自动定） |

`load_config` 遇到 `schema_version == 1` 时**自动升级**并打 warning，不静默改文件；`save_config` 一律写 2。已实现于 `articulation_v2.py::migrate_v1_to_v2`，自测第 7 组覆盖（`config-hybrid.json` 升上来 `mask = 0xFFFE`）。

### 5.2 老的 `hybrid_parts` 会怎样

`schema-1` 的 `config-hybrid.json` 是 `["sustain"] + ["strike"]×15` —— 只有基频 sustain，其余 15 个泛音 strike。升级后语义不变，只是从"烘进音色"变成"运行时掩码"。

**但听感会变，而且是变好**：以前编译时 `sustain=0` 让 15 个泛音的 `s_lvl=0`、`decay=fit_exp(decay_ms, 0)`，所有泛音用同一个 `d_k`；现在音色里 16 个泛音全 `s_lvl=192`，运行时掩码把这 15 个切到 strike 版，`d_k` 按序号从 14 递减到 5。**高次泛音会明显更快消失**，这才是原来想要的效果。

### 5.3 协议兼容

`artic_*` 寄存器需要新的 UART 命令。现有协议是 `E0=A5` 的 176 字节大包（16 词 × 11 字节）。建议加**短命令**：

```
E0 = A6  激发模式参数（12 字节负载）
  [0]    flags: bit0 = enable, bit1 = auto_release
  [1:2]  artic_mask         小端 16 位
  [3]    strike_d_m[1:0] | (strike_d_k_curve[3:0] << 2)      ; bit6-7 = 0
  [4]    strike_d_k_base[4:0] | (strike_s_lvl[3:0] << 5)     ; bit5-7 复用，见下
  [5:7]  strike_hold_ticks  小端 20 位（低 3 字节）
  [8:9]  strike_hold_ticks[19:16] 补足高位 + CRC
  ...
```

> **注意 `[4]` 的位分配**：`d_k_base` 5 位 + `s_lvl` 4 位 = 9 位，一个字节装不下。要么把 `s_lvl` 挪到 `[0]` 的高 4 位（`flags` 只用了 bit0-1），要么把命令扩到 12 字节。**建议前者**：

```
E0 = A6  激发模式参数（10 字节负载）
  [0]    flags: bit0=enable, bit1=auto_release, bit4-7 = strike_s_lvl[3:0]
  [1:2]  artic_mask         小端 16 位
  [3]    strike_d_m[1:0] | (strike_d_k_curve[3:0] << 2)      ; bit6-7 = 0
  [4]    strike_d_k_base[4:0]                                ; bit5-7 = 0
  [5:7]  strike_hold_ticks  小端 20 位（3 字节）
```

10 字节 ≈ 1.9 ms @115200。理由：演奏中切模式要**低延迟**，不能每次都发 31.8 ms 的 176 字节包。

---

## §6 验收清单

| # | 项 | 通过标准 |
|---|---|---|
| 1 | 行为等价性 | `artic_enable=0` 时，M1 全部六套回归逐位一致（改动前 vs 改动后） |
| 2 | 掩码生效 | 同一音色、`mask=0` 与 `mask=0xFFFF` 各录一段，基频衰减时长比 ≥ 4:1 |
| 3 | 面积 | 综合报告 `note_map_owned` 的 LUT 增量 ≤ 100（含梯度乘法与余音选择），总 CLS 仍 ≤ 20736 |
| 4 | 时隙不占满 | 连续按 32 个 strike 音并保持，第 33 个音仍能发声（`gact` 被 `auto_release` 清掉） |
| 5 | 已响音符不受影响 | 按住一个 sustain 音，改 `artic_mask`，该音音色不变；新按的音变 |
| 6 | 编译器 | `compile_tone` 输出 16 词，`s_lvl` 全相同；`compile_articulation` 三模式取值符合 §3.3 |
| 7 | 迁移 | `config-hybrid.json`（schema-1）能读入并升级，`mask = 0xFFFE` |
| 8 | **梯度一致性** | `part_ms(base,curve,d_m,k)` 与 RTL 仿真测得的 16 个泛音衰减时长逐个吻合（容差 1 个 tick） |
| 9 | **梯度可闻** | `curve=0` 与 `curve=10` 各录一段 strike，频谱质心随时间的下降速率应有明显差别（用 `audio_observer.py` 的频谱轨迹看） |
| 10 | **余音可闻** | `s_lvl=0` 与 `s_lvl=2` 各录一段，`s_lvl=2` 的尾部在 340 ms 后仍有 -18 dB 左右的残余，且在 `hold_ticks` 处干净切断 |
| 11 | **hold 位宽** | 请求 1500 ms 时实际 `hold_ticks` 应 ≥ 79102（20 位），不能被截到 65535 |

第 8 条是这次新增里最容易出错的一条：公式在两处实现（Python 与 Verilog），`>>4` 和钳位只要有一处写错，GUI 显示和板子实际就差一个数量级。

第 11 条来自实测踩坑：`articulation_v2.py` 第一版用 16 位，请求 1500 ms 被静默截到 1243 ms。

---

## §7 已定与待定

### 7.1 已定

| 项 | 决定 | 依据 |
|---|---|---|
| `strike` 的 `d_k` 基准 | **不继承音色** | §1.2 实测 |
| 每泛音差异 | **按序号 `k` 生成梯度** | §1.4 物理规律 + 用户拍板 |
| 梯度公式 | `d_k(k) = base - (k*curve)>>4` | §2.3 实测 183 倍跨度 |
| 默认值 | `base=14, curve=null(自动), d_m=3` | §2.3 完整表 |
| curve 自适应 | **不做硬件补丁**，改成上位机 `default_curve(span) = min(15, round(112/(span+1)))` | §2.3.1 实测归一化会过冲 |
| `hybrid` 默认分组 | **前 3 sustain + 后 13 strike** | Q2 由本文决定：音高感来自前 3 谐波 |
| `auto_release` | **默认开**；有余音 1500 ms，无余音 2×基频 | §2.6 |
| `hold` 位宽 | **20 位**（16 位只有 1243 ms） | §2.2 实测 |
| 余音（Q3） | **加**，`strike_s_lvl=2`（12.5%），只作用于 `k<4` | §2.7 不额外占时隙 |
| 参考实现 | `articulation_v2.py`（8 组自测全绿） | 本目录 |

### 7.2 三条决定的落实情况

| 问题 | 你的选择 | 落实结果 |
|---|---|---|
| Q1 strike 听感不随音色变 | 选"便宜的补丁" | **改了方案**：实测归一化会过冲，改成上位机 `default_curve(span)`，0 LUT。见 §2.3.1 |
| Q2 hybrid 默认分组 | 由本文决定 | **前 3 sustain + 后 13 strike**。音高感来自基频+八度+十二度，第 4 个起让位给打击感 |
| Q3 余音感 | 反问 | **加**。关键发现是余音不额外占时隙（一个音固定占 16 个，与几个泛音在响无关），代价只是 `hold` 从 680 ms 拉到 1500 ms。见 §2.7 |

### 7.3 遗留风险（不是待拍板，是已知坑）

| 风险 | 说明 | 缓解 |
|---|---|---|
| `k` 被综合器展开 | 若 `note_map_owned` 把 `P=16` 展开成 16 份并行，梯度乘法变 16 份，面积从 73 涨到 300+ | 跑一次综合确认；超了就把 `k_curve_off` 在 note-on 时算一次存寄存器（128 FF） |
| 2 泛音无梯度 | `(1*15)>>4 = 0`，数学上不可能有梯度 | 接受。2 个泛音本来没有"频谱演化"可言 |
| 余音吃掉复音 | `hold=1500ms` 时每个 strike 音占 1.5 s。快速演奏 10 音/秒 → 15 音同时 → 240 时隙 | 够用（512 里占 47%）。若不够就把 `s_lvl` 设 0，`hold` 自动降回 680 ms |
| GUI 显示与板子不一致 | `part_ms` 在 Python 与 Verilog 两处实现 | §6 验收第 8 条：逐泛音对时，容差 1 tick |
