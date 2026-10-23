# M1 面积取舍评估：`finger_pitch` 重写风险与功能取舍清单

日期：2026-10-22　｜　对象：`engine/src/finger_pitch.v`（`u_finger`，NG=32 / NF=32 / MULTI_BIND=1）
性质：**决策材料，不是验收结论**。所有数字标注"实测"或"推算"。

---

## 0. 四个最重要的结论

### 0.1 最大的杠杆不是砍功能，是 `-place_option`

| 配置 | `place_option` | CLS | Setup | Hold |
|---|---|---:|---:|---:|
| 全功能（v3 源） | 0 | 10335 | **路由失败** | — |
| **全功能（v3 源）** | **1** | **10327** | **−0.700** | −0.126 |

只把 `-place_option 0` 改成 `1`，setup 从 −6.397 → **−0.700**，**白送 5.697 ns**，而且第一次布通。代价是构建时间 344 s → 712 s。

**项目一直用的是 0。** 这条比本轮任何 RTL 改动都值钱。

> **但杠杆到此为止。** 查证后确认：`-place_option 1` 的官方定位是**可布通性优先**（不是"更好的布局"），
> `2`（XML 说的时序优先）在这个二进制里被钳到 `1` —— `board.bin` 与 `1` 逐字节相同（§5.1.2）。
> 加上 hold 修正器已无余量（§5.2.1），**剩下的 0.700 / 0.126 ns 只能靠腾面积，没有别的旋钮**。

### 0.2 两个裁剪配置在 `place_option 1` 下都干净 PASS

| 配置 | Setup | Hold | TNS |
|---|---:|---:|---:|
| 关逐指表情 | **+4.122** | **+0.002** | 0 / 0 端点 |
| 关视觉化 | **+3.123** | **+0.002** | 0 / 0 端点 |

### 0.3 hold 不是"坏了"，是修正器收敛到零

`-correct_hold 1` 在本版本有效且一直在工作，它把每条短路径推到刚好过线，所以 hold 表
从 +0.002 到 +0.015 密集排列。**+0.002 是正常结果，不是运气。**
唯一真正的违例（关视觉化那版 −0.050，DSP→FF 路径）是修正器在 99% CLS 下没有绕行余量，
换成 `place_option 1` 后自动消失。

### 0.4 剩下的 0.7 ns 正好落在 `finger_pitch` 的写路径上

`build_m1_v5_p1` 的最差 setup 路径是：

```
system/music/layers/state_0_s1/Q → system/music/core/contact_expression.u_finger/offset[21]_7_s1/D
```

也就是 `finger_pitch` 的 **32 路写译码 + `offset[]` 写数据 mux** —— 正是"重写 32 路线性搜索"
要动的东西。⇒ 在"两个功能都保留"的配置里，重写 `finger_pitch` 有了明确目标（打这条 0.7 ns），
不再是"为了省 CLS 而重写"。

> 修正上一版结论：此前判断"重写单独不足以闭合时序、应放弃"，是在 `place_option 0` 的前提下得出的。
> 换了布局算法后，缺口从 6.4 ns 缩到 0.7 ns，重写的性价比完全变了。

---

## 1. `u_finger` 现在占多少、花在哪

### 1.1 实测占用（基线，Gowin 分层资源报告）

| 项 | REG | ALU | LUT | SSRAM | LOGICeq |
|---|---:|---:|---:|---:|---:|
| `contact_expression.u_finger` | 809 | 173 | 1708 | 10 | **1941** |
| 占 `music` 子树 | — | — | — | — | 13.2% |

> 口径：`LOGICeq = LUT + ALU + 6×SSRAM`，与 Gowin 报告 `Logic` 完全一致（基线 17192 + 2282 + 6×144 = 20338）。
> **更正上一轮**：此前把 `u_finger` 写成 1881，是漏加一列，正确 LOGICeq 是 **1941**。

### 1.2 手算分解（**估算**，未单独实测）

| 结构 | 代码位置 | 估算 LUT |
|---|---|---:|
| `offset[i]` 的 18 位写数据 2:1 mux（32 组 × 18 位） | `:68` 与 `:76` 同块顺序赋值 | **≈576** |
| `contact_anchor[finger]` 32:1 × 12 桶形 mux | `:39` | ≈132 |
| `group==i` / `voice_group==i` / `owner[i]==finger` 三组 32 路比较 | `:35` `:62` `:74` | ≈192 |
| `owned` / `enabled` 置位清零 | `:61-77` | ≈96 |
| `(|mine)` 32 输入或 | `:39` | ≈11 |
| `delta` / `address` / 钳位 | `:40-43` | ≈30 |

