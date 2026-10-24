# 交接包分析：`handover(1).zip`（build_prod2 / `tdm_product_top`）

收到时间 2026-10-25。核对事实见 `evidence/handover-receipt.json`（含逐文件 SHA256）。

---

## 一句话结论

**能用，但只能用来上板验证，不能用来改 RTL。**

包里的码流是可信的、时序是干净的、工具与本仓库完全对得上；
但**它不是本仓库源码构建的** —— 100 个构建输入里 11 个哈希不同、6 个文件在本仓库
任何提交中都不存在。这 6 个恰好就是「84 电极模拟通路」这一层，也就是我们一直
认定为缺失的部分（`D-022` 的 G2 / G3 就卡在这里）。

---

## 一、可以确认的事实

### 1. 包没坏

`checksums.txt` 里 8 个文件的 SHA256 与实测**逐一相符**。

### 2. 时序确实干净

`时序报告.txt` 是逐路径原始转储（2834 行），没有汇总段，所以我自己按
「每块首字段 = slack」的口径解析了一遍：

| 项 | 结果 |
|---|---|
| SETUP 路径块 | 25 条，最小 slack **+10.413 ns** |
| HOLD 路径块 | 25 条，最小 slack **+0.205 ns** |
| 负 slack 条数 | **0** |

⇒ 说明书里「setup/hold 违规均为 0」成立。**这是本包最有价值的一项**：
它说明这套设计在 27 MHz 下有充裕余量，我们自己 PnR 时也有参照。

### 3. 寄存器/引导序列与本仓库一致

`selfcheck.ps1` 期望的 7 个引导值（`0x6E=0x80`、`0x6F=0x05`、`0x48=0x80`、
`0x5A=0x02`、`0x60=0x00`、`0x5B=0x00`、`0x50=0x00`）与本仓库
`tdm_top_owned.v` 的引导表**完全一致**。

`tools/play_note.py` 与本仓库 `fpga/current/tools/play_note.py` **逐字节相同**。

⇒ 说明队友是在我们的 `tdm_top_owned` 之上扩展的，协议层没分叉。

### 4. 码流格式正常

`board.fs` 是 Gowin 文本格式（`//Copyright (C) 2...` 开头，7,264,154 B）；
`board.bin` 是 Flash 用二进制（`FF FF FF...` 开头，907,418 B）。

---

## 二、关键问题：码流不是本仓库构建的

`构建记录-run.json` 有 100 条逐文件 SHA256（98 个 `engine/` + 2 个 `constraints/`）。
拿它们对本仓库 `fpga/current/` HEAD 逐个比：

| 类别 | 数量 |
|---|---|
| 哈希一致 | **83** |
| 哈希不同 | **11** |
| 本仓库任何提交中都不存在 | **6** |

### 2.1 仓库里根本没有的 6 个文件

| 文件 | 从名字看是什么 |
|---|---|
| `pad_mux84.v` | 84 电极模拟 MUX（6× CD74HC4067） |
| `pad_position.v` | 电极 → 位置（重心插值） |
| `pad_scan_v2.v` | 新版扫描器 |
| `strip_note_map.v` | strip → 音符映射 |
| `tdm_product_top.v` | 产品顶层（本次 `top`） |
| `tdm_product_v3.v` | 另一版产品顶层 |

> 已用 `git log --all` 确认：这 6 个文件在本仓库**任何分支、任何提交**里都没有，
> 本机 18 个 worktree 里也搜不到。源码只在队友机器上。

### 2.2 哈希不同的 11 个文件

`instrument_sensor_probe.v`、`layer_dispatch.v`、`left_contact_bridge.v`、
`left_layer_music_probe.v`、`left_music_probe.v`、`note_map_owned.v`、
`pad_pitch.v`、`rc_strip_positions.v`、`tdm_top.v`、`tdm_top_owned.v`、`tdm_top_rh.v`

这 11 个里有 4 个正是我们缺口清单上的位置：

| 缺口 | 文件 | 说明 |
|---|---|---|
| G1 | `rc_strip_positions.v` | 队友版与我们的 G1 修复（输出 `area`）不是同一版 |
| G2 / G3 | `left_contact_bridge.v` | 逐 strip 力度 + 重心单位换算都在这 |
| G4 | `pad_pitch.v` | 码流里是 `964ae87e…`，我们刚修完是 `c6617335…` |

**不能假定队友版已经修了这些缺口** —— 哈希不同既可能是修好了，也可能是
从更早的提交分叉出去的。必须拿到文件才能判断。

### 2.3 我们有、但构建里没有的 3 个文件

`scan_bus_arbiter.v`、`scan_shift165.v`、`sensor_frontend_board.v`

