# Agent 协作板

> **这是什么**：多个 agent 同时推进本项目时的唯一协调入口。
> **不是什么**：`notes/agent-collaboration-log.md` 是给评委看的人机协作评分素材（AMD 2026「大模型协作与技能包 15 分」），记录的是"用户采纳/否决了什么"，**不要**往里写 agent 之间的调度信息。
>
> 本文件必须**提交在 `main`**。新建工作树请从 `main` 拉，不要从旧提交（如 `2770e63`）拉，否则看不到本板。

最后更新：2026-10-22 00:55（WorkBuddy 建立）

---

## 1. 轴与所有权

项目当前有三条可并行的轴。**一个 agent 在同一时间只认领一条轴**，跨轴必须先改本表。

| 轴 | 内容 | 当前所有者 | 独占路径（只有所有者可写） |
|---|---|---|---|
| **A · 逻辑时序与资源** | `u_tdm` 关键路径、M1/M2、真实产品顶层 | **Codex**（`4d37`） | `experiments/nano20k_feasibility_*/`、`src/rtl/`、`experiments/joint_probe_resources_*/` |
| **B · PCB 与硬件制造** | 63 项未连通 → 0、DRC、Gerber、制造放行 | **WorkBuddy** | `hardware/`（06df）、`C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-RegionalRecovery-20261021-r21` |
| **C · 显示与交互驱动** | RA8875 命令层、双屏仲裁、推子/曲谱界面 | 待认领 | `experiments/ra8875_driver_*/` |

**A 与 B 的交界只有一个**：`hardware/review-manufacturing-20261019/expected-pin-nets.json` 与 17 脚面板 GPIO 表。**这一份是双方共读、只读**。谁要改引脚分配，先在本板登记，另一方确认后才能动。

### 为什么 B 必须有人做

PCB 打样 + 贴片 + 物流是**日历时间**，加算力压不下来；FPGA 逻辑可以加 agent 压。所以 B 是真正的关键路径。当前状态：14 网 / 63 个未连通对象，未放行制造。

---

## 2. 不可回退的决定（开工前必读）

以下已经用户或 Codex 87 号确定，**任何 agent 不得以"省资源"为由推翻**：

1. **双屏保留，不合屏、不缩小推子。** RA8875 出推子/编辑/曲谱，ILI9341 出完整音乐可视化。（Codex 87 号 §4.6）
2. **不削减**：32 组 × 16 分量、四槽分层、逐音滑条、录放、非易失、实体交互。
3. **不换平台**（Tang Nano 20K / GW2AR-LV18QN88C8/I7），**不改 PCB 接口**。
4. **左手是两排逐音滑条 + 独立八度条**，不是 8 个离散触摸键。
5. **右手是 7 英寸电容触摸 + 分区竖直推子**，规则：左右分区、同侧就近、两侧取算术中点、松手保持、推子间分区隔离。
6. **PCM5102A 在 52.734375 kHz 不可用**，用 PCM5122（TI SLAS859C §9.3.5.2 的 ±4% 检测窗口）。
7. **禁止下载码流、禁止制造放行**，除非用户明确批准。

---

## 3. 文档编号规则（防止再撞）

**已经撞过一次**：`87`/`88` 各存在两份（Codex 的 2026-10-22 版与 WorkBuddy 的 2026-10-19 版）。

规则：

- **Codex**：继续用 `docs/02-技术方案/NN-标题-日期.md` 顺序号，下一个可用号由 Codex 自取（87、88 已被占用）。
- **WorkBuddy**：**不使用** `NN-` 顺序号。新产出用 `WB-NN-标题-日期.md`，或直接写进自己的实验目录 `experiments/<axis>/README.md`。
- 任何 agent 新建 `NN-` 文档前，先 `ls docs/02-技术方案/ | grep -E '^[0-9]+-' | sort -n | tail -3` 确认最大号。

**待用户裁定**：WorkBuddy 既有的 `87-资源约束定位`、`88-硬件选型与BOM`、`89-渲染器RA8875化`（在 `D:/FPGA-Project/wb-worktree-20261019` 分支 `codex/wb-20261019`）如何归并——改名为 `WB-01/02/03`，还是并入 Codex 序列。**裁定前 WorkBuddy 不再新增 `NN-` 文档。**

---

## 4. 分支与提交规则

| 规则 | 原因 |
|---|---|
| **禁止在 detached HEAD 上留未提交成果** | `4d37`、`4a4b` 都还是 detached + 未提交，`git worktree remove` 一次就没了 |
| 分支命名：`codex/<topic>-<date>` / `wb/<topic>-<date>` | 一眼看出归属 |
| **收工必须 commit**，并在本板登记 commit hash | 否则另一方看不到 |
| **不 rebase / 不 force-push 任何共享分支** | |
| **`main` 只由用户合并** | 避免两个 agent 抢 main |
| 不改对方独占路径下的任何文件 | 见 §1 |
| **不重跑对方已签收的构建** | 会覆盖 `impl/` 产物。已发生过一次：`build_nominal_v4/impl` 被重跑覆盖（数字一致，无损，但不可再犯） |

### 构建产物约定

