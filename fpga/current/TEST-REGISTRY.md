# 测试台登记表（TEST-REGISTRY）

> 2026-10-25 建立。此前 26 个测试台、两套互不知情的驱动脚本、零登记表。
> 后果已经发生过两次：`audio_clk_en.v` 的注释引用了 `tb_audio_clk_en` 半年，
> **文件根本不存在**（采样率零覆盖）；`tb/tb_board_scan.v` 跑过、文档里写着
> "ALL PASS"，但没有任何脚本能重跑它。

## 0. 怎么跑

```bash
python tools/run_all_checks.py            # 全跑，出一张表
python tools/run_all_checks.py --fast     # 只跑 run_sims（约 90 s）
python tools/run_all_checks.py --list     # 只出清单 + 无驱动体检
python tools/run_all_checks.py --only tb_octave,check_sensor
```

两套驱动，历史原因，都保留：

| 驱动 | 范围 | 风格 | 耗时 |
|---|---|---|---|
| `tools/run_sims.py` | `sim/tb_*.v`（11 个） | 单模块级，编译+跑一体 | 秒级 |
| `check_*.py`（12 个） | `tb/` 与根目录的 `tb_*.v`（15 个） | 整链级，Python 参考模型对拍 | 十几秒到几分钟 |

`check_*.py` 共用 `common.py`：它会记录本次编译用到的每个输入文件的 SHA256，
跑完再核一遍。**跑的时候不要改 `engine/src/**`**，否则会看到
`AssertionError: ('inputs changed during execution', ...)` —— 那不是 RTL 错，是文件被动过。

## 1. 登记表

### 1.1 `sim/tb_*.v`（驱动：`tools/run_sims.py`）

| 测试台 | 守的是什么 | 判据数 | 最近结果 |
|---|---|---|---|
| `tb_rst_gen` | 复位序列时序 | — | PASS |
| `tb_beacon` | UART 心跳帧格式 | — | PASS |
| `tb_pad_velocity` | 触摸行程 → 力度映射（`pad_scan`） | — | PASS |
| `tb_vel_shape` | 力度曲线 + `REG_LIVE_MASK` 默认值 | — | PASS |
| `tb_pad_chain` | 端到端：触摸→力度→音符事件；**含换八度不打断在奏音（P11/P12）** | 8 | PASS |
| `tb_pad_velmap` | 25 音高通道的力度索引不别名（缺口 G4） | 83 | PASS |
| `tb_audio_clk_en` | **采样率 52734.375 Hz**：A(16)/B(18) 双配置各 6 项，含 sample_en 与 lrck 1→0 的对齐契约 | 12 | PASS |
| `tb_octave` | **八度档 5 格单电极直读**（节点 75..79）：逐格/全按/滞回/坏节点/标定/地址核对 | 17 | PASS |
| `tb_board_scan` | 载板扫描前端：165 位序、595/165 仲裁持有、整体连通 | 9 | PASS |
| `tb_decay2` | 双段衰减 | — | PASS |
| `tb_strike` | 激发模式（规格 §6 验收第 8 条） | — | PASS |

### 1.2 `tb/*.v` 与根目录 `tb_*.v`（驱动：`check_*.py`）

