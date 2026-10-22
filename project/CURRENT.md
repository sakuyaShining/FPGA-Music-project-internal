# 全项目当前入口

本入口管理全项目的版本和工作起点。**当前没有已经实现并通过验收的完整功能产品顶层。** 保存了源码、通过音乐回归、完成结构探针路由、通过STA、完成板验，是不同层级的事实。

新Agent先读`project/AGENT-START.md`和`project/handoff.json`。可直接转交的启动指令在`project/NEXT-AGENT-PROMPT.md`。本批交接分支为`codex/project-management-20261022`，标签为`handoff/20261022-management-v1`；入口检查加`--fresh-entry`会拒绝未包含当前已发布管理入口的旧工作区。

## 从哪里开始

1. 阅读本页和根目录AGENTS.md，再读协作板，确认负责人及路径边界。
2. 运行`python tools/scripts/project_control.py check`。需要核验全部保全内容时加`--full`。
3. 根据下表选择版本，按`project/versions/workspace-preservation-20261022.json`中的commit和manifest取回。**不要按文件修改时间选择“最新版”。**
4. 具体功能目标见38、39、49号文档及其后续已确定决定；Nano20K预算与完整功能缺口见4d37快照的87、88号文档。编号撞号时必须同时标注来源分支和完整文件名。

## 目标与约束

保持Tang Nano20K、32组×16分量、四层目标、左手两排逐音滑条与独立八度条、右手全局控制/保持/复位、双独立显示、音色非易失存储、录制/播放与现场演奏。组织整理不授权削减功能、换平台或改变PCB接口；禁止把临时移除子树的面积实验升级为产品方案。

## 有效版本的分工

完整机器清单见state.json；下表中的验证事实来自既有记录，本次管理整理没有重跑功能回归或PnR。

| 角色 | 版本入口 | 实际边界 |
|---|---|---|
| 已接合音乐/主机基线 | `codex/project-version-closure`，66a4快照 | 原有project/CURRENT.md及07源清单记录了回归、PnR和板验；实体全功能仍有缺口 |
| 频率/重奏修复候选 | `codex/instrument-engine-safety`及其快照 | 既有记录：专项覆盖与新PnR通过，未下载；不继承07板验为本版板验 |
| Nano20K结构探针 | 4d37快照，`experiments/nano20k_feasibility_20261021/project/CURRENT.md` | 原音乐逐拍等价、renderer穷举、完整路由/码流完成；setup−6.397ns、hold−0.048ns，STA失败；不是可下载产品 |
| M1历史检查点与面积实验 | m1-work、m1-reference快照 | 当时可能含关闭视觉化等临时配置，只是固定检查点；不作为本次最新源码入口 |
| 本次最新登记M1候选 | handoff.json的fpga_handoff：m1-work + 登记增量 | 按100个有效构建输入哈希确定身份；专项结果单独记录，新完整路由/STA未签收。负责人身份仍需登记 |
| GUI/协议来源 | 6e70、ca03快照及backup/ca03分支 | 存在多个来源，不视为已经与最新FPGA探针接合 |
| 硬件推进 | 06df快照中的`hardware/review-manufacturing-20261019/REGIONAL-WORK-IN-PROGRESS.json` | verified来源、pending_trial、ACTIVE-ROUTING候选分别保留；快照不是制造放行 |
| CAD原生输入 | native-source57、native-trial50、native-r15快照 | 分别保存当前来源、待验试作和旧稳定候选。ID中的数字是历史标签，真实状态由原始哈希/记录解释 |
| main | 根目录已提交历史 | 导航和集成主线；不等同所有工作树最新成果，也不代表完整产品已验收 |

## 取回与恢复

所有保全分支都是`codex/preserve-…-20261022`。正常clone internal会获取这些分支的对象；浅克隆或只取单分支时，需要先取回清单列出的分支。工作区的绝对路径只是捕获来源，不是恢复依赖。

```powershell
python tools/scripts/project_control.py check --full
python tools/scripts/project_control.py restore --snapshot 4d37 --output D:/FPGA-Project/restored/fpga-4d37
```

恢复命令拒绝覆盖已有目录，并恢复压缩轨迹到原相对路径。它只恢复清单中实际捕获的输入；工具安装、被排除的生成产物、第三方依赖、未保存的CAD会话状态不在其中。原生会话ID用于历史追溯，不得直接重用或重放事务。

便携FPGA交接包保存在`project/archives/`，含冻结输入、黄金数据、适配入口和校验清单。具体流程读包内START-HERE.md与WORKFLOW.md；不执行下载/Flash/制造。

原快照可能保留指向旧工作区的绝对路径。不要直接运行其中的prepare/build脚本；先使用便携包入口，或审查并适配到新的独立输出目录，避免覆盖历史构建。

检查点之后观察到的硬件/M1源变化另存于`project/archives/post-capture-wip-20261022.zip`，来源和哈希见`project/versions/post-capture-source-drift-20261022.json`。这是未验证增量，不是一份完整产品或原生事务快照；不继承旧测试、DRC或路由结论。未来变化仍由原owner继续提交。

## GitHub与协作

- 共享内部远程：`internal`。本次已通过GitHub API核实仓库为private。
- origin/public指向对外发布地址；对外发布另走审查导出流程。
- main按既有约定由用户合并。保存分支不等于合入main，源码捕获不等于功能验收。
- 每个任务使用命名分支，记录owner、源清单、验证边界、远程实际提交和下一步。
- 每个owner同时只推进一个任务。新增工作先登记负责人、源版本、范围和完成条件；未登记的新目录不算已接管的正式开发入口。
- `preserve-*`是一次性恢复档案，不是新增的活跃开发任务；后续从选定快照建立开发分支，不改写归档分支。
- 新检查点使用新ID；禁止覆盖封存分支、复用旧构建目录、强推共享历史。

## 仍需推进

1. 将后续改动持续提交到对应开发分支，减少在未登记目录继续累积源码。
2. 登记M1会话owner，明确保留功能候选与面积探针各自profile；本次不改它们。
3. 审查音乐安全修复、GUI/协议与当前探针的差异，按行为回归逐项接合；不批量合并全部历史提交。
4. 向真实产品顶层与完整资源/时序预算推进，独立验证双屏、录放、非易失及完整控制链。
5. 后续再整理目录和清理工作树。此次1—3步没有移动活跃工程或清理构建产物。