⇒ 队友把我们的 165 扫描总线 + 84 电极前端**换成了另一套**
（`pad_scan_v2` + `pad_mux84` + `pad_position`）。这不是我们这条线的演进方向，
是并行分支。

---

## 三、这份码流到底走哪条输入通路？

`时序报告.txt` 的层次路径里，`u_product` 下只出现两个实例：`u_rst` 和 `u_top`。
而 `u_top` 里有 **`legacy_input.u_pad`**（8 次出现在关键路径上），
**没有** `external_input`。

对照本仓库 `tdm_top_owned.v`：

```verilog
parameter integer LEGACY_PAD = 1,
generate if(LEGACY_PAD) begin: legacy_input
    pad_scan #(.NCH(16)) u_pad ( ... )      // 16 路 RC 电极
end else begin: external_input
```

⇒ 这份码流的 `u_top` 走的是 **`LEGACY_PAD=1`** 分支，即音高输入来自 16 路 RC 电极，
不是 84 电极。

**但有两种解释都能自圆其说，必须问队友：**

- **解释 A**：`tdm_product_top` 通过 `tdm_top_owned` 的排针 `ev_*` 端口
  （`ev_valid/ev_on/ev_note/ev_vel`）把 84 电极的事件注入进来，
  16 路 pad 悬空 ⇒ 零事件。这样 84 通路是通的。
- **解释 B**：`tdm_product_top` 只是个薄包装（复位 + LED），
  音符真的来自 16 路 RC 电极 ⇒ **84 电极通路没接进音符链**。

时序报告只收录关键路径，不等于完整网表，所以从包内材料**无法判定**。
这决定这份码流能不能用来验 84 电极，是当前最该问清的一件事。

---

## 四、能推进什么 / 不能推进什么

### ✅ 能推进（这是实打实的收获）

1. **上板 bring-up**：`board.fs` + `selfcheck.ps1` 可以直接验证
   「码流在跑 + UART 通 + 引导序列完整」，这把「烧 v1 到裸 Nano 20K 验音频链路」
   这一项从"等队友给码流"变成"现在就能做"。
2. **音频链路**：`play_note.py note 60` 能验 I²S + 功放是否出声。
3. **时序参照**：+10.413 ns / +0.205 ns 是这套设计在 27 MHz 下的真实余量，
   可作为我们自己 PnR 的对照基准（此前 README 里那组 13690/20736、+17.372 ns
   是 10-09 的历史值，不能当现状）。
4. **协议一致性已验证**：引导表、`play_note.py` 都对得上，说明后续联调不会
   在寄存器层面踩坑。

### ❌ 不能推进

1. **任何 84 电极的 RTL 工作** —— `pad_mux84.v` / `pad_position.v` /
   `strip_note_map.v` / `pad_scan_v2.v` / `tdm_product_top.v` 全都不在手上。
2. **G2 / G3 的修复** —— 需要 `left_contact_bridge.v` 的队友版本才能判断
   是否已经改过。
3. **把队友的成果合进本仓库** —— 现在连 diff 都算不出来。

### ⚠️ 两个必须记住的限制

- `hardware_programmed = false`：**队友自己也没在真机上跑过**这份码流。
  所以它只是"构建成功 + 时序通过"，不是"已验证可用"。
- 说明书要求接受 `Verify Failed / 0x00006020`：因为用了
  `-use_sspi_as_gpio 1` 把 SSPI 配置口当普通 IO，读回校验必然失败。
  这意味着**除了行为表现，没有第二条路能确认配置真的加载对了**。

---

## 五、要队友补什么（按优先级）

1. **`tdm_product_top.v` + `tdm_product_v3.v`** —— 先看顶层接线，
   就能判定第三节的解释 A/B。
2. **那 6 个新文件的源码**，以及这 11 个改动文件相对本仓库的 diff
   （或者干脆给一个 commit / 分支名，让我们自己 fetch）。
3. **`pad_pitch.v` 的队友版**：确认它的 `vel_bus` 是不是也是 64 位
   —— 如果是，G4（C5 力度串音）在他们的构建里同样存在。
4. **资源占用报告**（LUT / 寄存器 / BSRAM 用量）。包里只有时序，没有面积，
   而我们现在正需要这个数来规划 84 电极通路的余量。

---

## 六、建议的下一步

1. **先上板**（不依赖队友）：烧 `board.fs` → `selfcheck.ps1` → `play_note 60`。
   这一步能把"硬件是否好的"与"我们的 RTL 是否正确"彻底解耦。
2. **同时发消息要源码**（第五节 4 项）。
3. 源码到手之前，**不要在 RTL 上继续猜** —— 特别是 G2/G3，
   否则很可能和队友的实现撞车、白做一遍。
