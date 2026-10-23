# Agent 协作板

> **这是什么**：多个 agent 同时推进本项目时的唯一协调入口。
> **不是什么**：`notes/agent-collaboration-log.md` 是给评委看的人机协作评分素材（AMD 2026「大模型协作与技能包 15 分」），记录的是"用户采纳/否决了什么"，**不要**往里写 agent 之间的调度信息。
>
> 本文件必须**提交在 `main`**。新工作树先fetch核对私有内部仓库实际main；日期分支仅兼容，候选管理PR须明确尚未发布。禁止从旧提交（如`2770e63`）推断当前设计。

管理覆盖更新：2026-10-23（见§11）。接手先查main、governance及producer登记；旧交接的施工数字与日期分支不是实时状态。

最初建立：2026-10-22 00:55（WorkBuddy）

---

## 1. 轴与所有权

项目当前有三条可并行的轴。**一个 agent 在同一时间只认领一条轴**，跨轴必须先改本表。

| 轴 | 内容 | 当前所有者 | 独占路径（只有所有者可写） |
|---|---|---|---|
| **A · 逻辑时序与资源** | 音乐、M1、复位/力度/激发候选与完整载板顶层 | 独立FPGA会话，准确ID未登记；D盘源见producers.json | 未明确owner前不接管；4d37当前只做管理，不继续认领功能实现 |
| **B · PCB 与硬件制造** | 持续施工、DRC、Gerber、制造放行 | 会话“查看 huangyongtao 最新进展”，ID `01a15ee5-fa24-7501-8475-ad28a0f08939` | `hardware/`（06df）、当前U9ControlWork原生施工副本；实际入口由producer/review及实时原生身份确定 |
| **C · 显示与交互驱动** | J10命令层/触控服务、推子/曲谱界面 | 待认领 | `experiments/ra8875_driver_*/` |

**A 与 B 的接口合同**：由硬件入口登记的`expected-pin-nets.json`及当前GPIO映射，双方共读、只读。旧17脚/双屏表不能自动签收取消J11后的接口；先核对所选原生源身份。谁要改引脚分配，先登记并由双方确认，不能根据其他会话的显示控制器误解重排引脚。

### 为什么 B 必须有人做

PCB 打样、贴片与物流需要日历时间。施工数量只在相应review的观察时间有效；当前入口为producers.json → 硬件源/最新审阅，仍未放行制造。旧63项等数字仅为历史。

---

## 2. 不可回退的决定（开工前必读）

以下已经用户或 Codex 87 号确定，**任何 agent 不得以"省资源"为由推翻**：

1. **现行范围：保留J10右手泛音触控屏，用户已取消J11实体音乐可视化屏。** 2026-10-22硬件会话直接人类决定覆盖旧双屏红线，原话及turn见`project/versions/design-decision-20261023.json`。不据此削减其他功能；旧双屏实验保留历史。
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

### 2026-10-24 · Codex · 管理与工程交接
- 做了什么：接续4d37的工程整理，将FPGA、保存硬件、主机11版展开为current候选；清单341项，来源、恢复入口和隔离验证可追溯，详见project/ENGINEERING.md。
- 在飞什么：管理分支codex/current-engineering-sources-20261023，提交及实际远程身份以本次PR为准；未接管原owner目录。
- 卡在哪：历史音乐黄金对照存在差异；硬件47项未连通/13网，实体协议和完整产品未验收。
- 需要对方什么：在独立任务分支认领限定路径，按清单复现并交回结果，不用旧小样采购判断替代当前整板。
- 下一手从哪读：project/COLLABORATION-CHECKPOINT-20261024.md、project/reviews/20261024-engineering-publication/review.json；精确版本取包含本记录的Git提交与PR head，不预填未产生的远程SHA。

### 2026-10-22 00:55 · WorkBuddy · 建立协作板
- 做了什么：建立本板；确认 `agent-collaboration-log.md` 是评分素材不是协调板；认领 B 轴（PCB）。
- 在飞什么：无。
- 卡在哪：B 轴需要 LCEDA Pro 在运行才能重建原生会话（当前未运行）；`REGIONAL-WORK-IN-PROGRESS.json` 里的 session 是 Codex 的、已关闭不可复用，必须新开。
- 需要对方什么：Codex 确认 A 轴继续独占 `src/rtl/` 与 `experiments/nano20k_feasibility_*/`；确认 17 脚 GPIO 表暂不冻结（B 轴布线依赖它）。
- 下一手从哪读：`hardware/review-manufacturing-20261019/REGIONAL-WORK-IN-PROGRESS.json`、`bus-return-repair-20261022/remaining-networks.csv`。