| 测试台 | 驱动 | 守的是什么 | 最近结果 |
|---|---|---|---|
| `tb_delta` | `check_delta.py` | 三配置逐拍比对 delta 帧（120k cycles/配置） | PASS |
| `tb_scan_store` | `check_scan_store.py` | 扫描器 + 存储：行协议、越界、背压 | PASS |
| `tb_scan_store` | `check_scan_variant.py` | 扫描存储的**变异对照**（换成错误实现必须 FAIL） | **BROKEN**，见 §2 |
| `tb_joint` | `check_joint.py` | 整链联仿：扫描→存储→重心→引擎→PCM→回放 | PASS |
| `tb_joint` + `tb_mac_joint` | `check_joint_variant.py` | 联仿变异对照（MAC 资源路径） | **BROKEN**，见 §2 |
| `tb_positions` | `check_sensor.py` | 160 帧独立参考、标定、坏节点、端点、宽重心、去抖、滞回、背压、协议重同步 | PASS |
| `tb_sensor` | `check_sensor.py` | 6 lane × 96 节点 → 25 条位置，物理字到标定位置的整链 | PASS |
| `tb_area` | `check_sensor.py` | 接触面积（G1）：零接触/坏节点/标定清零/宽面积 | PASS |
| `tb_pitch_memory` | `check_pitch.py` | 音高存储器读写/复位/同址双写 | PASS |
| `tb_native` | `check_native.py` | 原生通路（NG=128） | PASS |
| `tb_renderer` | `check_renderer.py` | 渲染器：**8388608 像素穷举** + 单像素变异必须被拒 | PASS |
| `tb_envelope` | `check_envelope.py` | 包络状态机与 Python 参考模型逐拍比对 | **BROKEN**，见 §2 |
| `tb_phase_wrap` | `check_phase_wrap.py` | 相位回绕（divider 15 的两次翻转） | PASS |
| `tb_compat_music` / `tb_layers` / `tb_sensor_layers` | `check_engine_compat.py` | 引擎兼容层（71 条轨迹逐字节对拍金标） | **金标不可复现**，见 §2 |

合计 26 个测试台：**21 个由能通过的驱动跑到**，5 个只在坏掉的脚本里出现（`tb_mac_joint`、`tb_envelope`、`tb_compat_music`、`tb_layers`、`tb_sensor_layers`）；`tb_scan_store` 与 `tb_joint` 各有两套驱动，坏的是「变异对照」那套。

## 2. 四个坏掉的 check 脚本（已定位，未修）

这四条都不是"少写了测试"，而是**测试设施自己烂了**。登记在此，避免下次又当成"跑一下应该没事"。

| 脚本 | 症状 | 根因 | 修它要做什么 |
|---|---|---|---|
| `check_scan_variant.py` | 编译失败：`parameter GAP_SIZE not found in tb_scan_store.dut` | `tb/tb_scan_store.v` 给 `probe_scan_store` 传 `GAP_START`/`GAP_SIZE`，而 `rtl/` 侧被换进来的那个实现没有这两个参数 —— 变异对照的 RTL 与测试台漂移了 | 给 `rtl/` 侧实现补上 `GAP_START`/`GAP_SIZE` 形参（参照 `evidence/wrong-*.v` 的写法），或把变异体换成支持这两个参数的新版 |
| `check_joint_variant.py` | 同上（`rtl/joint_timing_top.v:40`） | 同源 | 同上 |
| `check_envelope.py` | `ValueError: invalid literal for int() with base 10: 'x'` | 包络 trace 里出现 `x`。要么 RTL 在复位未完成时输出了未初始化值，要么 tb 在复位前就开始采样 | 先看 trace 第一行：若 `x` 只出现在第 1 行，是 tb 采样早了一拍；若中间也有，是 RTL 有未初始化状态 —— 后者是真 bug，值得单独查 |
| `check_engine_compat.py` | 先 `FileNotFoundError`（已修），修好后 `AssertionError: engine behavior changed`（**金标与当前 RTL 不符**） | 两个独立的坑：① 参考轨迹在仓库里是 `compat-all.tsv.gz`，脚本却读 `.tsv` —— 在干净 clone 上**从来跑不起来**；② 解开之后 193475 行里有 56495 行与当前 RTL 不同 | ① 已修（读不到 `.tsv` 时从 `.gz` 解压到 `evidence/`）；② 需要重新采集金标，**但金标是"行为基线"，重采等于承认行为变了，必须单独拍板**，不能顺手做 |

> 四个里 `check_envelope.py` 最值得先修：`x` 若出现在 trace 中间，说明包络有未初始化路径，
> 而包络是"挂音/爆音"类问题的常见来源。

### 2.1 `check_engine_compat.py` 的金标到底有多旧（已定位到"从没跑过"）

`check_engine_compat.py` 会在 3 个提交上重跑（各自建临时 worktree，把 `.gz` 解开后跑）：

| 提交 | 说明 | 结果 |
|---|---|---|
| `f18ccbb4` | 引入本检查、发布第一版 manifest 的提交 | **FAIL** |
| `9950776e` | 25 音位改动之前 | **FAIL** |
| `0b6cd216` | 26→25 全仓落地 | **FAIL** |
| `d1b64af7` | 交接包核对（本轮起点） | **FAIL** |