**最大的单项不是"搜索"，是 `offset[]` 的写数据 mux（≈576 LUT）**。它存在的原因是 32 个 18 位寄存器
各自需要"写 `movement_offset` 还是写 0"的数据选择。若写入地址收敛到单一下标，这个 mux 会退化成
时钟使能（FPGA 里 CE 免费），576 LUT 直接消失。

---

## 2. A 路线：机械式 RAM 化（不改搜索语义）

| 数组 | 位宽 | 写口 | 能否 RAM 化 | 依据 |
|---|---:|---|---|---|
| `owner[0:31]` | 160 | 单（下标 `group`） | **能** | 去掉 `:49-51` 复位循环 |
| `contact_anchor[0:31]` | 384 | 单（下标 `finger`） | **能** | 去掉 `:52` 复位循环 |
| `offset[0:31]` | 576 | **多**（一指多组同拍写） | **不能** | 硬障碍，见 §2.2 |

### 2.1 风险

| # | 风险 | 严重度 | 说明与对策 |
|---|---|---|---|
| A1 | RAM 推断是二值的：要么整块进 RAM，要么退化成 576 FF + 桶形 mux | 中 | 已两次实测"局部省了、全局倒贴"（`finger_held`：`u_tdm` −56 但全局 +40）。每次先跑 `synth_area.py`（2 分钟），不直接上 9 分钟构建 |
| A2 | 未初始化读的 X 传播 | 中 | 去复位后上电为 X。`owner[]` 被 `owned[]` 门控、`contact_anchor[]` 被 `(|mine)` 门控 → 安全；但 `offset[]` 是**无条件**从 `expr_offsets` 输出。**`tb_layers:98` 的 `finger_offsets[c]!=0` 在 X 上会静默通过**（Verilog 里 `X != 0` 求值为 X，`$fatal` 不触发）。真正兜住的是黄金轨迹逐字节 |
| A3 | 综合器全局重排吃掉收益 | 高 | 两次实测。±100 LOGICeq 落在噪声带内，方向随机 |
| A4 | `MULTI_BIND` 两个分支只测了一个 | 中 | 探针构建 `MULTI_BIND=1`，`:61` 的 `if(!MULTI_BIND ...)` 被常量折叠，**该分支没进网表** |
| A5 | 收益上限有限 | 中 | 只能动 `owner`(160 FF) + `contact_anchor`(384 FF + 132 LUT)，`offset` 的 576 FF 与 576 LUT 数据 mux 都动不了。乐观 **−400 ~ −600 LOGICeq**，按 12.3:1 只有 **−32 ~ −49 CLS** |

### 2.2 为什么 `offset[]` 不能简单 RAM 化

```verilog
for(i=0;i<NG;i=i+1) begin
    if(cmd_valid) begin
        if(cmd==0) begin ... offset[i]<=0; end
        else if(owned[i] && owner[i]==finger) begin
            if(cmd==1) offset[i]<=movement_offset;   // MULTI_BIND=1 时多个 i 同时命中
        end
    end
    if(voice_valid && voice_group==i) begin
        if(voice_on) offset[i]<=0;                    // 同拍第二次写
    end
end
```

`MULTI_BIND=1` 时一根手指拥有多个组（`tb_layers` 里 `a=groups0[0]`、`b=groups1[0]` 被同一 contact
绑定，两条断言要求 `finger_offsets[a]==finger_offsets[b]`）。所以 `cmd==1` 是**散射写**：同一拍写
`offset[a]` 和 `offset[b]`。RAM 只有单写口。

---

## 3. B 路线：结构改写（每指一份状态 + 间接寻址）

思路：`offset[group]`（32×18，散射写）→ `finger_offset[finger]`（32×18，单写下标），
读侧 `finger_offset[owner[group]]`。

**收益**：写数据 mux 消失（−576 LUT 估算）+ 写地址收敛可 RAM 化（−576 FF）；
读侧变两级查表（`owner[]` 32:1×5 ≈55 + `finger_offset[]` 32:1×18 ≈162 = 217 LUT）。
净估算 **−500 ~ −800 LOGICeq ≈ −40 ~ −65 CLS**。

