# 未提交清单 · 远端基线充分性 · 版本控制基准

日期：2026-10-24
三个问题：① 尚未提交的有哪些 ② 远端够不够当基线 ③ 能不能以它为中心基准。

---

## 一、尚未提交的东西

### 1.1 总量

| 口径 | 数量 |
|---|---:|
| 真正未跟踪（未被 `.gitignore` 排除） | **10,631 文件 / 2,133 MB** |
| 被 `.gitignore` 正常排除（不算未提交） | 7,672 文件 |
| 已修改未提交（tracked） | 3 个：`README.md`、`docs/01-竞赛情报/monitoring-log.md`、`tools/state/monitor-state.json` |

**注意**：`git status` 只显示 51 个目录条目（`experiments/`、`notes/`…），实际内部是 10,631 个文件。上一份报告按文件系统总量估的 3.06 GB 偏大，**准确值是 2,133 MB**。

### 1.2 但 73% 是同一内容的多份拷贝

按大小分组（>100 KB）后：

| 文件 | 份数 | 单份 | **浪费** |
|---|---:|---:|---:|
| `compat-compat.tsv` | **17** | 36.4 MB | **582.8 MB** |
| `layers-compat.tsv` | **17** | 34.0 MB | **543.6 MB** |
| `sensor-compat.tsv` | **11** | 25.0 MB | **249.5 MB** |
| `engine.zip`（改前备份） | 2 | 60.9 MB | 60.9 MB |
| `LolitaMono.ttf` | 4 | 11.5 MB | 34.6 MB |
| `lolita.ttf` | 4 | 11.4 MB | 34.2 MB |
| `envelope.tsv` | 6 | 5.2 MB | 26.0 MB |
| 其他 | — | — | 23.4 MB |
| **合计可省** | | | **≈ 1,555 MB** |

**2,133 MB 里，唯一内容只有约 578 MB。**

### 1.3 `.v` 源文件：6,479 个只有 297 个不同

| 项 | 值 |
|---|---:|
| `experiments/` 下 `.v` 文件 | **6,479** |
| 按 SHA-256 去重后 | **297** |
| 体积 | 64.2 MB → **3.7 MB** |
| 最极端一份被复制 | **103 次** |

典型的「每个实验目录拷一份完整 `src/`」。**没有一个是新设计。**

### 1.4 按类型拆解（2,133 MB）

| 类型 | 体积 | 文件数 | 性质 | 处置 |
|---|---:|---:|---|---|
| `.tsv` | 1,557.5 MB | 81 | 回归轨迹，重复 17 份 | 留 1 份或留远端 `.gz` |
| `.zip` | 315.7 MB | 46 | 「改前备份」，git 历史已有 | 可弃 |
| `.ttf` | 91.7 MB | 8 | 字体，2 个唯一各 4 份 | 留 1 份 |
| `.v` | 64.2 MB | 6,479 | 唯一 297 个 | 留唯一 297 |
| `.txt` | 33.5 MB | 117 | 日志/报告 | 可弃 |
| `.html` | 25.0 MB | 203 | 报告 | 可弃 |
| `.pdf` | 16.2 MB | 11 | **datasheet** | **留** |
| `.json` | 11.5 MB | 1,025 | **EDA API 原始返回** | **留** |
| `.png` | 6.4 MB | 32 | 截图 | 留 |
| `.py` | 2.7 MB | 540 | 脚本（多为副本） | 留唯一 |
| `.hex` | 2.5 MB | 1,158 | 查表（远端已有） | 可弃 |
| `.in` | 2.2 MB | 3 | — | 留 |
| `.esch2` | 1.1 MB | 1 | **嘉立创原理图** | **留** |
| `.vh` | 0.5 MB | 87 | 头文件 | 留唯一 |

### 1.5 真正必须抢救的：35.7 MB / 1,113 文件

远端没有、且**不可再生**的（已按清单实测）：

