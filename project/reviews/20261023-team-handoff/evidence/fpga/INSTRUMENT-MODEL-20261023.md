# "自定义乐器"的实现机制与"音色 + 激发模式"框架评估 · 2026-10-23

回答三件事：
① 自定义乐器在硬件里到底是怎么实现的；
② 用户现在能编辑什么；
③ "乐器 = 音色 + 激发模式"这个两分法能不能统一实际乐器。

---

## §0 一句话结论

**硬件本体是"16 个独立的衰减正弦"，每个正弦 5 个可调参数。
"音色"和"激发模式"在硬件里不是两组参数，而是共享同一组——"激发"没有自己的旋钮，
它只能借用"音色"的衰减参数。而"激发"真正该管的那件事（起音），是硬编码常量。**

---

## §1 实现机制：一个乐器 = 4 槽 × 16 泛音 × 88 位

### 1.1 存储

```verilog
// instrument_table.v
reg [87:0] words[0:127];   // 4 槽 × 2 bank × 16 泛音
reg [15:0] written[0:3];   // 每槽 16 位，标记哪些泛音已写
```

**一个"乐器"= 16 个 88 位字**。16 个字全部写完才能 commit，commit 时 bank 翻转。

### 1.2 88 位怎么分

```
word[87:48]  40 位  自定义包络（每音符一份，不是每泛音一份）★ 见 §2
word[47:0]   48 位  泛音条目（每泛音一份）
```

| 段 | 位 | 字段 | 含义 |
|---|---|---|---|
| 泛音条目 | `[47:32]` | `ratio_q8` | 频率比，256 = 1.00× |
| | `[31:24]` | `amp` | 起音幅度 0–255 |
| | `[23]` | 保留 | 必须 0，否则 `instrument_table` 拒收 |
| | `[22:7]` | `s_lvl` | 衰减终点 0–32768（32768 = 100%） |
| | `[6:5]` | `d_m` | 衰减倍率 1–3（不能为 0） |
| | `[4:0]` | `d_k` | 衰减移位 0–31，越大越慢 |
| 自定义包络 | `[87:84]` | 保留 | 必须 0 |
| | `[83]` | `custom` | 1 = 启用下面 6 个字段 |
| | `[82:79]` | ATK shift | 起音时间抽稀 |
| | `[78:63]` | `a_inc` | 起音增量 16 位 |
| | `[62:59]` | DEC shift | 衰减时间抽稀 |
| | `[58:55]` | REL shift | 释放时间抽稀 |
| | `[54:53]` | `r_m` | 释放倍率 1–3 |
| | `[52:48]` | `r_k` | 释放移位 0–31 |

### 1.3 包络状态机（每个泛音一个）

```
IDLE ──on──> ATK ──lvl 到顶──> DEC ──lvl ≤ s_lvl──> SUS ──off──> REL ──lvl 到 0──> IDLE
```

衰减是**每拍一次乘加**：`lvl ← lvl − ((lvl × d_m) >> d_k)`，`d_m`/`d_k` 越大衰减越慢。
一拍 = 一个样本周期 = 18.963 µs（`fs = 27 MHz / 512`）。

`shift` 的作用是**时间抽稀**：`tick = (phase_read & ~(15'h7fff << shift)) == 0`，
即每 `2^shift` 拍才推进一次包络 —— 这是"粗调时间尺度"，让衰减能跨越 1 ms 到 8 s。

---

## §2 产品里只有 5 个参数生效 —— `INSTRUMENT_ENV=0`

```verilog
// tdm_top_owned.v:47
parameter integer CONFIG_DUAL_SOURCE=1, CONFIG_SERIAL=0, INSTRUMENT_ENV=0, ...
```

`tdm_ship_owned.v` 例化 `tdm_top_owned` 时**不传 `INSTRUMENT_ENV`** ⇒ 用默认 0。

```verilog
// tdm_engine_rh.v:392
generate if(INSTRUMENT_ENV) begin: per_instrument_env
    wire [39:0] eff_env = replace_params ? pe1[70:31] : epar1[70:31];
    wire custom = eff_env[35];
    wire shift  = (stg1==1) ? eff_env[34:31] : (stg1==2) ? eff_env[14:11] : (stg1==4) ? eff_env[10:7] : 4'd0;
    wire hold_level = custom && !tick && !trig_on && !trig_rel;
    assign env_a_inc = custom ? eff_env[30:15] : a_inc;
    assign env_r_m   = custom ? eff_env[6:5]   : r_m;
    assign env_r_k   = custom ? eff_env[4:0]   : r_k;
end else begin: legacy_env
    assign env_a_inc = a_inc;      // ← 产品走这里
    assign env_r_m   = r_m;
    assign env_r_k   = r_k;
end endgenerate
```

