# M1 面积取舍评估：`finger_pitch` 重写风险与功能取舍清单

日期：2026-10-22　｜　对象：`engine/src/finger_pitch.v`（`u_finger`，NG=32 / NF=32 / MULTI_BIND=1）
性质：**决策材料，不是验收结论**。所有数字标注"实测"或"推算"。

---

## 0. 三个最重要的结论

### 0.1 本轮第一次拿到 `PASS scoped structural STA`

`build_m1_exp_nofinger`（把逐指表情整块关掉，仅为测量，非产品决定）：

| 指标 | 基线 `build_ref_v0` | `build_m1_exp_nofinger` |
|---|---:|---:|
| Setup slack | **−6.397** | **+1.258** |
| Hold / Recovery / Removal | −0.048 / +33.016 / +1.876 | **+0.003 / +33.107 / +1.795** |
| TNS / 违例端点 | −355.644 ns / 186 | **0.000 ns / 0** |
| Fmax（约束 27.000） | 23.023 MHz | **27.949 MHz** |
| Logic / CLS / Register | 20338 / 10346 / 10760 | 17957 / **10155** / 10020 |
| 路由 | 完成 | **完成，exit 0，344.9 s** |

证据：`evidence/exp-nofinger-audit.json`、`build_m1_exp_nofinger/`。

**第二个实验（关视觉化）也做了**：setup 更好（+1.367），但 hold 差 50 ps（1 个端点）。
两个配置的完整对照见 §5。唯一"setup+hold 双清"的是**关逐指表情**这一版。

### 0.2 关键路径已经换人：不再是音乐，是视觉化

新的 16 条最差路径**全部**是 `system/visualizer/u_renderer/py_6_s1/Q → u_renderer/u_panel/held_pixel_*/D`
（slack +1.258 … +3.686）。**音乐引擎的 setup 路径已经跌出前 20 名（slack > +3.686）**，
即从 −6.397 至少改善了 **10 ns**。

原因不是"少算了 2211 个 LOGICeq"，而是 **`u_finger`（1708 LUT + 809 FF）原本压在音乐布局区里**，
把它整个移走后，TDM 引擎与它的 20 个存储块得以紧凑放置，长线消失。
§0.1 里 28.84 ns 的线延迟里那 25.1 ns 集中在 8 条线上的现象，与这个解释一致。

### 0.3 重写 `finger_pitch` 单独**不足以**闭合时序

| 项 | 数值 |
|---|---:|
| 实测斜率（本次） | 180 CLS 换回 7.655 ns ⇒ **0.0425 ns/CLS** |
| 闭合 −6.397 ns 需要的面积 | **约 150 CLS** |
| `u_finger` 整块关掉换来的 CLS | **180 CLS（实测）** |
| 重写能拿回的（乐观） | 500–800 LOGICeq ⇒ **约 40–65 CLS** |
| 覆盖率 | **25%–40%** |

而且重写**不改变关键路径**——现在卡的是 `u_renderer → u_panel`。
⇒ 只有在"已决定保留逐指表情、且还需要再挤一点"时，重写才有意义；它不能作为主修法。

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

**两个"整块开关"都实测了。** 结果不对称，而且都不完美：

| 配置 | Logic | CLS | Setup TNS | Hold TNS | 结论 |
|---|---:|---:|---:|---:|---|
| 基线（两个功能都在） | 20338 | 10346 | −355.644（186 端点） | −0.048（1 端点） | FAIL |
| v3（retime，两个功能都在） | 20234 | 10335 | 路由失败 | — | FAIL |
| **关逐指表情（`FINGER_EXPR=0`）** | 17957 | 10155 | **0.000（0 端点）** | **0.000（0 端点）** | **PASS** |
| **关视觉化（整块）** | 17545 | 10061 | **0.000（0 端点）** | **−0.050（1 端点）** | **FAIL（hold）** |

### 5.1 关视觉化这一版：setup 更好，但 hold 差 50 ps

- 面积：LOGICeq −2642（19921 → 17279）、LUT −2120、REG −1648、SSRAM −22、RAM16 49→39
- Setup **+1.367**（比关逐指表情的 +1.258 更好），TNS 0，0 个违例端点
- **Hold −0.050 ns，1 个端点**：`scan_storage/hard_register[7] → system/music/control/panel/bank/id_q_10_s0/D`
- 新的关键 setup 路径变成 `system/music/layers/state_2_s1 → u_finger/offset[*]_s1/D`
  ⇒ **在这个配置里，`u_finger` 自己就是关键路径**（它是 `music` 里剩下最大的块）

### 5.2 一个更重要的发现：hold 一直在噪声底

| 构建 | Hold slack | 违例路径 |
|---|---:|---|
| 基线 | −0.048 | `scan_storage/hard_register[5] → panel/bank/tx_q_10` |
| 关逐指表情 | **+0.003** | `u_uart/data_1 → serial_configuration.receiver/buffer`（不违例） |
| 关视觉化 | −0.050 | `scan_storage/hard_register[7] → panel/bank/id_q_10` |

三条里两条卡在 `scan_storage → panel/bank` 这同一结构上，量级都是 50 ps，符号随机。
**归档基线本来就是 Hold −0.048，即这个项目从来没有过干净的 hold 签收** —— 这不是本轮引入的。

