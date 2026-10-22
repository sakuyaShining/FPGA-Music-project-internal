# 工程文件组织与版本控制调查

调查时间：2026-10-22 17:52—17:59，Asia/Shanghai。主盘点完成于17:52；后续补查单独记录。其他会话仍在工作，所有数字都是当时快照。

结论：项目存在实际的版本管理缺口。最大问题是源码、实验、验证证据、硬件原生工程散落在不同工作树和D盘；“磁盘最新”“已经提交”“已接入main”“远程已有副本”“通过了哪一级验证”缺少统一映射。目录数量本身不是主要问题。先建立版本保护和入口，再迁移目录。

本轮只读调查Git、工程文件和远程分支；新增本工作树的审计脚本与报告。没有移动、删除、改写既有工程，没有提交、切分支、合并、fetch、push、清理工作树或运行构建。没有接触设备或修改PCB。

## 1. 目前工程实际分布

| 位置 | 实际作用 | Git状态与边界 |
|---|---|---|
| `C:/Users/Sakuya/FPGA-Music-project` | 主目录，旧RTL、工具、38—86号文档，以及大量新实验 | main=`3824391`，跟踪509文件；2个已跟踪文件有修改，10,631个未跟踪路径 |
| `C:/Users/Sakuya/.codex/worktrees/4d37/FPGA-Music-project` | 本聊天87—89号文档、Nano20K候选、交接工具 | detached `2770e63`；盘点时184个未跟踪路径，不含随后生成的本报告；没有命名分支保护这些新增成果 |
| `C:/Users/Sakuya/.codex/worktrees/06df/FPGA-Music-project` | 当前硬件制造审查、布线过程与入口JSON | detached `fe326ad`；4个已跟踪文件修改，10,575个未跟踪路径；其中部分内容已有独立备份分支，不能简单说“全部没进Git” |
| `C:/Users/Sakuya/.codex/worktrees/66a4/FPGA-Music-project` | 已做过的产品版本归一、GUI/协议接合、源码身份和板验记录 | `codex/project-version-closure`=`614b2a7`；与main分叉；尚有691个未跟踪路径 |
| `C:/Users/Sakuya/.codex/worktrees/instrument-engine-safety/FPGA-Music-project` | 在上述已验候选上继续修复频率范围与重奏 | `codex/instrument-engine-safety`=`683db48`；有3个文档修改；该版入口注明未下载，不能继承旧板验为本版验收 |
| `C:/Users/Sakuya/.codex/worktrees/ca03/FPGA-Music-project` | GUI及包络重奏等工作 | detached `fe326ad`；10个修改、64个未跟踪路径，但当日备份分支保存了对应快照 |
| `D:/FPGA-Project/wb-worktree-20261019/FPGA-Music-project` | WorkBuddy技术文档与实验 | `codex/wb-20261019`=`b209df5`；266个未跟踪路径；87—89编号与4d37发生冲突 |
| `D:/FPGA-Project/codex-builds/fpga-m1-agent-work` | 后续M1源码、脚本、面积实验与构建证据 | 不是Git仓库，也不是已登记Git工作树；含正在变化的源码，不能按普通缓存清理 |
| `D:/FPGA-Project/codex-builds/fpga-m1-baseline-ref` | M1独立基线副本 | 不是Git仓库；有交接身份文件，不能与M1修改版混用 |
| `D:/FPGA-Project/codex-deliverables` | 硬件、可行性与Agent交接的交付副本 | 是交付存储，不等同Git分支或远程备份 |
| `C:/Users/Sakuya/Documents/LCEDA-Pro/projects` | 实际CAD原生项目 | 不在本次主仓库目录内；须由硬件入口指针、文件哈希与证据共同定位 |

共登记17个Git工作树，其中12个detached，13个存在修改或未跟踪路径。detached本身不代表代码消失；风险是新增成果没有命名分支与提交，正常克隆也不会带走。不能因为HEAD落后就删除工作树，也不能把“未跟踪”直接等同“无价值”。完整清单见[worktrees.csv](C:/Users/Sakuya/.codex/worktrees/4d37/FPGA-Music-project/notes/project-organization-audit-20261022/worktrees.csv)。

## 2. 主目录的体量与重复

以下为不递归跟随目录联接、排除共享`.git`后的文件字节总和；不是物理磁盘占用。主目录共16,770文件、约3.57 GB。

