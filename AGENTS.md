# 项目工作入口

**main长期入口：先fetch核实private的内部仓库实际main，再读`project/DESIGN-CURRENT.md`、`project/governance.json`、`project/decisions.json`及`project/producers.json`。用户已取消J11实体音乐可视化屏、保留J10；此项覆盖旧双屏红线。固定源码归档、活跃未发布源和已验证源必须分开，旧PASS不继承。快速获取见`project/QUICKSTART.md`。**

新Agent读`project/AGENT-START.md`与`project/handoff.json`，执行`python tools/scripts/project_control.py check --remote --fresh-entry`及`python tools/scripts/design_governance.py status --remote`。在本机继续功能工作前加`--live`核对声明的活跃源；源不可访问/变化/审阅过期必须明示并处理，不视为通过。日期分支仅兼容，v1/v2标签仅复现；实际main唯一权威。不能只看旧README、目录时间戳或继承的source-identity就实施。

先读 `project/CURRENT.md` 和 `project/state.json`，再读协作板。入口身份检查：`python tools/scripts/project_control.py check`；完整保全内容核验加 `--full`。源码捕获不等于产品验收。

命名分支与远程提交是交接必填项。共享开发只推已核实为private的internal；origin/public用于独立对外发布。

**本项目由多个 agent 并行推进。开工前必须先读 `docs/00-协作/AGENT-BOARD.md`**，确认：
你被分配到哪条轴、哪些路径只有你能写、哪些决定不可回退、上一个 agent 在飞什么。
一个 agent 同一时间只认领一条轴。`notes/agent-collaboration-log.md` 是给评委看的人机协作
评分素材，不是 agent 之间的调度板，不要往里写调度信息。

开始设计讨论或实现前，先读：

- `docs/02-技术方案/38-代码盘点与实现基线-2026-10-09.md`：当前源码事实与验证边界。
- `docs/02-技术方案/39-最新设计构想与落地差距-2026-10-09.md`：目标、状态与未决项。

运行 `git status --short` 和上面的project_control检查，先识别版本归属与恢复输入。旧版本的project_baseline.py仅按对应冻结入口使用，不用旧范围签收新实验。
同时查看38号 §0 的工作树分布：main不是项目所有最新成果；a61b有事件修复/逐指接口，6e70有未接合GUI/协议及未提交成果。
39号 §0 为较新设计，后面旧方案用于历史对照。不得把右手回中、只修饰单音等旧提案覆盖后续松手保持、全和弦修饰选择。
旧的 PROJECT_MEMORY、34/35 号文档和架构图保留历史；有冲突时核对实际源码及相应版本证据。

讨论收尾更新对应设计项的决定、差距与下一步；实现收尾注明源码版本、实际验证和未验证项。
分别使用“讨论中、待实现、部分实现、已实现待验证、已验证、已回滚”，不把方案或现状刻画测试的 PASS 当成目标完成。
代码、数据表、约束、构建入口、主机协议与验证脚本都属于需追踪的实现。
新快照仅在改动经过评估与适当验证后写入；不要为了消除漂移提示直接覆盖旧快照。
用户决定优先；盘点和文档整理不授权替用户裁定新的音乐交互语义。

跨会话收工还须遵守`project/MAINTAINING-MAIN.md`：新决定登记证据及supersedes，新owner/源登记producer和实际远程提交；新观察不自动续期，严禁仅改审阅日期、隐藏活跃源或复制旧PASS以消除告警。main已登记的信息才可对其他Agent宣称已发布；未知会话不假定已同步。