### 风险

| # | 风险 | 严重度 | 说明 |
|---|---|---|---|
| B1 | **破坏"释放尾音保留最后音高"** | **最高** | 现在 `offset[i]` 是每组独立冻结的：抢占时 `owned[i]<=0` 但 `owner[i]` 不清，尾音停在最后偏移。改"每指一份"后，同一手指再绑新组时 `offset<=0`，**旧尾音会瞬间跳回基准音高**。这是可听见的功能回归 |
| B2 | `owned` 与 `enabled` 的不对称是刻意的 | 高 | `enabled`（→`expr_active`）只在 `voice_on` 清零，`cmd==2` 不清（`:64` vs `:69`）。任何"顺手统一"都会改变 `finger_active` 时序，而它直接进 `finger_use` → `p_fuse` → 音高 |
| B3 | 锚点共享不变量容易被改坏 | 中 | `contact_anchor` 是"每指一份"不是"每组一份"；`MULTI_BIND=1` 下第二次 bind 用 `moving_anchor` |
| B4 | `|mine` 在 bind 的关键路径上 | 中 | bind 是单拍命令（`cmd_valid` 与 `position` 同拍），**不能靠加一拍同步读解决**，否则漏一次 bind |
| B5 | **测试覆盖缺口导致"改错了还是 PASS"** | **最高** | 见 §4。偏差落在没有断言的地方 → 仿真全绿，板上表现为"某根手指滑音不跟手" |
| B6 | 例化面 4 处、参数 2 种，只测 1 种 | 中 | `tdm_top.v:961`、`tdm_top_rh.v:977`、`tdm_top_owned.v:1071`；只有 `MULTI_BIND=1, NG=32, NF=32` 进过测试 |

---

## 4. 现有测试覆盖了什么

### 4.1 有硬断言（`$fatal`）的

| 行为 | 位置 | 内容 |
|---|---|---|
| 一指多绑 | `tb_layers.v:96` | `finger_active[a]` 与 `[b]` 同时为 1 |
| 滑动不重触发 | `tb_layers.v:98` | `group_start_tag[a]` 不变 |
| 一指多组共享偏移 | `tb_layers.v:98` | `finger_offsets[a] == finger_offsets[b]` |
| 其他手指不受影响 | `tb_layers.v:98` | `finger_offsets[c] == 0` |
| 抢占后旧手指失去控制 | `tb_layers.v:113` | 被抢组 `finger_active[a]==0`，同指另一组仍在滑 |
| 旧尾音释放不杀新音 | `tb_layers.v:115` | `nm_active[a]` 仍为 1 |
| 实体位置独立驱动音高 | `tb_sensor_layers.v:49` | `g0` 非零、`g12`/`g13` 为零、`ons==6` |
| 实体滑动到达第二层 | `tb_sensor_layers.v:50` | `groups1[0]` 与 `groups0[0]` 偏移相同 |
| 逐拍值比对 | 三组黄金轨迹 | 轨迹含 `finger_valid`/`finger_active`/`finger_offsets`，逐字节相同 |

### 4.2 没有覆盖的

| 缺口 | 位置 | 为什么危险 |
|---|---|---|
| **同拍 `cmd_valid` 与 `voice_valid` 竞态** | `:72-77`（注释写明 "including same-clock races"） | 顺序赋值决定"分配器复用优先"，改写成优先级 mux 时最易写反；现有 TB 全是分拍驱动 |
| **`MULTI_BIND=0` 分支** | `:61` | 构建里常量折叠，网表里根本不存在；但另外两个顶层用它 |
| 锚点 ±256 钳位边界 | `:43` | 两个端点的取整行为没验证 |
| 释放后再次 bind 的锚点捕获 | `:55` | 三态只在特定序列下走 |
| 同一 finger 绑第 3 个组 | `:56-71` | TB 只到 2 个组 |
| 32 指全满 | 全局 | TB 最多 4 个 contact |

---

## 5. 功能取舍菜单

### 5.0 完整实测矩阵（**含构建参数**，这是本轮最大的变量）