**⇒ 40 位自定义包络整段是死路径。`custom`、三个 `shift`、`a_inc`、`r_m`、`r_k` 全部不参与。**

### 2.1 起音和释放被硬编码

```verilog
// tdm_top_owned.v:1358-1359 —— 这些是"端口默认值"，在 legacy 路径下直接当常量用
.a_inc(16'd117), .d_inc(16'd1), .d_m(2'd3), .d_k(5'd12),
.s_lvl(16'd22938), .r_inc(16'd1), .r_m(2'd3), .r_k(5'd13),
```

| 参数 | 值 | 换算 |
|---|---|---|
| `a_inc` | 117 | 32768 / 117 = 280 拍 = **5.31 ms 起音** |
| `r_m` / `r_k` | 3 / 13 | τ = 2¹³/(3 × 52734) = **51.8 ms 释放时间常数** |

**这两个值不可调。** 界面上 `attack_ms` 能从 0 拖到 60000，`release_ms` 同理 —— **硬件上没有任何通路接收它们。**

### 2.2 因此衰减有一个 621 ms 的天花板

`d_k` 是唯一的衰减速度旋钮（`shift` 死了）。而 `(lvl × d_m) >> d_k` 在 `d_k ≥ 14` 时
每拍减 1，从 32768 减到 0 需要 32768 拍：

```
32768 × 18.963 µs = 621.4 ms
```

**钢琴低音的衰减是 10–20 秒。现在物理上做不到。**

> 双段衰减（`0x5D/0x5E/0x5F`）能绕开这个天花板：`d2_k > d_k` 让跌破断点后变慢。
> 但它是**全局的**，不是每泛音 —— 所以"第 1 个泛音衰减 15 秒、第 2 个 3 秒"这种真实行为仍然表达不了。

---

## §3 全局旋钮：不属于任何一个槽，但对音色影响很大

| 旋钮 | 地址 | 作用 | 粒度 |
|---|---|---|---|
| 力度表 `vel_wtab` | ROM（刀1 已扩到 4 槽） | `amp = base × w[slot][vel][part] >> 8` | **每槽 × 每力度 × 每泛音** |
| 亮度轴 TILT | `0x5C` | 整体频谱倾斜 | 全局 |
| 力度灵敏度 | `0x6E` / `0x6F` | 力度曲线的增益与移位 | 全局 |
| 双段衰减 | `0x5D/0x5E/0x5F` | 断点 + 第二段斜率 | 全局 |
| 演奏法 | `0x38–0x3F` | `artic_mask` + strike 参数 | 每泛音掩码 + 全局参数 |
| 滑音 / 颤音 | `0x00[2]`、`0x30–0x34` | | 全局 |

**力度表是当前唯一真正"每槽独立"的音色维度** —— 这就是刀1 第二步要分化的东西。

---

## §4 四个出厂预设实际长什么样

| 预设 | 特征 | k=0 | k=1 | k=2 | k=3 |
|---|---|---|---|---|---|
| **0** | `s_lvl=30000`（91.6%），`d_k=20` | 1.00× amp200 | 2.00× amp**0** | 3.00× amp140 | 4.00× amp**0** |
| **1** | `s_lvl` 递减，`d_k` 17→15 | 1.00× amp220 | 2.00× amp140 | 3.00× amp100 | 4.00× amp80 |
| **2** | `s_lvl=0`（打击），`d_k` 15→12 | 1.00× amp220 | 2.76× amp170 | 5.40× amp140 | 8.93× amp110 |
| **3** | `s_lvl=0`，`d_k` 13→10 | 1.00× amp220 | 4.00× amp150 | 9.20× amp70 | 16.0× amp40 |

**预设 0 的真相**（`ARTICULATION-RUNTIME-SPEC` §1.1 实测）：

> `d_k=20` 时 `(lvl×3)>>20 ≈ 0.09`，被钳成 1 ⇒ 每拍减 1 ⇒ 从 32768 减到 30000 需 2768 拍 = **52.5 ms**，然后停在 91.6%。
> 听感：起音后 52 毫秒内掉 8.4%，之后**完全静止**。

这就是"加法合成听着像风琴、不像钢琴"的第一号原因。

预设 0 只有 2 个泛音有声（k=1、k=3 的 amp=0），所以它其实是"1 倍频 + 3 倍频"的简单叠加。

---

## §5 界面能编 11 个，硬件只有 5 个

`experiments/config_transport_20261017/host/config_adapter.py:11`：

```python
FIELDS = {'ratio_q8','amplitude','sustain_q15','decay_m','decay_k','decay_shift',
          'attack_inc','attack_shift','release_m','release_k','release_shift'}
```

