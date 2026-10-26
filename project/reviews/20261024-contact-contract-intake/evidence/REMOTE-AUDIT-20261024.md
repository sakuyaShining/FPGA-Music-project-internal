# 远端 Git 检查报告

日期：2026-10-24
目的：确认哪个远端可作为唯一可靠版本。

---

## 一、结论

| 问题 | 答案 |
|---|---|
| 哪个远端可信 | **`internal`** → `github.com/sakuyaShining/FPGA-Music-project-internal` |
| 哪个分支是权威源 | **`codex/current-engineering-sources-20261023`** @ `4036d84a`，**不是 `main`** |
| 本地能否直接切 | **能，不用联网**。本地对象库已有 `4036d84a` |
| 能不能当"产品版本" | **不能**。远端自己写 `product_acceptance: false`、`manufacturing_release: false`、`physical_tests: UNMEASURED` |

**"唯一可靠"的正确含义是「唯一可信的开发起点」，不是「可交付的产品版本」。**

---

## 二、三个 remote 的真实状态

| remote | 仓库 | 可见性 | 最后推送 | 大小 | 判定 |
|---|---|---|---|---:|---|
| **internal** | `FPGA-Music-project-internal` | **public** | **2026-10-24 04:24 UTC**（北京 12:24） | 170 MB | ✅ **活的，唯一权威** |
| origin | `FPGA-Music-project` | **private** | 2026-10-08 10:14 UTC | 10 MB | ❌ **16 天未动，废弃** |
| public | 同 `FPGA-Music-project` | private | 同 | 同 | ❌ 与 origin 完全重复 |

> `origin` 和 `public` 指向**同一个**私有仓库，停在 10-08。它们是早期版本，**不要再推任何东西进去**。

---

## 三、internal 的分支地图（33 个）

| 类别 | 数量 | 说明 |
|---|---:|---|
| **权威源** | 1 | `codex/current-engineering-sources-20261023` @ `4036d84a`（10-24 12:24） |
| 主干 | 1 | `main` @ `100b35bd`（10-24 00:58）—— **比权威源落后 7 个提交** |
| 快照备份 | 18 | `codex/preserve-*-20261022`，一次性恢复存档，**不是活跃任务** |
| 其他历史 | 13 | `codex/project-version-closure`、`codex/v1-behavior-freeze`、`backup/*`、`repair-20261004` 等 |

### 3.1 权威源为什么不是 main

`project/state.json` 原文：

```json
"engineering_checkpoint": {
  "source_branch": "codex/current-engineering-sources-20261023",
  "product_acceptance": false
}
```

`main...codex/current-engineering-sources-20261023` = **ahead 7 / behind 0**，可直接 fast-forward。

落后的 7 个提交（全是实质工程进展，不是文档）：

| commit | 时间(UTC) | 内容 |
|---|---|---|
| 374a84d6 | 10-23 17:34 | 对齐产品规格与公开协作交接 |
| 9c150d98 | 10-23 18:00 | 登记 score-live FIFO 规则，隔离黄金力度差异 |
| fd3feda5 | 10-23 18:36 | 分离 music profiles，记录 tail-first 分配契约 |
| 33a18189 | 10-23 19:21 | 验证 32 组共享音符资源协调器 |
| bff7c4e9 | 10-23 23:08 | 共享音符资源接真实 TDM 音频后端 |
| 6e899f87 | 10-24 00:22 | 接四槽部分渲染器，修 velocity 缩放/并发准入缺陷 |
| **4036d84a** | **10-24 04:24** | **路由 tagged live/score 事务，保留排队取消与失败时序证据** |

**这 7 个提交比本地和 main 都新，是当前最前沿的 FPGA 工作。**

---

## 四、本地落后多少

| 项 | 实际 |
|---|---|
| 主工作区分支 | `main` @ `3824391d`（**2026-10-22 01:06**，两天前） |
| 落后 `internal/main` | **15 个提交** |
| 领先 | **0**（纯落后，无本地提交） |
| 本地对象库 | **已含 `4036d84a`**（= 远端最新），**无需 fetch** |