结论：**这个金标在引入它的那个提交上就已经对不上**，不是后来改坏的。
在干净 clone 上它甚至跑不到比对那一步（`.tsv` 不存在）。

一个待验证的猜测：`tb_compat_music.v` 里的 `$readmemh` 用相对路径，而脚本第 9 行会把
`"../` 替换成 `"../../` 再写进 `fpga/current/`。如果金标是用**未替换**的 tb 采集的，
两边的表加载路径不同（加载失败时 `$readmemh` 不报错，只是数组留空）——
那金标记录的其实是"表没加载"的行为。**修之前先验这一条，别急着重采。**

## 3. 三条判据本身的教训（比测试台更值钱）

这三条都发生过，且都是"测试全绿但实际没测到"：

1. **位回文让位序测试变成假的**（`tb_board_scan`）
   第一版向量用 `0xA5/0x5A/0x3C`，全 PASS；把 `MSB_FIRST` 改成 0 反向验证，**仍然全 PASS** ——
   三个数都是位回文，整体颠倒后数值不变。换成 `0x01/0x9b` 后立刻抓到。
   ⇒ **判据写完必须做反向验证：把实现改坏，测试台必须红。**

2. **取值巧合让别名测试漏一格**（`tb_pad_velmap`）
   力度表用 `vtab[16+i]=9-i`，`k=4` 时两边都等于 5，于是通道 20 的别名没被发现
   （17 处失败里独缺 20）。改成 `vtab[16+i]=vtab[i]+6` 并加判据 [0] 自检力度表。
   ⇒ **测试数据要保证"正确实现与错误实现的取值不同"，这本身是一条判据。**

3. **判据读不出结果，等于测试台坏了**（`run_sims.py` × `tb_board_scan`）
   `tb_board_scan` 打印 `ALL PASS` / `=== 结果: 0 个失败 ===`，而 `run_sims.py` 只认
   `RESULT: PASS` 和 `PASS ——`，于是**全绿被判 FAIL**。已把第三种风格加进识别。
   ⇒ **汇总行是一种接口，改 tb 的汇总格式要同步改驱动。**

## 4. 本轮新增/改动的判据

| 文件 | 变更 |
|---|---|
| `sim/tb_audio_clk_en.v` | **新建**。此前 `audio_clk_en.v` 注释引用的同名文件根本不存在。12 项判据；3 个变异（丢整周期翻转 / 半周期差一 / 样本使能挪到半周期）全部被检出 |
| `sim/tb_octave.v` | **新建**。八度档 5 格单电极直读，17 项判据；把 `SINGLE_BASE` 加 1 的变异被检出 10 处 |
| `tools/check_audio_rate.py` | **新建**。静态核对"产品顶层到底给 `audio_clk_en` 传了什么"，并校验 `NSLOT == DIV_BCK × BCK_PER_LRCK`。仿真查不到这一层（仿真自己传参）。把 `tdm_top` 的 `DIV_BCK` 改成 18，报 3 个问题 |
| `sim/tb_pad_chain.v` | 新增判据 [5]~[8]：换八度不产生事件、在奏音不跟变、note-off 用锁存值、换档后新按按新档位 |
| `tools/run_sims.py` | 注册 `tb_audio_clk_en` / `tb_octave` / `tb_board_scan`；判据识别加第三种汇总风格 |
| `tools/run_all_checks.py` | **新建**。统一跑两套驱动 + 无驱动体检 |
| `tb/tb_board_scan.v` | `sck_a` 由 `reg` 改 `wire`（原来只有 `-g2012` 能编译，`-g2005` 报"不能由连续赋值驱动"） |
| `check_engine_compat.py` | 参考轨迹改为"没有 `.tsv` 就从 `.tsv.gz` 解压"（原写法在干净 clone 上必然 FileNotFoundError） |
| `tools/scripts/engineering.py` | `check()` 跳过 .gitignore 忽略的文件（否则跑过一次 `check_*.py` 就会因为 `fpga/current/evidence/` 而永远 check 不过）；`MANIFEST` 指向 `engineering-sources-20261025.json` |