| 配置 | `place_option` | Logic | CLS | Setup | Hold | 结论 |
|---|---|---:|---:|---:|---:|---|
| 基线（两功能都在） | 0 | 20338 | 10346 | −6.397 | −0.048 | FAIL |
| v3（retime，两功能都在） | 0 | 20234 | 10335 | 路由失败 | — | FAIL |
| **v3（retime，两功能都在）** | **1** | 20233 | **10327** | **−0.700** | −0.126 | **FAIL，但只差 0.7 ns** |
| v3（retime，两功能都在） | 2 | 20233 | 10327 | −0.700 | −0.126 | **与上一行 `board.bin` 逐字节相同 ⇒ 选项无效** |
| 关逐指表情 | 0 | 17957 | 10155 | +1.258 | +0.003 | PASS |
| **关逐指表情** | **1** | 17957 | 10121 | **+4.122** | +0.002 | **PASS** |
| 关视觉化 | 0 | 17545 | 10061 | +1.367 | −0.050 | FAIL（hold） |
| **关视觉化** | **1** | 17545 | 10024 | **+3.123** | +0.002 | **PASS** |
| 全功能 + place 1 + route 1 | 1/1 | 20233 | 10327 | — | — | **9747 unrouted nets（布线失败）** |

### 5.1 `-place_option 1` 是免费杠杆：−6.397 → −0.700

`build_m1_v5_p1`（两个功能都在，只把 `-place_option 0` 改成 `1`）：

- **第一次布通**（CLS 10327，基线 10346 时也能布通，但 v3 在 10335 时布不通）
- Setup **−6.397 → −0.700**，**白送 5.697 ns**
- Hold −0.048 → −0.126（变差 0.078）
- 两个裁剪配置也同步受益：+1.258 → **+4.122**、+1.367 → **+3.123**，且 novis 的 −0.050 hold 违例直接消失

代价是构建时间 344 s → 712 s。**项目一直用的是 0。**

#### 5.1.1 `-place_option` 的真实语义（本版本实测查证）

Gowin 1.9.11 的 `IDE/data/config/` 下有**两份**互相矛盾的定义，我一开始读错了：

| 文件 | 内容 |
|---|---|
| `rtlplacerouteoptions.xml`（整段被 `<!-- -->` 注释掉） | 只列 0/1，说"算法 1 牺牲时间效率以尝试找到更好的布局结果" |
| **`rtlplaceoptions.xml`（生效的那份）** | **0 = 速度优先，1 = 可布通性优先，2 = 时序优先，3/4 = 未命名"select a number"** |

⇒ 所以：

- `-place_option 1` 的官方定位是**可布通性优先**。它能第一次布通是设计意图，**+5.697 ns 是副产品**。
- **`-place_option 2` 才是"时序优先"**，项目从来没试过。这是本轮之前漏掉的最大一格。
- `rtlplaceoptions.xml` 里的 `-correct_hold_violation 1` 与二进制不符（见 §5.2），说明这份 XML 也略超前于 `gowin.dll`；
  但 `-place_option` 的取值表是 IDE 下拉框直接渲染的，可信度高。

同类查证：`-clock_route_order` 只有 0（按扇出排序）/ 1（按时钟频率排序），`-route_maxfan` 范围 1–100（当前 23），
`-replicate_resources` 默认开启（无 cmd，不可关）。**没有** hold 余量/加强修正之类的隐藏选项
（在 `gowin.dll` / `GowinProxy.dll` / `gwsyn.dll` 里搜 `-correct_hold*`、`-hold*`、`-fix*hold*`，只命中 `-correct_hold` 一个）。
⇒ **hold 在选项层面已经没有可调空间了。**

#### 5.1.2 但 `-place_option 2` 在本版本是空的（实测否决）

`build_m1_v6_p2`（`-place_option 2`，其余与 `build_m1_v5_p1` 完全相同，`cmd.do` 只差第 13 行一个数字）：

| | v5_p1（place 1） | v6_p2（place 2） |
|---|---|---|
| Logic / CLS / REG | 20233 / 10327 / 10880 | 20233 / 10327 / 10880 |
| Setup / Hold | −0.700 / −0.126 | **−0.700 / −0.126** |
| 最差 setup 端点 | `layers/state_0_s1 → u_finger/offset[21]_7_s1` | **完全相同** |
| **`board.bin` sha256** | `70c1f03d5bbf268e…` | **`70c1f03d5bbf268e…`（逐字节相同）** |
| **`board.db` sha256** | `6b1d87d0efaa3b99…` | **`6b1d87d0efaa3b99…`（逐字节相同）** |

`board.fs` 不同只是因为里面嵌了时间戳/用户码。

