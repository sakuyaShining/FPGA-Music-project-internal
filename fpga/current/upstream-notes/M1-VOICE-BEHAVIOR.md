# M1 发声行为核查：同音重触发 / 效果器 / 加法合成短板

日期：2026-10-22　｜　性质：**源码级核查记录**，不是验收结论。
所有结论都标了文件行号，可直接复核。

---

## 1. 同音快速重按：**不会硬切，但也不会叠加**

### 1.1 分配器第一优先级就是"复用正在奏同一音符的组"

`engine/src/note_map_owned.v:312-334`：

```verilog
// 优先级：已在奏同一音符的组 > 空闲组 > round-robin 抢占
// 先找"正在奏同一音符"的组
for (n = 0; n < NG; n = n + 1) begin
    if (!found_match && gact[n] && gtab[n]==n_hold) begin
        gsel_cur = n; found_match = 1'b1;
    end
end
if (!found_match) begin /* 找空闲组 */ end
```

⇒ 第一个音还在响时按下同一个音，**不会新开一个声部**，而是**复用同一个组重触发**。
注释里也明确写了（`:397`）："同音重触发（found_match）—— 那是重击同一个音，不是滑音"。

### 1.2 但重触发不是硬切，不爆音

`engine/src/osc_env.v:118-123`：

```verilog
// A new excitation can arrive during sustain or an old release tail.
// Restart attack from the current level, preserving phase/amplitude
// continuity. Gate-off and ordinary parameter refresh do not trigger it.
if (trig_on) begin
    stg_o = ST_ATK;      // ← 只改状态，lvl_o 保持 lvl_i（不清零）
end
```

- **电平不清零**：`trig_on` 分支只写 `stg_o`，`lvl_o` 仍是进入时的 `lvl_i` ⇒ 从**当前音量**继续起音。
- **相位不重置**：`tdm_engine_rh.v:353-357` 的 `replace_params` 只替换 `inc` / `amp` / `epar`，
  不写 `phase_mem`；相位累加器一直在跑 ⇒ 泛音之间的相对相位连续。
- **旧音的 note-off 不会杀新音**：释放事件按"实例"匹配（`note_map_owned.v:375` 的 `owner_hit`
  比对 `group_instance` 与 `instance_hold`），`tb_layers.v:115` 有 `$fatal` 断言兜住这条。

### 1.3 听感结论

| 场景 | 实际行为 | 听感 |
|---|---|---|
| 按住第一个音不放，再按同音 | 同一组重触发，电平从当前值继续起音 | "再弹一次"，无爆音 |
| 第一个音已松手、释放尾音还在响，再按同音 | `trig_on` 落在 RELEASE 态 ⇒ 从衰减中的电平重新起音 | legato 重触发，无爆音 |
| 想要"两个同音叠加成两层" | **做不到**，只有一层 | — |

⇒ **不存在"强行终止"导致的爆音**。真正的限制是**同音不能叠层**。

### 1.4 如果要做"同音叠加"

改 `found_match` 的优先级（同音也去开新组）。代价：
- 复音数按"同时按下的同音数"成倍消耗（32 组 / 16 泛音 = 32 声部，同音叠加会加速抢占）；
- 抢占策略必须同时改，否则会抢掉正在响的其他音；
- `19 alloc` / `28 legato` 两套回归必须重跑（`note_map_owned.v:352` 的注释已警告过这一点）。

---

## 2. 效果器：**已经实现了，只是默认全关**

用户判断"还没有效果器等成熟电子乐器的功能"——这条与源码不符。

### 2.1 实现内容

`engine/src/fx_delay.v`（326 行，`u_fx`，715 LOGICeq，**已在当前网表里**）：

| 效果 | 参数 | 默认值（开机自举写入） |
|---|---|---|
| 延迟 delay | `0x41/0x42` 延迟长度、`0x43` 反馈 | 1500 样本 ≈ **28 ms**、反馈 **0.375** |
| 合唱 chorus | `0x44/0x45` 速率、`0x46` 深度 | **1.35 Hz**、**64 样本** |
| 混响 reverb | `0x48` 反馈、`0x49` 阻尼 | 反馈 **0.5**、阻尼 **3**（一阶低通，越大越暗） |
| 湿声衰减 | `0x40[5:3]` | 由 `FX_CTRL` 决定 |

混响不是简单反馈延迟：`fx_delay.v:223-254` 有 `rev_lpn = rev_lp + (rev_dlt >>> rev_damp)` 的
一阶低通阻尼，以及 ÷8 平均后的环路增益。

### 2.2 为什么听不到

`engine/src/tdm_top_owned.v:263-266`：