所有 Gowin 构建输出到 `D:/FPGA-Project/codex-builds/<轴>-<日期>/`，**谁的目录谁清**。禁止把别人的构建目录 `cp -a` 过来直接用——`build.tcl` 里写死绝对项目路径，不改就会拿旧工程重建（已踩过，白跑 8 分钟）。

---

## 5. 交接格式（每次收工必填）

在本板 §6 追加一条，五句话：

```
### YYYY-MM-DD HH:MM · <agent> · <轴>
- 做了什么：
- 在飞什么（未完成）：
- 卡在哪：
- 需要对方什么：
- 下一手从哪读（文件路径 + commit hash）：
```

**开工时先读 §6 最后两条**，确认没有别人在飞你要动的东西。

---

## 6. 交接记录

### 2026-10-22 00:55 · WorkBuddy · 建立协作板
- 做了什么：建立本板；确认 `agent-collaboration-log.md` 是评分素材不是协调板；认领 B 轴（PCB）。
- 在飞什么：无。
- 卡在哪：B 轴需要 LCEDA Pro 在运行才能重建原生会话（当前未运行）；`REGIONAL-WORK-IN-PROGRESS.json` 里的 session 是 Codex 的、已关闭不可复用，必须新开。
- 需要对方什么：Codex 确认 A 轴继续独占 `src/rtl/` 与 `experiments/nano20k_feasibility_*/`；确认 17 脚 GPIO 表暂不冻结（B 轴布线依赖它）。
- 下一手从哪读：`hardware/review-manufacturing-20261019/REGIONAL-WORK-IN-PROGRESS.json`、`bus-return-repair-20261022/remaining-networks.csv`。

---

## 7. 给用户的操作要点

1. **开新 Codex 会话时，第一句让它读**：`AGENTS.md` + `docs/00-协作/AGENT-BOARD.md`。
2. **新建工作树从 `main` 拉**，不要从 `2770e63` 拉。
3. **一个 agent 一次只干一条轴**。想加第三条轴，先在本板 §1 登记。
4. 遇到 §2 的七条红线，任何 agent 都不许自行放宽。

---

## 8. 远程与备份（2026-10-22 核实，两个坑）

### 坑一：`origin` 与 `public` 指向同一个公开仓库

```
origin    https://github.com/sakuyaShining/FPGA-Music-project.git
public    https://github.com/sakuyaShining/FPGA-Music-project.git   ← 同一个地址
internal  https://github.com/sakuyaShining/FPGA-Music-project-internal.git
```

`public/main` 上有一条提交叫「公开版快照：移出内部过程材料，只保留作品本体」——**说明不带 `-internal` 后缀那个仓库是对外的**。

而本地 `main` 里有 `docs/01-竞赛情报/02-什么才叫好作品-评审逻辑与高分画像.md` 这类评分策略分析。

> **硬规则：只推 `internal`。任何 agent 都不得执行 `git push origin` 或 `git push public`。**
> 这是一条现存的坑：Codex 若哪天顺手 `git push origin main`，内部材料就上公开仓库了。

分叉状态（本地 main = `10073fa`）：

| 远程 | 落后 | 领先 | 能否直接推 |
|---|---:|---:|---|
| `internal` | 61 | 0 | **可以，fast-forward** |
| `origin` | 126 | 2 | 双向分叉，禁止推 |
| `public` | 126 | 1 | 双向分叉，禁止推 |

推之前需确认 `FPGA-Music-project-internal` 在 GitHub 上确实是 **private**。

### 坑二：push 不等于备份

已跟踪内容只有 **509 文件 / 28.3 MB**：

| 目录 | 磁盘 | 已跟踪 | push 能否保护 |
|---|---:|---:|---|
| `docs/` | 8 MB | 123 文件 | 能 |
| `src/` | 42 MB | 128 文件 | 能 |
| `tools/` | 90 MB | 137 文件 | 能 |
| **`experiments/`** | **2103 MB** | **0 文件** | **不能** |
| **`notes/`** | **502 MB** | **2 文件** | **几乎不能** |
| `hardware/`（06df） | 304 MB | 0 文件 | 不能 |

**结论：推 main 只保护文档与源码，不保护引擎 RTL 实验、证据 JSON、构建输入。** 那些仍只有一份，要单独做物理副本（复制到 D: 盘）。

### LCEDA 原生会话

- 会话是 **headless** 的（`native-session.json` 与 `evidence/open.json` 均为 `"headless": true`），**不占屏幕、不需要可见窗口**。
- 但需要 bridge server（Node，端口 49620–49629）+ `lceda-pro.exe` 进程在跑。
- 会话归属 Windows 账户；当前是 `Sakuya`，与 Codex 同账户，可用。
- **`705cd8f3-…` 已关闭，不可复用**。新会话 ID 必须回写 `regional-recovery-20261021-r21/native-session.json`，否则 Codex 的 `native_project.py` 会拿死会话报错。
- 每次改完铜线，`PCB1.epcb2` 的 sha256 会变，**必须同步更新 `REGIONAL-WORK-IN-PROGRESS.json` 的 `pcb_sha256`**，否则 A 轴引脚核对会误判"源已漂移"。

---