⇒ 这个版本的 PnR 二进制**只实现了算法 0 和 1**，`2/3/4` 被钳到 1。XML 里的"timing priority"
是 IDE 那一侧的描述，后端没落地。**选项层面到此为止。**

### 5.2 hold 的真相：不是坏掉，是修正器没有余量

- `-correct_hold 1` 在本版本是**有效选项**（`gowin.dll` 里确实存在，和 `-place_option` 并列），
  而且一直在工作：它把每条短路径推到刚好过线，所以 hold 表从 +0.002 到 +0.015 密集排列。
- IDE 的选项 XML 里写的 `-correct_hold_violation 1` **在本版本不存在**（二进制里搜不到）。
  实测把它写进 tcl 后 `cmd.do` 逐字节不变、结果完全相同 —— 是空操作。
- 唯一真正的违例（novis 的 −0.050，DSP→FF 路径）是修正器在 99% CLS 下**没有绕行余量**造成的；
  换成 `place_option 1` 后自动消失。
- ⇒ **+0.002 不是运气，是修正器收敛的正常结果。** 我之前说"不能靠 +0.003 签收"是错的。

### 5.2.1 全功能配置的 hold 到底违例在哪（`build_m1_v5_p1`，10 个端点 / TNS −0.753）

从 `board_tr_content.html` 的 TNS 汇总表读出的完整口径：

| 时钟 | 类型 | TNS | 违例端点数 |
|---|---|---:|---:|
| `core_clk` | Setup | **−2.308** | 5 |
| `core_clk` | Hold | **−0.753** | 10 |
| 其余 5 个时钟 | Setup/Hold | 0.000 | 0 |

Fmax 实测 **26.499 MHz**，约束 27.000 MHz ⇒ 差 **1.9%**。

把 `board.timing_paths` 里 25 条 hold 路径全部展开（脚本见 §7），10 个违例端点全部是
**"FF → BSRAM 写口"** 这一类，没有一条是逻辑路径：

| 违例端点 | 源 | 目的 | slack |
|---|---|---|---:|
| 3 | `u_wave/write_data_{0,5}_s0` | `u_renderer/wave_mem` | −0.126 |
| 6 | `receiver/word_shift_{2,4,20,41,43,54}_s0` | `u_nm/table_store/words` | −0.126 ~ −0.001 |
| 1 | `scan_storage/hard_register[0]` | `scan_storage/gap.memory` | −0.000 |

**关键形态**：同一批源寄存器里，有的被修到 +0.002 ~ +0.015，有的卡在 −0.126 —— 说明修正器
**在这批端点上找不到合法的延迟资源**，不是它没工作。而数据延迟只有 0.323 ns、捕获时钟比发射时钟
晚 0.44 ns（`board.timing_paths` 里 1.511 → 1.712 → 1.834，required 1.960）⇒ 缺的 0.126 ns
**全部是时钟偏斜，不是数据太慢**。

对照实验给出的因果链很干净：

| 配置 | CLS 余量 | hold 结果 |
|---|---:|---|
| 全功能 `v5_p1` | **41**（10327/10368，99.6%） | −0.126，10 端点 |
| 关逐指表情 `nofinger_p1` | 247 | **+0.002，0 端点** |
| 关视觉化 `novis_p1` | 344 | **+0.002，0 端点** |

⇒ **hold 能不能收，取决于有没有 CLS 余量给修正器插延迟。** 41 格不够，247 格够。
这就是为什么"单独修 hold 这条路径"在 RTL 层面无从下手：它不是一条路径的问题，是**整个器件满了**。

### 5.3 剩下的 0.7 ns 在哪

`build_m1_v5_p1` 的最差 setup 路径：

```
system/music/layers/state_0_s1/Q  →  system/music/core/contact_expression.u_finger/offset[21]_7_s1/D
```

**正是 `finger_pitch` 的 32 路写译码 + `offset[]` 写数据 mux。** 也就是说，
在"两个功能都保留"的配置里，`u_finger` 自己就是唯一的关键路径。
⇒ 重写 `finger_pitch` 的意义回来了，但目标变了：不是省 CLS，而是**打这条 0.7 ns 的路径**。

### 5.3.1 右手触控的泛音构造在哪条链上（PCB 影响评估，源码级确认）

用户问"砍可视化会不会影响右手触控屏的泛音构造、会不会影响 PCB"。逐级追了源码，结论是**两条独立支路**：