| 内容 | 体积 | 为什么不可再生 |
|---|---:|---|
| `notes/` 的 `.pdf`（datasheet 11 份） | 16.2 MB | 厂家可能下架 |
| `notes/` + `experiments/` 的 `.json`（EDA API 原始返回、证据摘要） | ~11 MB | 要重跑嘉立创 API，接口可能已变 |
| `notes/` + `experiments/` 的 `.png`（截图） | ~5 MB | 不可重拍 |
| `hardware/`（53 件小样工程 + 成本调研，75 文件） | 3.0 MB | 含 `.eprj3` 原件 |
| `.esch2` 原理图 | 1.1 MB | 嘉立创工程内嵌 |
| `tools/scripts/` 6 个 `.py` + `src/board_diag/` 2 个 | 0.0 MB | 需确认远端 62 个脚本里是否已含 |
| **合计（实测清单）** | **35.7 MB / 1,113 文件** | 压缩后约 25 MB |

> **2,133 MB 里，真正值得抢救的是 35.7 MB —— 1.7%。**

---

## 二、远端够不够当基线

### 2.1 逐领域核查

| 领域 | 远端内容 | 判定 |
|---|---|---|
| **FPGA RTL** | `fpga/current/engine/src` 完整：含 `vel_wtab.hex` **和我改的 `.bak-20261023`**、`vel_shape.v`、`layer_dispatch.v`、`instrument_table.v`、`tdm_engine_rh.v` 等 | ✅ **齐** |
| **测试台** | `engine/tb` 13 + `sim/` 8 + `tb/` 12（含 `tb_vel_shape.v`、`tb_joint.v`、`tb_sensor.v`） | ✅ **齐** |
| **约束** | `constraints/` 4 个：`tdm_ship_owned.cst/.sdc`、`sdram_board.cst/.sdc` | ✅ **齐** |
| **判据脚本** | 22 个 `check_*.py` + `audit_*.py` + `build_board.py` / `build_product.py` | ✅ **齐** |
| **黄金证据** | `handoff_support/*/evidence/*.tsv.gz` —— **压缩版，0.53 MB 对本地 36.4 MB（68:1）** | ✅ **齐且更优** |
| **硬件** | `hardware/current/native/` 完整 `.eprj3` + `PCB1.epcb2`（`e098c5db`）+ **14 张原理图** + 面板 | ✅ **齐** |
| **BOM/采购** | 36 料号 / 227 件 / 217 SMT 位号 / 32 行外部采购范围 | ✅ **齐** |
| **主机** | `host/current/tools` 38 个 | ✅ **齐** |
| **文档** | `docs/02-技术方案` 98 个 + `docs/04-架构图` 16 | ✅ **齐** |
| **工具链** | `tools/scripts` 62 + `tools/pylib` | ✅ **齐** |
| **治理** | `project/` 94：4 组 review、state.json、5 个入口文档 | ✅ **齐** |

**结论：够。** 而且比本地更完整——本地 `src/` 根目录那份是 10-08 前的旧结构，远端 `fpga/current/` 是重组后的当前源。

### 2.2 远端自己承认的缺口

| 缺口 | 来源 |
|---|---|
| 完整产品顶层未实现、未验收 | `state.json`: `product_acceptance: false` |
| 历史音乐黄金回归**未通过**（第 6662 拍数值差异） | `COLLABORATION-CHECKPOINT-20261024.md` |
| PCB DRC **47 项未连通 / 13 网** | `construction-state.json` |
| `manufacturing_release: false`、`physical_tests: UNMEASURED` | 同上 |
| **PCF8575 / 16 键扩展未做**（按键只 5 颗 SW2–SW6） | BOM 里无 PCF8575 |
| 大屏线束未签核、屏 SKU/CTP 未闭合 | `采购范围与装配分工-r1.md` |
| `CPL_final: false`、`board_quantity_not_frozen: true` | `current-board-procurement.json` |

**这些是「未完成」，不是「缺失」。基线该有的都有，缺的是工作。**

---

## 三、能不能以它为中心基准

**可以。但有一个你必须先确认的问题。**

### 3.1 ⚠️ `internal` 是 public 仓库

| remote | 仓库 | 可见性 |
|---|---|---|
| **internal** | `FPGA-Music-project-internal` | **public** |
| origin / public | `FPGA-Music-project` | **private** |

**完整原理图（14 张）、PCB 工程、227 件 BOM、成本核算、采购报价，全部在一个公开仓库里。**

如果这是竞赛作品要公开，没问题；如果你以为它是私有的，**这是必须马上决定的事**。两个选项：