⇒ 结论修正：**setup 在两种裁剪下都能过；剩下的唯一阻碍是一个 50 ps、1 个端点的 hold 问题**，
它属于"插一级流水/加一个延迟"的工程问题，不是功能取舍问题。但 50 ps 的余量意味着
任何配置的 hold 都是运气级，签收前必须刻意修，不能靠某次构建恰好 +0.003。

### 5.3 完整取舍菜单

| 取舍 | LOGICeq | ≈CLS | 实测结果 | 后果 | 可逆 | 阻断 M2 |
|---|---:|---:|---|---|---|---|
| **关逐指表情（`FINGER_EXPR=0`）** | −2211 | −180 | **PASS（setup+hold 双清）** | 失去接触表情/逐指滑音 | 高（一个参数） | 否 |
| **关视觉化整块** | −2642 | −274 | setup PASS / **hold −0.050** | 无画面/频谱/波形 | 高 | 否 |
| ├ `u_renderer`+`u_panel`+`u_spi` | ≈−1918 | — | — | 无画面，但 FFT 会一起被扫掉（`levels` 无其他消费者） | 高 | 否 |
| └ `u_fft` | −767 | — | — | 无频谱柱 | 高 | 否 |
| 传感器子树 | −1539 | ≈−125 | 未测 | 左手实体输入断开 | 低 | **是** |
| transport（UART/在线配置） | −510 | ≈−41 | 未测 | 无法在线改配置 | 低 | 是（调试链） |
| `u_nm` 音符映射 | −2409 | — | — | 音乐核心 | 不可 | 是 |
| 复音 32→16 | 未测 | — | — | 音乐能力腰斩 | 中 | 否 |
| **重写 `finger_pitch`（A/B 路线）** | −400~−800 | ≈−32~−65 | — | 保留全部功能 | 高 | 否 |

> "≈CLS"按实测比例推算（关逐指表情 12.3:1、关视觉化 9.6:1），**不是线性关系**，只作量级参考。

---

## 6. 建议

1. **不要做重写。** 它最多补 25–40% 的缺口；而且在"关视觉化"这个配置里它恰好变成关键路径，
   在"关逐指表情"这个配置里它又完全无关 —— 收益不稳定，不该作为主修法。
2. **功能取舍现在只剩一个判断：保哪一个。** 两条路都实测过，setup 都能过：
   - **保视觉化、关逐指表情** → setup+hold **双清**（这是目前唯一干净 PASS 的配置）
   - **保逐指表情、关视觉化** → setup 更好（+1.367），但 hold 差 50 ps（1 个端点）
3. **判断依据不该是时序**（两者几乎等价），而是产品与项目状态：
   - 逐指表情的实体输入**还没做**（docs/38："实体触控、触点追踪/绑定上游、同音多指独立性仍未完成"），
     PCB 未完成，现在板上没有触点硬件 —— 它在 M2 才需要
   - 视觉化是**已经实现、现在就能演示**的
   - 但反过来，逐指表情是这台乐器的核心输入概念（滑条 + 连续位置），视觉化只是显示
4. **无论选哪条，hold 都必须单独修。** 它一直在 ±0.05 ns 摆动，归档基线就是 −0.048；
   这不是本轮引入的，也**不能靠某次构建恰好 +0.003 就算签收**。
   目标：把 `scan_storage → panel/bank` 这条 50 ps 路径用一级流水或显式延迟消掉。
5. 若两个功能都要保留：需要更小的组合裁剪（视觉化内部分档、复音降档），
   或接受"这台器件放不下全部功能"作为 M1 结论，把 −6.397 ns 记为设计约束转 M2。
6. 只有在"已决定保留逐指表情、并且已经裁掉别的东西、还需要再挤一点"时，
   才做 A 路线（可证明等价）；B 路线不建议——收益只比 A 多 200–300 LOGICeq，
   但把"可证明等价"换成了"靠不完整的测试兜底"。

---

## 7. 复现命令

```bash
cd D:/FPGA-Project/codex-builds/fpga-m1-agent-work

# 面积（1–2 分钟，不布局不布线，不产生码流）
python synth_area.py synth_<label> --ref synth_v4_sl2.json

# 实验一：关逐指表情（把 engine/src/left_layer_music_probe.v:81 的 FINGER_EXPR(1) 改成 (0)）
#   测完已还原，sha256 5451b95b…
python build_board.py build_m1_exp_nofinger nominal 0
python <handoff>/tools/audit_build.py --workspace . --label build_m1_exp_nofinger --output evidence/exp-nofinger-audit.json

# 实验二：关视觉化（把 rtl/sdram_stream_probe.v:78 的 music_visualizer 例化换成常量驱动）
#   测完已还原，sha256 74b20865…
python build_board.py build_m1_exp_novis nominal 0
python <handoff>/tools/audit_build.py --workspace . --label build_m1_exp_novis --output evidence/exp-novis-audit.json

# 行为等价性
python tools/run_checks.py --workspace . --suite layers --run-id <id>
python tools/run_checks.py --workspace . --suite sensor --run-id <id>
```
