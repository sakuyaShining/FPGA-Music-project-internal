# 公开后执行计划 · 信息补救 · 设置变更

日期：2026-10-24
前提：用户已决定接受 `internal` 仓库公开。

---

## 零、先说一件事：两个文件没收到

| 文件 | 状态 |
|---|---|
| `91-产品规格与使用规则-v1-20261024.md` | **不存在** |
| `impl_pnr_board.fs` | **不存在** |

实际检查：`...\msg\file\` 下最新只有 **`2026-09`**，**没有 `2026-10` 目录**。

```
ls C:/Users/Sakuya/Documents/xwechat_files/wxid_.../msg/file/
→ 2025-10 … 2026-08 2026-09     # 无 2026-10
```

`find` 全盘搜 `*产品规格*` 和 `impl_pnr_board.fs` 也是零结果。**需要你重发，或直接给文件的实际落盘路径。**

> 参考：远端 `docs/02-技术方案/` 最新只到 **89 号**（10-22）。**91 号是你队友 10-24 新写的，还没进任何分支。**

### 关于 `impl_pnr_board.fs` 的提醒

`.fs` 是 Gowin 比特流，**本身不携带可验证的时序信息**。单独一个 `.fs` 只能烧板，不能证明 setup/hold 通过。要判断它是不是「好消息」，必须配套：

| 必需 | 用途 |
|---|---|
| `impl_pnr_board.rpt.txt` | 资源占用、DRC 结果 |
| `board.timing_paths` 或 `.tr.html` | setup / hold 是否收敛 |
| 对应的 commit / 源身份 | 确认烧的是哪版 |

远端 `state.json` 现在写的是 `programming_allowed: false`，两个探针 profile 都是 `sta: false`、`setup_ns: -6.397`、`hold_ns: -0.048`。**如果这个 `.fs` 是新的，必须先看时序报告再谈能不能烧。**

---

## 一、公开前审计结果（已扫完 1,163 个文件）

在 `4036d84a` 全量 grep：

| 检查项 | 结果 | 判定 |
|---|---|---|
| 密钥 / token / 私钥 | **零命中**（唯一命中是队友自己写的扫描脚本正则 `preserve_workspaces_20261022.py:17`） | ✅ 安全 |
| 手机号 | 零 | ✅ |
| 个人邮箱 | 只有 `fpgacamp.cn@outlook.com`（竞赛官方）、`steve@icarus.com`（Icarus 作者） | ✅ |
| 竞赛内部资料 | 已被 `.gitignore` 排除（`refs/past-years/`、`official-notices/`、`candidate-guides/` 等） | ✅ |
| **绝对路径** `C:\Users\Sakuya` / `D:\FPGA-Project` | **167 个文件** | ⚠️ 体面问题 |
| **会话 ID**（UUID） | 8+ 个文件（`AGENT-BOARD.md`、`construction-state.json`、`budget.json`…） | ⚠️ 体面问题 |
| **成本 / 单价 / 报价** | 8+ 个文件（`24-采购清单.md`、`采购范围与装配分工-r1.md`…） | ⚠️ 商业敏感 |

**结论：没有安全泄露。需要补救的是 3 类「体面 / 商业」问题，不是「危险」问题。**

而且队友已经很专业：`hardware/current/README.md` 里已经写了「上下文中的绝对路径和 session 只是原工作区出处，不可复用会话或重放事务」——**声明已经在了，只是没做技术拦截。**

---

## 二、我要补救哪些信息

### 2.1 原则：不改写历史

**不能**用 `git filter-repo` 洗掉那 167 个文件里的路径。原因：

| 后果 | 说明 |
|---|---|
| 18 个 `codex/preserve-*` 分支全部失效 | 它们是按旧 commit 建的快照 |
| 所有已有 clone 失效 | 包括队友手上那份 |
| 40+ 个 commit 哈希全变 | `state.json`、`manifest` 里登记的源身份全部对不上 |

**源身份哈希是这个项目治理的核心**（`engineering-sources-20261023.json` 逐文件登记 sha256）。改写历史 = 摧毁它。

### 2.2 改为「声明 + 拦截 + 新规」

| # | 补救项 | 做法 | 影响 |
|---|---|---|---|
| 1 | 绝对路径 167 文件 | 在 `README.md` 顶部加「路径说明」段：文档中 `C:\Users\...`、`D:\FPGA-Project\...` 均为**历史记录中的原工作区出处**，不代表当前可访问路径，不构成部署指引 | 零风险，只加说明 |
| 2 | 会话 ID | 同上段落一并声明 | 零风险 |
| 3 | 成本报价 | 在 `采购范围与装配分工-r1.md`、`24-采购清单.md` 顶部加一行：**报价为 2026-10-21 快照，非实时，不构成供货承诺** | 零风险 |
| 4 | 新增拦截 | 写 `tools/scripts/check_public_hygiene.py`：扫新增文件里的绝对路径 / 密钥 / 手机号，**只对 `git diff --cached` 生效**，不追溯历史 | 新文件不再犯 |
| 5 | 挂到 pre-commit | 本地 `.git/hooks/pre-commit` 调用上述脚本（不入库，各人自装） | 本地生效 |

> 第 4 项也可以做成 GitHub Actions，但对单人项目来说 pre-commit 更轻。

---

## 三、我要补哪些缺失的仓库要件

现在仓库是这样的：

| 项 | 当前值 | 问题 |
|---|---|---|
| `description` | **null** | GitHub 上搜不到、看不出是什么 |
| `license` | **none** | 默认「保留所有权利」，别人不能合法引用 |
| `topics` | **[]** | 无标签，不被检索 |
| `main` 分支保护 | **未保护**（API 返回 404） | 谁都能直推，包括误操作 |
| `secret_scanning` | **disabled** | 公开仓库免费功能没开 |
| `push_protection` | **disabled** | 同上 |
| `has_wiki` | false | 合理，文档都在 `docs/` |
| `has_issues` | true | 合理 |

---

## 四、我要改哪些设置（具体清单）

### 4.1 GitHub 仓库设置

| # | 项 | 现在 | 改成 | 谁来定 |
|---|---|---|---|---|
| 1 | Description | 空 | `基于 Tang Nano 20K (GW2AR-18) 的 FPGA 实时加法合成电子乐器 · 2026 高云杯` | 我写，你可改 |
| 2 | Topics | 空 | `fpga` `gowin` `tang-nano-20k` `additive-synthesis` `verilog` `electronic-instrument` | 我写 |
| 3 | **License** | **none** | **⚠️ 必须你定** | **你** |
| 4 | main 分支保护 | 无 | 要求 PR + 1 approval + 状态检查通过；禁止 force push | 我设 |
| 5 | Secret scanning | 关 | **开** | 我设 |
| 6 | Push protection | 关 | **开** | 我设 |
| 7 | Wiki | 关 | 保持关 | — |

### 4.2 License 为什么必须你定

| 选项 | 适用 | 对竞赛的影响 |
|---|---|---|
| **MIT** | 代码 | 最宽松，别人可商用；竞赛一般不禁止 |
| **Apache-2.0** | 代码 | 带专利授权，比 MIT 严谨 |
| **CERN-OHL-P v2** | **硬件（原理图/PCB）** | 专为开源硬件设计，你的 14 张原理图正需要 |
| **CC BY-NC-SA 4.0** | 文档 | 禁止商用 |
| **保留所有权利（不加）** | — | 别人不能合法复用，但作品仍是公开可看 |

**我的建议**：代码 `Apache-2.0` + 硬件 `CERN-OHL-P v2` + 文档 `CC BY-NC-SA 4.0`。三层分开，是开源硬件项目的标准做法。

**但如果竞赛规则要求「作品未公开发表」或「原创未开源」，加 License 可能有风险。这一条我不能替你判断。**

### 4.3 本地 Git 设置

| # | 项 | 现在 | 改成 |
|---|---|---|---|
| 1 | remote 数量 | **3 个**（internal / origin / public，后两个指向同一个 10-08 停更的私有仓库） | **只留 internal** |
| 2 | 权威分支 | 语义不清（`main` 落后 7 个提交） | 固定 `codex/current-engineering-sources-20261023`，`main` 只做 ff |
| 3 | 快照分支 | **18 个** `codex/preserve-*-20261022` | 打 tag `archive/20261022-preserve` 后删分支 |
| 4 | `.gitignore` | 已排除 `*.fs` `*.vvp` `*.log` `backups/` | **补**：`*.tsv` 原始轨迹（>1MB）、`*.zip`、`*.ttf` |
| 5 | pre-commit | 无 | 挂 `check_public_hygiene.py` |
| 6 | 本地工作区 | `main` @ 10-22，**10,631 个未跟踪 / 2,133 MB** | 抢救 35.7 MB，其余归档 |

---

## 五、执行顺序（等你确认后跑）

```
第 0 步  收到 91 号规格 + 时序报告（现在缺）
   ↓