| 主目录部分 | 目录内常规文件 | 字节体量，十进制 | main提交树跟踪文件 |
|---|---:|---:|---:|
| experiments | 9,096 | 2.18 GB | 0 |
| notes | 1,208 | 523 MB | 2 |
| sim_build | 4,841 | 572 MB | 20 |
| src | 217 | 43.1 MB | 128 |
| tools | 393 | 92.9 MB | 137 |
| docs | 123 | 7.89 MB | 123 |

主目录21个实验目录混有完整源码副本、测试、综合/PnR输出、表数据和证据。按“experiments内src/rtl子目录，排除tb/reference/impl”的筛选口径，1,045个`.v/.sv/.vh`文件只有113种原始内容。例：`tdm_engine_rh.v`有12份、2种内容；`pitch_mod.v`有12份、3种内容；`mv_renderer.v`有17份、1种内容。这里不是1,045个独立设计模块，更不能把重复副本的行数相加当成产品规模。

同名副本也并非全等，不能批量去重覆盖。历史冻结实验应保留原身份；共用模块归一必须经过差异审查与行为回归。

主目录另有18个指向D盘构建/证据的目录联接，4d37有2个，06df有2个。本轮看到的目标均存在。`git status`可能展开联接目标，因此“未跟踪路径数”与上表常规文件数不相等。不能拿两种统计直接做减法，也不能据此算丢失率。

## 3. 版本控制的具体缺口

### P0：当前FPGA实现没有完整Git落点

main提交树没有experiments目录；38—86号文档虽然已经存档，但它们描述的实验源码不因此自动进入版本库。

4d37候选的85个RTL/头文件中，36个文件的内容可在本地命名引用的可达历史中找到，49个找不到；23个文件内容可在本地缓存的internal远程历史中找到。比对同时检查原始字节与CRLF转LF后的Git blob，避免Windows换行造成假差异。**这是文件内容存在性检查，不证明完整构建配置、静态表、约束和验证证据已被保护。** 本轮未穷举reflog、未命名悬空对象或其他云盘，所以也不把“未找到”写成“世界上只剩一份”。

本聊天此前新增的87—89号文档、候选与交接工具仍未提交，也属于缺口。独立交接ZIP保存了该版副本，但不能替代后续开发的Git提交。

[交接ZIP](D:/FPGA-Project/codex-deliverables/fpga-agent-handoff-20261022-v1.zip)的既有封存SHA256为`115f7d8f3789af99fed182ad331352e861c2795bba371567d9008df9d5458a78`。该身份来自此前交付，本轮未重新执行ZIP回归。

### P0：本地提交与远程备份脱节

本轮实际执行只读`ls-remote --heads`，没有fetch或更新远程跟踪引用。

| 引用/仓库 | 实际或缓存身份 | 与本地main的关系 |
|---|---|---|
| 本地main | `3824391` | 本地主线 |
| internal实际远程main | `90e891d` | 本地main领先62提交，远程无独有提交 |
| origin实际远程main | `12a4f07` | 双向分叉，本地独有127、远程独有2 |
| 本地缓存public/main | `2f2e454` | 过期缓存；public与origin实际指向同一URL |
| backup/hardware-20261022 | `80879c0` | 本地硬件快照分支，未合入main |
| backup/ca03-20261022 | `979c97d` | 本地GUI/RTL快照分支，未合入main |

internal远程当时只返回main分支，以上两个backup分支没有同名远程分支。不能把“本地backup分支”说成“已上传备份”。

origin和public都指向`https://github.com/sakuyaShining/FPGA-Music-project.git`；internal指向带`-internal`后缀仓库。本地协作板要求只推internal，并在推送前核实私有性。本轮只检查远程引用，没有查询仓库可见性、没有推送。main的上游已设为internal，但其他分支仍需明确推送目标。

### P1：备份快照与实时硬件入口继续漂移

硬件备份分支跟踪1,661个hardware文件。与06df比较，1,655个一致、5个不同、1个在实时目录缺失；这个结果只覆盖备份树已有路径，不证明后来新增文件均已备份。

备份入口记录04:22、PCB哈希`8b9b68a5…`、59个connection问题；盘点时实时入口记录14:47、PCB哈希`6509803e…`、57个connection问题。不能把旧快照与新入口混成一个版本，也不能仅凭入口JSON认定原生工程已通过新验收。本轮不做CAD复验。