```
右手触控屏
  touch_valid / touch_active / touch_x / touch_y / touch_id
        │
        ▼  left_layer_music_probe.v:77   rh_performance_control
  gains[159:0]  =  16 个分音 × 10 位（q8）
        │
        ▼  tdm_top_owned.v:1153
  u_tdm.timbre_gain_q8  (tdm_engine_rh.v:136  input [PART*10-1:0])
        │
        ▼  tdm_engine_rh.v:500  raw_gain = first_slot ? timbre_gain_q8[9:0] : gain_frame[9:0]
  加法合成的分音增益  ← 这就是"泛音构造"
```

而可视化是**纯 sink**（`music_visualizer.v` 全文只有 3 个例化，端口全是输入 + LCD 输出）：

| 事实 | 证据 |
|---|---|
| `music_visualizer` **没有任何输出回到音乐核** | 端口表只有 `lcd_*` + `rendered_frames`/`late_frames`/`analysis_gaps`/`spectrum_sequence`（遥测计数） |
| 触控输入**根本不进** `music_visualizer` | `sdram_stream_probe.v:78` 的例化里没有 `touch_*`，触控走 `music(...)` 那一行 |
| 触控 → 泛音的通路与 `FINGER_EXPR` 无关 | `FINGER_EXPR` 只 gate `tdm_top_owned.v:1070` 的 `finger_pitch` 和 `tdm_engine_rh.v:698` 的 `finger_use` |
| LCD 时序驱动在可视化内部 | `mv_renderer.v:117` `mv_panel_driver u_panel(...)` |

⇒ **两种裁剪都不会动到泛音构造**。但对 PCB 的影响天差地别：

| 裁剪 | 失去的功能 | 引脚变化 | PCB 影响 |
|---|---|---|---|
| **`FINGER_EXPR=0`（砍逐指表情）** | 左手逐指滑音/揉弦（`finger_offsets`，18 位有符号，按组） | **0 个** | **无** |
| **关视觉化整块** | 480×272 SPI LCD 画面 / 频谱 / 波形，连 `u_panel` 时序驱动一起消失 | LCD 模组 + SPI 5 线 + 背光/供电 | **大**：连接器、走线、供电全白做 |

保留不变的（两种裁剪都一样）：音符触发与分配（`bridge`）、力度、**右手 16 分音增益**、包络、复音数、SDRAM 录音/回放、左手实体传感器扫描。

> **所以如果只能砍一个，应该砍 `FINGER_EXPR` 而不是可视化** —— 它 PCB 零影响，而且时序余量更好
> （+4.122 / +0.002 vs 可视化的 +3.123 / +0.002）。

### 5.3.2 如果逐指表情必须保、显示必须砍：**不要改 PCB，做 DNP**

用户判定逐指表情是核心功能，那 M1 只能砍可视化。但"砍可视化"**不等于"重新设计 PCB"**：

| 做法 | 改动面 | 时间成本 | 可逆性 |
|---|---|---|---|
| **A. 保留 LCD 封装，不贴片（DNP）** | PCB **零改动**；BOM 去掉 LCD 模组；固件把 LCD 引脚钉在静态安全电平 | **0**（PCB 车道完全不动） | **完全可逆**：M2 想加回来直接贴片 + 恢复 RTL |
| B. 真删 LCD：改原理图 → 重排重布 → 重新打样 → 重新贴片验证 | 连接器、SPI 走线、背光供电全删 | 一轮打样是串行的（打样→贴片→验证），而且 **Codex 已完成的布局要返工** | **不可逆** |

**推荐 A。** 理由：

1. **PCB 版本不用动**，Codex 的 PCB 车道不受任何影响，两边不会互相等。
2. **电气上是干净的**。关视觉化的实验里 LCD 引脚已经钉成：
   `lcd_reset_n=1'b0`（LCD 保持复位）、`lcd_cs_n=1'b1`（片选释放）、`lcd_sck=1'b0`、`lcd_mosi=1'b0`、`lcd_dc=1'b0`
   ⇒ 不贴片的模组位上没有翻转信号、没有额外电流，不存在浮空输入倒灌。
3. **保留了 M2 的退路**。PCB 上的封装和走线都在，M2 只要把面积腾出来（`finger_pitch` 重写 + 把
   `u_renderer`/`u_nm` 里的 LUT-ROM 与寄存器数组搬进 BSRAM），贴回 LCD 就能恢复画面，**不用再打一次板**。