### 4.1 本地有 51 项 untracked

| 路径 | 规模 | 远端有吗 |
|---|---|---|
| `notes/` | **1208 文件 / 502 MB** | **远端 notes 只剩 7 个条目** |
| `experiments/` | 整个目录 | 远端有，但只留 `nano20k_feasibility_20261021` |
| `hardware/` | 整个目录 | 远端有 `hardware/current/`（新结构） |
| 其他 | `.obsidian/`、若干单文件 | — |

**关键风险**：本地 notes 里 10-15~19 的实验记录，在远端 main **完全不存在**：

| 关键词 | 远端命中数 |
|---|---:|
| `board-audio` | **0** |
| `cost-survey` | **0** |
| `joint-timing` | **0** |
| `pitch-memory` | **0** |
| `seven-inch` | **0** |

远端做过**激进瘦身**：502 MB 的本地笔记 → 7 个条目。这些历史**只存在于本地**（或某个 preserve 分支）。

> **所以不能直接 `git reset --hard`。** 切之前必须先把这 502 MB 备份出去。

---

## 五、远端有什么是我不知道的（最重要）

### 5.1 完整板已经画完了

`hardware/current/native/`：

| 文件 | 内容 |
|---|---|
| `FPGA-Music-U9ControlWork-20261023.eprj3` | 完整嘉立创工程 |
| `pcb/PCB1.epcb2` | **PCB 已画**，sha `e098c5db…`，**227 件 / 616 孔** |
| `panel/Panel1.epan2` | 面板 |
| `sch/Schematic1/` | **14 张原理图** |

14 张原理图清单：

```
01_Nano_headers          02_Shift_and_memory     03_Display_harnesses
04_PCM5122_AUX           05_Power                06_Controls
07_Scan_lane_0 ... 12_Scan_lane_5                13_Power_off_isolation
14_Protected_power_entry
```

### 5.2 我前两轮说"缺 5 类"，其中 3 类早就画了

| 我说缺 | 实际 |
|---|---|
| 电源**零器件** | ❌ **错**。有 `05_Power` + `14_Protected_power_entry` + `13_Power_off_isolation`，器件是：**DMP2035U-7**（PMOS 防反接）+ **MF-MSMF110/16-2**（自恢复保险丝）+ **TPS2553DBVR**（限流开关）+ **AP2112K-3.3 ×2**（LDO） |
| 无 PCM5122 | ❌ **错**。`04_PCM5122_AUX` 已画，BOM 里 `C962071 PCM5122PWR` ×1 |
| 只有 2×4067 | ❌ **错**。`07~12_Scan_lane_0..5` 共 6 条，BOM 里 `74HC4067PW` ×6 |
| 无 PCF8575 | ✅ **对**。BOM 里没有 PCF8575，按键只有 5 颗（SW2–SW6），16 键扩展确实未做 |
| 无屏座 | ⚠️ **部分**。有 `J10` = 2.54-1×12P 反弯针（屏接口），但大屏线束未定 |

### 5.3 板子上还有这些我不知道的东西

| 器件 | 作用 |
|---|---|
| `TCA9517DGKR` | I²C 电平转换/缓冲 |
| `74LVC1G157GV` | 2:1 多路选择 |
| `SN74LVC244APWR` | 八缓冲 |
| `SN74LVC1G17DBVR` | 单施密特 |
| `TPD4E02B04DQAR` ×24 | ESD（我之前说"草稿无 ESD"，是 53 件小样，不是这块板） |
| `PZ254V-11-16P` ×6 | 6 组电极线束座（J20–J25），每组 14 电极 + 2 地 |
| `B2B-XH-A` (J13) | XH 2.5 mm 2P 电源输入 |
| `2.54-1*3P` (J12) | AUX 3 针接口（**不是 3.5 mm 座**，插座是面板件） |
| `RC0603FR-071KL` ×87 | 87 路电极串阻 |