```verilog
// ---- 效果器默认值：干声直通、两个效果都关 ----
5'd9: begin b_addr <= 8'h40; b_data <= 8'h01; end // FX_CTRL: 仅干声
```

`FX_CTRL = 0x01` ⇒ `fx_dry_en=1`、`fx_dly_en=0`、`fx_cho_en=0`、`fx_rev_en=0`
⇒ `fx_active = 0` ⇒ 顶层 `audio = fx_active ? fx_out : sample`（`:1181`）**完全旁路**。

### 2.3 打开它零面积成本

`u_fx` 已经在网表里，开关只是寄存器位：

```
0x40 FX_CTRL:  bit0=干声  bit1=延迟  bit2=合唱  bit6=混响  bit[5:3]=湿声衰减
```

参数寄存器 0x41–0x49 都已给好默认值，只写 `0x40` 一位就能听到效果。
运行时通过 `cfg_*`（reg_bank 串行配置）或 UART 写入即可，**不需要重新综合**。

> 这是当前"听感不够电子乐器"里**性价比最高的一格**：零面积、零时序风险、当天可听。

---

## 3. 纯加法合成"效果不好"的三个可验证原因

### 3.1 频谱不随时间演化（最主要）

`tdm_engine_rh.v:155-160`：`phase_mem` / `inc_mem` / `env_mem` / `stg_mem` / `gcur_mem`
都是 **每 slot 一份**（NSLOT=512 = 32 声部 × 16 泛音）⇒ 每个泛音有**独立的包络状态**。

但 `load_env` 是**每音符一个 40 位值**（`tdm_top_owned.v:1008/1149`，来自 `nm_load_env`）
⇒ 16 个泛音拿到的是**同一组包络参数**，形状完全相同。

真实乐器（钢琴、吉他、拨弦）的关键特征是**高次泛音衰减更快**——频谱在几百毫秒内从亮变暗。
现在所有泛音同步衰减 ⇒ 听感像**静态管风琴/电子琴**，这是加法合成最典型的"塑料感"来源。

### 3.2 高音区会掉泛音

`note_map_owned.v:519,530-531`：

```verilog
wire nyq_kill = |inc_mul[PHASE_W+15:PHASE_W+7];
wire [AMP_W-1:0] amp_use = on_cur ? (nyq_kill ? {AMP_W{1'b0}} : amp_cal) : ...
```

分音频率超过 Nyquist 时**幅度直接清零**。这是**正确的**（否则会混叠成不和谐音），
但副作用是：音越高，可用泛音数越少 ⇒ 高音区**变闷**，同一个预设在不同音区音色不统一。

### 3.3 只有 16 个泛音（右手确实是连续推子）

- `PART = 16`（`tdm_top_owned.v:1137`）。16 个泛音做不出明亮 lead——锯齿波要几十个泛音才成形。
- **右手泛音构造是连续推子，不是开关。** 见 §3.4 的通路。

### 3.4 右手泛音构造的真实通路（**更正 §3.3 的旧说法**）

> 我先前把 `note_map_owned.v:461` 的 `spec_eff = pad_mask[k] ? 8'd255 : spec_ram[k]` 当成了
> "右手泛音构造"，据此说它"是开关不是推子"。**这是错的**——那是另一条已停用的旧通路。
> 正确结论如下。

现行通路（`RIGHT_TIMBRE=1`，`left_layer_music_probe.v:81` 已启用）：

```
右手触控屏 touch_valid / touch_x / touch_y / touch_id / touch_active
  │
  ▼  rh_performance_control.v   （四段流水：touch → fader → gain → ramp）
  rh_fader_panel        → fader_y[79:0]      = 8 个推子 × 10 位
  rh_fader_gain_map     → gain_target[159:0] = 16 个泛音 × 10 位
                          （part_to_control 把 16 个泛音映射到 8 个推子，
                            再查 fader_gain_q8.hex → 12 位 LUT）
  rh_timbre_slew        → current_gain       = 按 slew_step 斜坡逼近目标
  │
  ▼  tdm_engine_rh.v:486-514   generate if (RIGHT_TIMBRE)
  raw_gain = first_slot ? timbre_gain_q8[9:0] : gain_frame[(sl1%PART)*10 +: 10]
  gain     = raw_gain < 256 ? 256 : raw_gain        // 下限 = 1.0×
  boosted  = (amp_eff * gain) >> 8
  rh_amp_eff = mask_bit ? boosted : amp_eff
```

关键数值（都是逐位核过的）：