第 1 步  抢救本地 35.7 MB → D:/FPGA-Project/rescue-20261024.tar.gz
   ↓       （验证 tar 能解，否则不往下走）
第 2 步  git worktree add D:/FPGA-Project/authoritative-20261024 4036d84a
   ↓       python tools/scripts/engineering.py check
第 3 步  补 5 项信息声明（README / 采购文档顶部）
   ↓
第 4 步  加 check_public_hygiene.py + pre-commit
   ↓
第 5 步  GitHub 设置：description / topics / 分支保护 / secret scanning / push protection
   ↓       （License 等你定）
第 6 步  git remote remove origin && git remote remove public
   ↓
第 7 步  18 个 preserve 分支 → 打 tag → 删分支
   ↓
第 8 步  主工作区降级为归档，只保留 .git + 35.7 MB 抢救包
```

**第 1 步验证不通过就停。** 第 2 步 `engineering.py check` 不通过也停，先看报告。

---

## 六、我不会做的事

| 不做 | 为什么 |
|---|---|
| 不改写 git 历史 | 会摧毁 18 个 preserve 分支、所有 clone、和 `engineering-sources` 里登记的逐文件 sha256 身份 |
| 不删主工作区的 2,133 MB | 除非第 1 步抢救包验证通过，且你明确同意 |
| 不动 `hardware/current/native/` 里的 `.eprj3` / `.epcb2` | 这是嘉立创原生工程，改一个字节就破坏身份哈希 |
| 不烧 `impl_pnr_board.fs` | 远端规定 `programming_allowed: false`，且没看到时序报告 |
| 不替你选 License | 涉及竞赛规则 |
| 不把 `internal` 改成 private | 你已决定接受公开 |

---

## 七、需要你现在回的三件事

| # | 问题 | 卡住什么 |
|---|---|---|
| 1 | **91 号规格 + `.fs` + 时序报告重发**（或给实际路径） | 第 0 步，全流程的入口 |
| 2 | **License 选哪个**（或明确「不加」） | 第 5 步 |
| 3 | 第 1 步抢救包做好后，**是否同意清理主工作区的 2,133 MB** | 第 8 步 |