### 5.4 但板子没有放行

| 项 | 值 |
|---|---|
| `drc.Connection Error` | **47** |
| 未连通网络 | **13** |
| `phase` | `MOSI_MAIN_CLOSED_47_13NETS_616VIAS_NOT_FAB` |
| `manufacturing_release` | **false** |
| `physical_tests` | **UNMEASURED** |

> 注意：`采购范围与装配分工-r1.md` 里写"当前 74 未连通"，而 `construction-state.json` 是 **47 项 / 13 网**。两个数字不一致，**以 construction-state.json 为准**（它是机器状态）。

---

## 六、我前两份采购文档作废

远端 `project/COLLABORATION-CHECKPOINT-20261024.md` 原文：

> `fpga/current/upstream-notes/` 保留 WorkBuddy 原文作来源证据，其中 `JLCPCB-ORDER-PACKAGE`、`POST-PCB-BOM` 和 `AUX-SCREEN-PRODUCT-BOM` **依据 53 件四滑条小样推断整板为空，不能代表当前整板**。

我的 `JLCPCB-ORDER-PACKAGE-20261023.md` 和 `POST-PCB-BOM-20261023.md` 已被收进远端 `fpga/current/upstream-notes/`，定性为**历史证据，非权威**。

**真实采购口径**（`current-board-procurement.json`）：

| 项 | 值 |
|---|---|
| 板上元件 | **227 件**（215 SMT + 12 通孔） |
| 料号 | **36 个** |
| SMT 位号 | **217 个**（含 5 个按键） |
| 通孔件 | **13 个/板** |
| 报价假设 | 2 块 SMT 载板 + 1 块补焊 13 通孔；5 块裸板 |
| 板尺寸 | **140 × 100 mm**，2 层 1 oz 1.6 mm FR-4 |
| `CPL_final` | **false** |
| `board_quantity_not_frozen` | **true** |

**我猜的 300×200 mm 是错的**，实际 140×100。

---

## 七、建议的切换方案（不动主工作区）

本地对象库已有 `4036d84a`，**不需要 fetch**（当前代理对 GitHub 不稳定，CONNECT 经常 502）。

```bash
cd "C:/Users/Sakuya/FPGA-Music-project"

# 第 1 步：先备份本地 502 MB untracked（不可省）
tar -czf "D:/FPGA-Project/backup-local-20261024.tar.gz" \
    --exclude=.git --exclude=sim_build .

# 第 2 步：把权威源检出到独立目录（detached，不建分支、不动 main）
git worktree add "D:/FPGA-Project/authoritative-20261024" 4036d84a

# 第 3 步：在权威源里跑核对
cd "D:/FPGA-Project/authoritative-20261024"
python tools/scripts/engineering.py check
```

**为什么用 worktree 而不是 `git checkout`**：

| 做法 | 后果 |
|---|---|
| `git checkout codex/current-...` | 主工作区 51 项 untracked 会被同名文件挡住，可能冲突 |
| `git reset --hard` | **直接删掉 502 MB 本地历史笔记，且不可恢复** |
| **`git worktree add`（推荐）** | 主工作区原样保留，新目录是干净的权威副本 |

**第 4 步（可选）**：把 `D:/FPGA-Project/authoritative-20261024` 设为唯一开发入口，主工作区降级为"本地历史归档"。

---

## 八、需要你确认的三件事

| # | 问题 | 为什么必须你定 |
|---|---|---|
| 1 | 本地 `notes/` 那 502 MB 历史实验记录，**要还是不要** | 远端已删。要 → 得先提交到某个分支；不要 → 备份后即可丢弃 |
| 2 | 权威源用 `codex/current-engineering-sources-20261023`，还是等它合进 `main` | 现在是 ahead 7 / behind 0，可以 fast-forward；但谁来做这次合并需要明确 |
| 3 | 板子 DRC 47 项未连通 / 13 网，**谁来继续** | 远端记录当前施工 owner 是会话 `01a15ee5-…`，是否续接需要你授权 |