| 界面字段 | 硬件对应 | 产品里生效？ |
|---|---|---|
| `ratio_q8` | `[47:32]` | ✅ |
| `amplitude` | `[31:24]` | ✅ |
| `sustain_q15` | `[22:7]` | ✅ |
| `decay_m` | `[6:5]` | ✅ |
| `decay_k` | `[4:0]` | ✅ |
| `decay_shift` | `[62:59]` | ❌ |
| `attack_inc` | `[78:63]` | ❌ |
| `attack_shift` | `[82:79]` | ❌ |
| `release_m` | `[54:53]` | ❌ |
| `release_k` | `[52:48]` | ❌ |
| `release_shift` | `[58:55]` | ❌ |

**11 个旋钮里有 6 个是空的。** 用户拖 `attack_ms`、`release_ms`，界面上数值会变、文件会存、
CRC 会算对、硬件也会收进去 —— **但声音不会变**。

> 这比"功能没做"更危险：**它看起来是好的。** 界面的单元测试全绿，因为它只测文件往返，
> 不测硬件行为。这正是 `ARTICULATION-RUNTIME-SPEC` §1.3 记的"`shift` 只在 `custom=1` 时生效"那个坑。

---

## §6 "音色 + 激发模式"能不能统一实际乐器

### 6.1 先说结论

**能统一，但两分法要重构一次。** 三个理由：

#### 理由 1："音色"在硬件里是两组参数，不是一个

- **静态频谱**：`ratio` + `amp`（有哪些分音，各多响）
- **时域演化**：`s_lvl` + `d_m` + `d_k`（这些分音怎么消失）

**钢琴和风琴的频谱可以完全一样**（都是 1/n 衰减的泛音列），区别全在时域。
如果"音色"是一个不可分的包，那它装了两件可以独立编辑的事。

#### 理由 2："激发模式"不是和"音色"并列的维度，它是时域层的替代参数集

证据就在 `note_map_owned.v`：

```verilog
wire strike_sel = artic_enable && artic_mask[k];
wire [22:0] p_epar_eff = strike_sel ? {p_s_lvl_eff, strike_d_m, strike_d_k} : p_epar;
wire [39:0] env_eff    = strike_sel ? {env_base[39:15], 4'd0, env_base[10:0]} : env_base;
```

`artic_mask` 的作用是**"哪些泛音改用另一套 `s_lvl`/`d_m`/`d_k`"**。
它**不改 `ratio`，不改 `amp`**。

**⇒ "激发模式"在硬件里的位置是"时域层的一个开关"，不是独立的一层。**

这也解释了 `hybrid_parts`（每泛音选 sustain/strike）为什么能直接映射到 `artic_mask[15:0]` ——
因为 hybrid 本来就是"每泛音选一套时域参数"。

#### 理由 3：缺了第三维 —— 力度响应

钢琴轻按和重按：**同一个音色、同一个激发模式**，但频谱不同（轻按泛音少）。
这件事由 `vel_wtab` 承担，而它既不属于"音色"（音色是固定的表），也不属于"激发"（激发是时域）。
它是"输入强度 → 频谱"的映射。

**两分法装不下它。** 而这恰恰是刀1 正在做的东西。

### 6.2 更关键的一点：现在的"激发模式"改的是衰减，不是激发

用户说"激发"，直觉指的是**怎么把能量注入系统**（敲、拨、拉、吹）。
这件事在硬件里是 `a_inc`（起音速度）+ `amp`（注入量）。

| | 真实乐器 | 硬件 | 现状 |
|---|---|---|---|
| 敲击 vs 拉弓 | 起音段完全不同（1 ms 冲击 vs 200 ms 渐入） | `a_inc` | **硬编码 117 ≈ 5.3 ms** |
| 敲击 vs 拉弓 | 衰减形态不同 | `d_k` / `s_lvl` | ✅ 可调（`artic_mask`） |

**strike 模式让声音消失得快，但起音段（前 5 ms）完全一样。
而敲击和拉弓的区别，恰恰主要在那 5 ms 里。**

所以严格说：**现在实现的是"衰减模式"，不是"激发模式"。**

### 6.3 建议的框架（四层，可映射回两分法）

```
乐器
├─ 频谱        ratio[16] + amp[16]                    静态：有哪些分音，各多响
├─ 时域        s_lvl[16] + d_m[16] + d_k[16]          动态：每个分音怎么消失
│              + a_inc[16] + shift + r_m/r_k          ← 现在全死
├─ 响应        vel_wtab[slot][vel][part]              力度如何改变频谱
└─ 演奏法      artic_mask + strike_*                 时域层的一套替代参数
```

映射：

| 用户的两分法 | 实际对应 | 差在哪 |
|---|---|---|
| 音色 | 频谱 + 时域 | 这两件事可以独立编辑，不该合并 |
| 激发模式 | 演奏法（只作用在时域） | 真正管"注入"的 `a_inc` 现在是死的 |
| （缺） | 响应（力度） | 没有它，轻按重按只有音量差别 |