---

## 7. 给用户的操作要点

1. **开新 Codex 会话时，第一句让它读**：`AGENTS.md` + `docs/00-协作/AGENT-BOARD.md`。
2. **新建工作树从已发布管理分支拉**；PR合入后再用包含新入口的main，不要从`2770e63`拉。
3. **一个 agent 一次只干一条轴**。想加第三条轴，先在本板 §1 登记。
4. 遇到 §2 的七条红线，任何 agent 都不许自行放宽。

---

## 8. 远程与备份（2026-10-22历史盘点，统计不代表当前）

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



---

## 9. 2026-10-22 管理收口检查点

用户已授权执行保全版本、同步GitHub、统一入口三步。本轮管理分支为`codex/project-management-20261022`（4d37）；没有移动其他活跃工程、没有改写其他工作树索引或分支。

- 共享入口：根README → `project/CURRENT.md` → `project/state.json`。旧正文中的工作区、会话和硬件计数是历史信息，当前取所选源码快照中的入口核对。
- GitHub：已核实internal为private；main及既有有效分支已同步。各工作区保全分支与精确提交见`project/versions/workspace-preservation-20261022.json`。保全不是产品验收。
- A轴：4d37候选已冻结；D盘M1有独立活跃工作区，owner身份尚待登记，临时关闭可视化的面积实验不得作为产品裁剪决定。
- B轴：保持06df及其硬件入口所有权；原生来源、pending试作、R15候选分别保全，不改板、不重放会话、不制造放行。
- 管理owner：本会话4d37，仅修改入口、登记、恢复工具和管理文档；未认领其他会话功能实现。main接合仍由用户完成。
- 下一步：合并本管理PR后，各owner从登记的来源继续提交并同步新检查点；目录迁移及功能接合另行审查。


## 10. 2026-10-23 最新设计与Git接手修复

本会话用户已明确授权：**本次代为合并PR #1并保留发布分支**。这是本次管理接合授权，不构成未来任意PR、功能合并或制造放行授权；实际合入结果查询GitHub，不凭本文预判。

- 做了什么：本会话继续管理轴，仅修改4d37入口、保全/恢复工具与管理文档。核对硬件会话人类决定，修正J11取消/J10保留；保全D盘新观察FPGA源码、测试、设计说明和所列硬件恢复包。
- 在飞什么：独立FPGA会话仍在改D盘候选，owner会话身份未完全登记；硬件会话“查看 huangyongtao 最新进展”（01a15ee5-fa24-7501-8475-ad28a0f08939）继续写06df及U9施工副本。本管理会话不接管它们。
- 卡在哪：没有完整产品顶层验收；原100输入的旧专项PASS不签收新候选；硬件总入口缓存与下级施工状态存在先后差异，必须核对实际原生哈希。
- 需要对方什么：各owner收工提交命名分支、精确输入/结果身份和源截止时间；未来修改不能隐含纳入本批已发布检查点。main继续按§4由用户合并。

### 本次PR #2合入授权

2026-10-23，本会话用户直接回答：“授权本次代为合并 PR #2，保留任务分支”。对应问题`call_9c1141282b434486bf7e2cfc891d285f`，PR为私有内部仓库`pull/2`。仅授权本次入口治理与协作说明PR，保留`codex/main-design-authority-20261023`；不构成未来PR、功能范围、码流下载或制造放行授权。实际合入与CI结果查GitHub。
- 下一手从哪读：`project/DESIGN-CURRENT.md`、`project/design-state.json`、`project/QUICKSTART.md`，发布分支`codex/project-management-20261022`；提交由实际远程分支及v2冻结标签解析，禁止凭日期冒充当前。


## 11. 2026-10-23 main authority and review freshness

- Management owner: current 4d37 session, branch codex/main-design-authority-20261023; no functional/CAD ownership taken.
- Authoritative publication: actual private remote main. Dated branch is fast-forward compatibility only; v1/v2 tags remain immutable.
- Decisions: project/decisions.json records accepted/proposed/superseded items with evidence; D-010 directly confirms retain J10 and existing controller route, superseding the external RA8875 cancellation interpretation.
- Freshness: project/governance.json/current review, 24h design review and6h active observations; --live detects actual local drift, missing roots are not green. Observe does not renew a review.
- Handoff: project/MAINTAINING-MAIN.md and NEXT-AGENT-PROMPT.md. Active unpublished code, FPGA owner identity gap and unvalidated hardware remain explicit. main merge still needs user approval for this new PR.