| 项 | 值 | 依据 |
|---|---|---|
| 推子数 | **8** | `rh_fader_gain_map` 参数 `NF=8`，`fader_y` 80 位 |
| 泛音数 | **16**，每个映射到 8 个推子之一 | `part_to_control` 48 位 = 16 × 3 位 |
| 推子行程 | 0 … 1023 | `fader_y` 每项 10 位 |
| 增益范围 | **×1.0 … ×2.0（0 … +6 dB）** | `fader_gain_q8.hex` 是 12 位十六进制：`0x100`(256) … `0x200`(512)，取 `rom_q[9:0]` |
| 平滑 | 按 `slew_step` 逐样本斜坡 | `rh_timbre_slew.v` 的 `next_gain=(distance<=step)?t:c±step` |
| 增益作用方式 | **乘**在包络后幅度上，且只增不减 | `gain` 下限 256 = 1.0× |

⇒ 右手是**连续的、带防拉链噪声斜坡的 8 推子 → 16 泛音增益矩阵**，推程 0~+6 dB。

**那条被我误认成"右手泛音构造"的通路，其实是停用的旧机制**：

| | 旧通路（已停用） | 现行通路 |
|---|---|---|
| 输入 | 物理电极阵列 `pad[15:8]`（8 根泛音键） | 右手触控屏坐标 |
| 寄存器 | `0x5B HARM_PADS` 软掩码 | `0x40` 起的效果器无关；推子由触控驱动 |
| 增益 | **二值**：`spec_eff = pad_mask[k] ? 255 : spec_ram[k]`，摸到即满幅 | **连续**：256…512 |
| 现状 | `LEGACY_PAD=0`（`left_layer_music_probe.v:81`）⇒ `pad_state_raw=16'd0`、`pad=16'bz`，**物理电极整个断开**；`0x5B` 开机被显式清零 | 启用中（`RIGHT_TIMBRE=1`） |
| 代码位置 | `tdm_top_owned.v:596-614`、`:734`、`note_map_owned.v:461` | `tdm_engine_rh.v:486-514`、`rh_performance_control.v` |

> 补充：`tdm_top_owned.v:293` 的注释把 `0x5B` 那一片称作"并行版的紧凑泛音表遗留垃圾"，
> 与"旧通路"这个判断一致。所以它留在硅片里是历史遗留，不是现行功能。

### 3.5 那么"泛音构造"还缺什么

既然推子是连续的、范围 0~+6 dB，问题不在"手感是开关"，而在**两个更实的地方**：

1. **只能加不能减**：`gain` 下限锁在 256（×1.0），推子拉到底也只是回到基准幅度，
   没法把某个泛音**压掉**。要"去掉不想要的泛音"，只能靠预设谱本身把它设成 0。
2. **8 个推子要管 16 个泛音**：`part_to_control` 是 16 个 3 位索引，只能指向 8 个推子
   （`part_to_control[g*3 +: 3] < NF=8`，越界会置 `map_error`）。按鸽笼原理至少 8 个泛音要共用推子，
   平均每个推子带 2 个。具体配对由 `part_to_control` 运行时配置决定，**做不到 16 个泛音各自独立**。
   这是 `NF=8` 的接口约束，不是软件可调项；要独立就得把 `NF` 提到 16（`fader_y` 80→160 位、
   `rh_fader_panel` 的几何映射也要改）。

---

## 4. 建议的优先级（按"成本 / 听感收益"排序）

| # | 动作 | 面积成本 | 工期 | 预期收益 |
|---|---|---|---|---|
| 1 | **打开效果器**（写 `0x40`），调 `0x41–0x49` | **0**（已在网表） | 当天 | **最大**：延迟/合唱/混响直接补上"空间感" |
| 2 | 调 `0x5C TILT`（独立亮度轴）与 4 个预设谱 | 0 | 当天 | 中：音色从"平"变"有明暗" |
| 3 | 重做 `fader_gain_q8.hex` 与 `part_to_control` 映射（推子行程/配对关系） | 0（只换 hex 与 3 位映射） | 1 天 | 中：推子手感与配对更贴合 |
| 3b | 让推子能**衰减**（`gain` 下限 256 → 更小，并相应调 `amp_eff` 基准） | 需 RTL 小改 | 1–2 天 | 中：可以"压掉"泛音，而不是只能加 |
| 4 | **每泛音独立包络参数**（高次泛音衰减更快） | 需 RTL 改动 | 数天 | **大**：治"塑料感"的根 |
| 5 | 泛音数 16 → 24/32 | 需面积（当前 CLS 99.6%，**放不下**） | — | 大，但被面积卡死 |

> 第 5 条要等 M2 的面积问题解决后才能谈；第 1–3 条是**现在就能做且零面积成本**的。