ca03备份树的519个文件均与对应实时目录原始或LF归一内容相符。这说明这份快照有实际保护作用；不是证明整个项目已经归一，也不是验收其中的RTL行为变更。

### P1：D盘构建目录已混入开发源码

M1工作目录中含engine、rtl、tb和新增脚本，不能按“codex-builds都是可删除产物”处理。

17:55后补查时，M1相对4d37候选至少有3个RTL文件不同：`pitch_mod.v`、`tdm_engine_rh.v`、`sdram_stream_probe.v`。第三个文件当前临时摘除了可视化子树，代码注释明确为面积实验。README仍写“唯一增量是renderer”，M1改动记录开头写“只动2个文件”，说明当前工作文件、旧README与阶段说明并非同一身份。

这些目录仍在活跃修改。本报告不把临时面积实验当成功能削减决定，不恢复它，不签收其中的性能推断。后续必须分别给完整功能候选、基线和临时探针建立源清单，比较时绑定各自构建输入。4d37旧候选“路由完成但STA失败”不能自动签收M1，M1阶段记录的路由失败也不能覆盖旧候选的事实。

### P1：已有归一入口没有成为全项目共同入口

66a4已建立[project/CURRENT.md](C:/Users/Sakuya/.codex/worktrees/66a4/FPGA-Music-project/project/CURRENT.md)、catalog/state、源码清单、验证与板验记录。安全分支也有[更新入口](C:/Users/Sakuya/.codex/worktrees/instrument-engine-safety/FPGA-Music-project/project/CURRENT.md)。这项工作应保留并审查接续，不宜再创建一个互不承认的“唯一CURRENT”。

但main没有这些project目录；4d37另有实验级CURRENT；06df另有硬件JSON；各工作树README又有自己的“当前”。必须区分“全项目导航入口”和“某冻结版本的局部入口”。历史34/35号规格、PROJECT_MEMORY和旧资源数字应保留来源日期，不能继续与新状态并列作当前签收。

主目录README已经把旧13,690 Logic、+17.372 ns注明历史，不能误报为README完全没有警示；问题是它仍没有覆盖后续所有有效入口。

### P1：协作规则只覆盖了少数工作树

17个工作树中只有3个有本地AGENTS.md，只有main有当前协作板。旧工作树无法仅靠“先读本地AGENTS”发现新规则。协作板还列63个硬件未连通和旧原生工程路径，已落后于实际入口；D盘M1源码位置也未登记。

87—89号文档发生跨分支撞号。协作板已有新命名约定和旧编号待裁定事项，应执行并修正索引；本轮未擅自改名。对工作树的清理必须经过所有权与成果保全核对，不应按日期或detached状态筛选删除。

### P2：证据与输出的保留规则不一致

根.gitignore全局忽略`.log`、`.rpt.html`、`.timing_paths`等，候选还忽略evidence目录。因此普通git add不会自动保存这些关键验收材料。另一方面main已有20个sim_build文件，分支快照还带音频/字体等较大文件；“只放源码和证据”的原则尚未落实为可执行目录规则。

不建议反向放行所有构建输出。应把需要长期保留的小型验证摘要、命令、工具版本、退出码、源码和报告哈希放入明确受跟踪位置；大型波形/音频/报告归档到有校验的交付存储。综合所需`.hex`等静态表必须随源码跟踪，不能全局忽略。

原始实验脚本还含主目录、06df及D盘的绝对依赖。此前便携交接已做过适配，但原工程入口本身并未因此自动可移植。应分别登记工具安装路径、可配置输出根目录与不可缺失的工程输入，不能复制build.tcl后直接重跑旧路径。

## 4. Git本体检查

只读`git fsck --connectivity-only --no-reflogs`退出0，没有发现连接性错误。输出含438个dangling blob、158个dangling tree、22个dangling commit；因为显式不使用reflog，不能据此判断它们无用。

`count-objects`看到约10.71 MiB loose、120.26 MiB packs及约5.75 MiB临时残留。检查时仍有其他进程活动，残留数量也在变化。没有足够证据说Git仓库损坏；当前不应执行gc/prune或手删.git目录。这里的风险主要是工作流程与版本覆盖，清理几MB不能解决它。

## 5. 建议执行顺序与完成判据