**这套框架能覆盖真实乐器吗？**

| 乐器 | 频谱 | 时域 | 响应 | 演奏法 | 够不够 |
|---|---|---|---|---|---|
| 钢琴 | 1/n 泛音 | 低音 10 s、高音 1 s，高次泛音先死 | 重按泛音多 | 击弦 | ⚠️ 时域 621 ms 天花板不够 |
| 小提琴 | 弓噪 + 泛音列 | 起音 200 ms 渐入、持续 | 弓速改亮度 | 连弓/跳弓/拨弦 | ❌ 起音不可调 |
| 长笛 | 近乎纯正弦 | 起音 100 ms、几乎不衰减 | 气速改亮度 | 吐音 | ❌ 起音不可调 |
| 钟/马林巴 | 非谐泛音（2.76×/5.4×） | 打击后自由衰减 | 力度改亮度 | 敲击 | ✅ 预设 2/3 就是 |
| 风琴 | 整数泛音 | 起音快、永不衰减 | 无 | 无 | ✅ 预设 0 就是 |

**⇒ 现在能做"打击类"和"持续类"，做不了"起音可塑类"（弦乐、管乐）。**

原因不是框架不对，是 `a_inc` 被关掉了。

---

## §7 打开这条路要付多少

### 7.1 最小改动：`INSTRUMENT_ENV=1`

```verilog
// tdm_engine_rh.v:155
localparam integer EPW = 31 + (INSTRUMENT_ENV ? 40 : 0);   // 31 → 71
```

`epar_mem[0:NSLOT-1]` 从 512 × 31 位变成 512 × 71 位：

| 项 | 增量 |
|---|---|
| `epar_mem` | +512 × 40 bit = **+20480 bit ≈ +1.1 BSRAM** |
| `phase_count` / `phase_read` | 2 × 15 位 = +30 FF |
| `shift` 选择 + `hold_level` + 三路 mux | ≈ +150–250 LUT |
| **合计（估算）** | **+2 BSRAM、+40 FF、+250 LUT** |

当前 15/46 BSRAM、8265/10368 CLS ⇒ 加完约 **17/46、8400/10368（81%）**。**代价不大。**

### 7.2 但要真用上，还需要 `CONFIG_SERIAL=1`

`INSTRUMENT_ENV=1` 只让 40 位字段**能被读取**，但 `eff_env` 来自 `epar_mem`，
而 `epar_mem` 的装载源是 `custom_entry[87:48]`，`custom_entry` 来自 `instrument_table`，
`instrument_table` 的写口是 `cfg_*`，`cfg_*` 在 `CONFIG_SERIAL=0` 时恒 0。

**⇒ 两个参数必须一起开。** 见 `CUSTOM-INSTRUMENT-STATUS-20261023.md`。

### 7.3 顺序建议

| 步 | 内容 | 能听到什么 |
|---|---|---|
| 1 | `INSTRUMENT_ENV=1` + 一个 host 脚本把 4 槽写成"钢琴/弦乐/钟/贝斯" | 每泛音独立起音/衰减，长音终于能超过 621 ms |
| 2 | 4 张 `vel_wtab` 分化（刀1 第二步） | 力度改音色，不只是音量 |
| 3 | 实体切槽 | 不连电脑也能换 |

---

## §8 复现命令

```bash
P=D:/FPGA-Project/codex-builds/fpga-m1-agent-work

# 总开关
grep -n "INSTRUMENT_ENV=0" $P/engine/src/tdm_top_owned.v

# 40 位包络的位段
sed -n '388,418p' $P/engine/src/tdm_engine_rh.v

# 起音/释放被硬编码
sed -n '1355,1362p' $P/engine/src/tdm_top_owned.v

# 88 位字段解包（权威）
sed -n '1,20p' $P/engine/src/uart_cfg_transport.v   # 协议
sed -n '18,35p' $P/experiments_host/config_adapter.py 2>/dev/null || \
  sed -n '11,35p' "C:/Users/Sakuya/FPGA-Music-project/experiments/config_transport_20261017/host/config_adapter.py"

# 出厂预设实际参数
python -c "
lines=[l.strip() for l in open('$P/build_decay2_v1/preset_part.hex') if l.strip()]
for p in range(4):
    w=int(lines[p*16],16)
    print('preset%d k=0 ratio=%d amp=%d s_lvl=%d d_m=%d d_k=%d'%(p,w>>32,(w>>24)&255,(w>>7)&65535,(w>>5)&3,w&31))
"

# strike 只改时域，不改 amp
grep -n "strike_sel" -A3 $P/engine/src/note_map_owned.v | head -12
```