| 选项 | 操作 |
|---|---|
| 接受公开 | 什么都不用做 |
| 要私有 | GitHub 设置里改成 private，或在私有仓库建镜像后停止推 public |

**这个我不能替你决定。**

### 3.2 另外三个前提

| # | 前提 | 说明 |
|---|---|---|
| 1 | **权威分支是 `codex/current-engineering-sources-20261023`，不是 `main`** | `state.json` 明确注册。ahead 7 / behind 0，可 ff |
| 2 | **本地 38 MB 先抢救，2,095 MB 可弃** | 不抢救就 `reset` = 永久丢 datasheet 和 EDA 原始返回 |
| 3 | **用 `worktree` 而非 `checkout`** | 10,631 个 untracked 会挡住 checkout |

### 3.3 建议的治理动作（防版本控制再乱）

现在乱在哪：3 个 remote 指向 2 个仓库、18 个 preserve 分支、origin 停更 16 天、本地落后 15 提交、2 GB 未提交。

| # | 动作 | 理由 |
|---|---|---|
| 1 | **删掉 `origin` 和 `public`** | 都指向 10-08 停更的私有仓库，留着只会误推 |
| 2 | **只保留 `internal` 一个 remote** | 单一事实来源 |
| 3 | **权威分支固定为 `codex/current-engineering-sources-20261023`**，`main` 只做 ff 合并 | 避免"到底看哪个分支" |
| 4 | **18 个 `codex/preserve-*-20261022` 归档后删** | 一次性快照，占分支列表 55% |
| 5 | **大文件永不进 git**：`.tsv` 原始轨迹、`.zip` 备份、`.ttf` | 远端已示范：用 `.gz`，68:1 |
| 6 | **每次提交前跑 `python tools/scripts/engineering.py check`** | 远端规定的核对命令 |

---

## 四、执行方案

### 第 1 步：抢救 35.7 MB（必做，先于一切）

用 `git ls-files` 生成精确清单，避免 glob 误伤：

```bash
cd "C:/Users/Sakuya/FPGA-Music-project"

git ls-files -o --exclude-standard > untracked-all.txt
{ grep -E '^(hardware/|src/board_diag/)' untracked-all.txt
  grep -E '^notes/.*\.(json|pdf|png|esch2)$' untracked-all.txt
  grep -E '^experiments/.*\.(json|png)$'   untracked-all.txt
  grep -E '^tools/scripts/(audit_board_samples|check_board_diag_sim|prepare_board_diag|project_baseline|recheck_board_regctl|test_board_hardware)\.py$' untracked-all.txt
} > rescue.txt

wc -l rescue.txt          # 应为 1113
tar -czf "D:/FPGA-Project/rescue-20261024.tar.gz" -T rescue.txt

# 验证：能列出条目，压缩后约 25 MB
tar -tzf "D:/FPGA-Project/rescue-20261024.tar.gz" | wc -l
```

> 清单已在本机实测：**1,113 文件 / 35.7 MB**。

### 第 2 步：检出权威源（不动主工作区）

```bash
git worktree add "D:/FPGA-Project/authoritative-20261024" 4036d84a
cd "D:/FPGA-Project/authoritative-20261024"
python tools/scripts/engineering.py check
```

### 第 3 步：主工作区降级为归档

确认第 2 步能跑通后，主工作区只保留：
- `.git`（历史不丢）
- 抢救包里的 38 MB

其余 2,095 MB 可删。**删之前先确认 `rescue-20261024.tar.gz` 能正常解开。**

### 第 4 步：治理

```bash
git remote remove origin
git remote remove public
git remote -v          # 应只剩 internal
```

---

## 五、一句话总结

| 问题 | 答案 |
|---|---|
| 尚未提交有哪些 | **10,631 文件 / 2,133 MB**，但 **73% 是重复拷贝**，唯一内容 578 MB，**真正不可再生只有 35.7 MB（1.7%）** |
| 远端够不够当基线 | **够**。11 个领域逐项核查全部齐，黄金证据还是压缩版（68:1），比本地更优 |
| 能不能以它为中心基准 | **可以**。前提是先确认 **internal 是 public 仓库**这件事，然后抢救 35.7 MB、用 worktree 检出 `4036d84a`、删掉两个废 remote |