4. 反过来说，选 B 就等于**用一次不可逆的板级改动，去换一个 M1 阶段还没定论的功能取舍** —— 这正是
   docs/88 里"不得静默删功能"要防的情况。

> 结论：**砍可视化 = 固件层的一个参数 + BOM 少一颗模组，PCB 不动。** 所以"重新设计 PCB"这个成本问题
> 其实不存在；真正存在的只是"M1 期间屏幕上没有画面"这个体验代价。

### 5.4 完整取舍菜单

| 取舍 | LOGICeq | ≈CLS | 实测结果 | 后果 | **PCB 影响** | 可逆 | 阻断 M2 |
|---|---:|---:|---|---|---|---|---|
| **`-place_option 1`（不是功能取舍）** | 0 | −34~−37 | **setup +5.7 ns** | 构建时间 ×2 | **无** | 高（一个参数） | 否 |
| **关逐指表情（`FINGER_EXPR=0`）** | −2211 | −180 | PASS（+4.122 / +0.002） | 失去左手逐指滑音/揉弦 | **无（0 引脚）** | 高（一个参数） | 否 |
| **关视觉化整块** | −2642 | −274 | PASS（+3.123 / +0.002） | 无画面/频谱/波形 | **大**：LCD 模组 + SPI 5 线 + 背光全废 | 高 | 否 |
| ├ `u_renderer`+`u_panel`+`u_spi` | ≈−1918 | — | — | 无画面，FFT 会一起被扫掉 | 大 | 高 | 否 |
| └ `u_fft` | −767 | — | — | 无频谱柱 | 高 | 否 |
| 传感器子树 | −1539 | ≈−125 | 未测 | 左手实体输入断开 | 低 | **是** |
| transport（UART/在线配置） | −510 | ≈−41 | 未测 | 无法在线改配置 | 低 | 是（调试链） |
| `u_nm` 音符映射 | −2409 | — | — | 音乐核心 | 不可 | 是 |
| 复音 32→16 | 未测 | — | — | 音乐能力腰斩 | 中 | 否 |
| **重写 `finger_pitch`** | −400~−800 | ≈−32~−65 | — | 保留全部功能，且打中 0.7 ns 那条路 | 高 | 否 |

> "≈CLS"按实测比例推算（关逐指表情 12.3:1、关视觉化 9.6:1），**不是线性关系**，只作量级参考。

---

## 6. 建议

1. **先把 `-place_option 1` 定为 M1 的构建基线。** 它是免费 5.7 ns，是唯一让"两个功能都保留"
   布通的配置，也是两个裁剪配置从 +1.3 ns 提升到 +3~4 ns 的原因。**不采用它，后面所有时序结论都是错的。**
   > 注意：`place_option 2`（XML 声称时序优先）与 `3/4` 在这个二进制里被钳到 `1`，实测 `board.bin`
   > 逐字节相同（§5.1.2）；`route_option 1`（按时序布线）与 `place 1` 组合出现 **9747 unrouted nets**（§5.0 矩阵）。
   > **所以构建基线只能是 `place 1` + `route 0`，没有更好的布局/布线算法。**
2. **hold 的根因是 CLS 满了，不是路径坏了。** 修正器在 `place_option 1` 下工作正常：两个裁剪配置
   都 TNS 0、0 端点。全功能配置仍有 −0.126（10 端点），因为它是 99.6% CLS；腾不出给修正器插延迟的余量。
   在 RTL 层面"单独修这条 hold"行不通（加一级写寄存器约 60 CLS，只剩 41 格）。
3. **缺口现在是 0.7 ns setup + 0.126 ns hold，不是 6.4 ns。** 这个量级不需要"砍一个功能"就能打平，
   但需要**面积**，三条路按性价比排序：
   - **重写 `finger_pitch` 的写路径**：关键路径正好在 `layers → offset[]`，重写直接打中；
     但 §1.2 拆解表明最大 LUT 项是 `offset[]` 的写数据 mux（≈576 LUT），不是 32 路搜索本身。
     而且省下的 400–800 LOGICeq 按实测斜率只换约 **−40~−65 CLS**，可能**不够**让 hold 闭合（需要 ~200 格）。
   - **配合其他面积优化**（把 `u_renderer`/`u_nm` 里的 LUT-ROM 或寄存器数组搬进 BSRAM）凑够余量，
     风险和工期高，且必须逐个行为等价性验证。
   - **小功能裁剪**：只砍 `u_fft`（−767 LOGICeq，无频谱柱）或只砍 `u_renderer`（−1918，无画面）。