| 顺序 | 动作 | 完成判据 |
|---|---|---|
| 1：保全 | 按所有者建立命名分支，精确提交当前有效源码、数据表、约束、入口、测试和源清单；对活跃M1与硬件先记录稳定检查点 | 能从明确提交或校验归档恢复；不靠未跟踪工作目录；不批量git add整个工程 |
| 2：登记 | 在现有归一入口基础上建立全项目导航，列主线、最近板验、开发候选、探针、硬件验证版/WIP、GUI分别对应的commit/源哈希与验证等级；同步协作板实际路径 | 新agent不搜索聊天也能确定该改哪份、不能用哪份签收 |
| 3：远程保护 | 审核待提交内容，核实internal私有性后显式推送需要保护的分支；main合并仍按现有规则由用户完成 | 远程实际引用与封存清单一致；public路径不承担内部开发备份 |
| 4：验证可恢复 | 从干净目录按锁定身份恢复，检查全部构建输入；运行对应行为回归，使用新的输出目录构建；目录迁移前后分别比较 | 不借用旧工作树未跟踪文件或旧impl；测试与构建结果绑定同一源身份 |
| 5：整理目录 | 先做只改路径和入口的独立变更，再处理重复模块与功能接合；每轮保留回归与回退点 | 组织调整不改变音乐行为、平台或PCB接口；已冻结证据仍能定位 |
| 6：归档清理 | 登记不活跃工作树与大型产物，核对快照及恢复能力后按所有者归档 | 无未保全源码、无仍被入口引用的证据；清理与功能改动分别审查 |

不要把79/81个未合主线提交、硬件大快照和GUI包络变更一次性全合入main。先按源清单、行为和协议差异评估，保留已验底座，逐项向前接合；也不要为了目录整齐直接退回旧main。

建议的目录职责如下，只是迁移目标，本轮未创建或搬迁这些目录；实际保留src还是改为fpga，应结合已有构建清单选迁移最小的方案。

```text
project/       全项目导航、候选登记、源码身份、验证状态（接续已有工作）
src/           受控共用实现；按core/control/io/display/storage等职责分层
boards/        Nano20K构建配置、约束、时钟和引脚契约
sim/           测试、模型、黄金数据与回归入口
tools/         构建/验证/主机工具；安装依赖与输出位置另行配置
hardware/      原生源与校验入口；verified和WIP身份明确区分
experiments/   有清单的独立研究；临时探针与产品候选明确标记
docs/          当前设计索引、决定记录、历史文档
```

大型构建结果留在D盘，工程中保留受跟踪索引与哈希。D盘包含源码的活跃工作区应迁入或注册为明确的开发分支工作区；迁移前保留其输入清单，不直接移动正在使用的目录。

## 6. 本轮证据与复核方式

- [完整盘点数据](C:/Users/Sakuya/.codex/worktrees/4d37/FPGA-Music-project/notes/project-organization-audit-20261022/inventory.json)：17工作树、分支树统计、存储联接、备份覆盖、远程实际分支与连接性检查。
- [源码身份清单](C:/Users/Sakuya/.codex/worktrees/4d37/FPGA-Music-project/notes/project-organization-audit-20261022/source-inventory.json)：所扫描5个位置的`.v/.sv/.vh`，含测试及生成副本；不可把总数当产品模块数。
- [重复内容清单](C:/Users/Sakuya/.codex/worktrees/4d37/FPGA-Music-project/notes/project-organization-audit-20261022/duplicate-verilog-content.json)：跨扫描位置的原始字节SHA256分组，包含正常工作树副本。
- [补充统计](C:/Users/Sakuya/.codex/worktrees/4d37/FPGA-Music-project/notes/project-organization-audit-20261022/supplement.json)：实验副本统计、分支分叉数量、M1相对候选的三处源差异哈希。
- [审计脚本](C:/Users/Sakuya/.codex/worktrees/4d37/FPGA-Music-project/tools/scripts/audit_project_organization_20261022.py)：可重新盘点，但会更新本审计目录中的JSON/CSV；需要保留此次快照时先另存。脚本内根路径属于本机调查范围配置。

调查覆盖所有已登记工作树的Git状态，深入扫描主目录、4d37、06df和两个M1目录；不是对所有磁盘、所有云端、CAD工程全内容或全部未命名Git对象的穷举审计。本轮没有重跑音乐回归或PnR，报告中的既有验证边界来自相应版本记录，组织调整后仍须按新身份验证。