4. **产品判定：逐指表情是核心功能，不能砍。** ⇒ M1 的取舍结论固定为**保逐指表情、砍可视化**。
   两条裁剪的实测对比（供记录）：

   | | 砍 `FINGER_EXPR` | 砍可视化 |
   |---|---|---|
   | 时序 | +4.122 / +0.002 | +3.123 / +0.002 |
   | 失去 | 左手逐指滑音/揉弦 | 画面/频谱/波形 |
   | 泛音构造 | 保留 | 保留 |
   | PCB | 0 引脚变化 | 见第 5 条 |

   砍 `FINGER_EXPR` 时序更宽，但**产品价值不足**；这个选择由产品决定，不由时序决定。
5. **砍可视化不需要重新设计 PCB，做 DNP。** PCB 保留 LCD 封装与走线，BOM 去掉模组，固件把
   `lcd_reset_n=0 / lcd_cs_n=1 / lcd_sck=0 / lcd_mosi=0 / lcd_dc=0` 钉成静态安全电平（§5.3.2）。
   **PCB 车道零改动、零等待，且完全可逆**：M2 腾出面积后贴回模组即可恢复画面，不用再打一次板。
   ⇒ 用一次不可逆的板级改动去换 M1 阶段尚未定论的功能取舍，是不该做的。
6. **M2 恢复画面的路径**：重写 `finger_pitch` 写路径（目标 −40~−65 CLS）+ 把 `u_renderer`/`u_nm` 里的
   LUT-ROM 与寄存器数组搬进 BSRAM（还有 13 块 BSRAM 空闲），凑到 ~200 CLS 就能把可视化加回来。
   这条路的工期和验证风险都高，不适合塞进 M1。
7. **B 路线（每指一份状态）仍然不建议**：它会破坏"释放尾音保留最后音高"，
   而现在的目标只是 0.7 ns，用 A 路线 + 写路径重定时就够。

---

## 7. 复现命令

```bash
cd D:/FPGA-Project/codex-builds/fpga-m1-agent-work

# hold 全景（只读解析，不产生码流）：展开全部 HOLD 块 + TNS 汇总表
python analyze_hold.py build_m1_v5_p1     # → evidence/hold-build_m1_v5_p1.json

# 面积（1–2 分钟，不布局不布线，不产生码流）
python synth_area.py synth_<label> --ref synth_v4_sl2.json

# 全功能 + 布局算法 1（本轮最佳：setup −0.700，第一次布通）
python build_board.py build_m1_v5_p1 nominal 4
python <handoff>/tools/audit_build.py --workspace . --label build_m1_v5_p1 --output evidence/v5-p1-audit.json

# 裁剪实验（测完均已还原）
#   关逐指表情：engine/src/left_layer_music_probe.v:81  FINGER_EXPR(1)→(0)，sha 5451b95b…
#   关视觉化  ：rtl/sdram_stream_probe.v:78  music_visualizer 例化换常量驱动，sha 74b20865…
python build_board.py build_m1_exp_nofinger_p1 nominal 4   # +4.122 / +0.002
python build_board.py build_m1_exp_novis_p1    nominal 4   # +3.123 / +0.002

# build_board.py 的 strategy 取值（本轮扩展，原包只支持 0/1）
#   0 = 默认（place 0, route 0）
#   1 = place 1 + route 1          ★ 全功能构建 9747 unrouted nets；v1_s1 也失败（9945 nets）
#   2 = route 1 only               （按时序布线，>15 min 未收敛，未取得结果）
#   3 = correct_hold_violation 1   （本版本无此选项，实测为空操作）
#   4 = place 1 only               ★ 本轮有效（可布通性优先）
#   5 = place 2 only               ← 与 place 1 board.bin 逐字节相同 ⇒ 选项无效
#   6 = place 2 + route 1          ← 同 1，未测
#   7 = place 3                    ← 同 1，未测
#   8 = place 4                    ← 同 1，未测
# 另：内部超时 900 → 1800 s（route/place 1 的全功能构建需 712 s，原 900 s 会误杀）

# 行为等价性
python tools/run_checks.py --workspace . --suite layers --run-id <id>
python tools/run_checks.py --workspace . --suite sensor --run-id <id>
```
