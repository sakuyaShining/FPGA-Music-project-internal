**采购执行只看[本次整机采购](hardware/sourcing-closure-20261030/BUYING.md)**。旧采购清单/统一包里的ORDER-STATUS仅作沿革，不再作为购物车输入；铜箔/铜胶带/样片电极、旧S1、额外DAC/J11/音箱退出本次采购。三类成品板均可送厂家审单报价，数据线型号明确；屏幕、内部线束、电源、预焊音频组件、外壳五项仍未交付为完整可付款订单，不能用候选或工程核验替代采购完成。

**2026-10-30 完整84路电极原生DRC与真实CAM核验已完成**：先读 [完整面板制造核验候选](hardware/electrode-fullpanel-cam-20261030/README.md)。在原工程保存关闭重开后DRC0，真实两层Gerber最小异网铜距0.255951mm>=0.25mm、90网连通，84电极阻焊覆盖/102过孔盖油/96排针开窗、198PTH+6NPTH逐孔、BOM/CPL/IPC96针检查和独立恢复复跑通过。源b7e9ecb1未变，旧WIP字节只读保留。现在是厂家审单报价候选；屏幕复位/实物尺寸、最终线束/覆膜/外壳及700元全报价仍未签收，不代表整机或付款制造放行。下方旧“EDA离线/未做原生DRC/CAM”的历史状态由本条更新。

**2026-10-30 C88电容料号提示已澄清**：见 [采购核查补充](hardware/sourcing-closure-20261030/README.md)。冻结R2原理图实例属性、PCB实际attrs与BOM的88项料号完全一致；13个电容均为C14663，C1591来自嵌入库默认值及残留数据表链接，不能覆盖实例属性。未换料、未改冻结源；C14663的真实工厂备料/报价仍需确认，国际目录库存快照不能代替国内SMT库存。

**2026-10-30 完整84路电极已完成布线源备份，制造核验待接续**：先读 [完整面板接续](hardware/electrode-fullpanel-450-20261030/README.md)。236×156mm整块面板含25音位×3+5八度+4备用，六背面排针和全部84映射不变；90网源连通、最小异网源铜距0.255949mm、96针线束合同及独立恢复复跑通过。原生客户端退出后尚未完成保存重开DRC及真实Gerber/阻焊/钻孔核验，本面板不能下单；屏幕/插头净空、覆盖材料和采购报价仍待确认。S2审单成果不受影响。

**2026-10-30 S2修正版已完成工程核验**：先读 [Sensor14Bank S2](hardware/sensor14-s2-20261030/README.md)。已解决原22处严格铜距，实际最小0.23254mm，保存重开DRC0、四层实际异网铜距/连通、83孔、28件BOM/CPL及阻焊板框核验通过。六块传感板请改用S2文件审单；旧S1保持停用。厂家DFM/报价与付款、实物性能仍未签收；完整电极面板仍未完成。

**2026-10-30 采购与Agent最新统一交接**：先读 [今日完整交接](hardware/team-handoff-20261030/README.md)。450×190×60mm及18mm音位间距已获用户确认；C88可独立送审，S1严格铜距HOLD、完整电极未完成、屏幕完整配置报价与电源精确商品仍待闭合。音箱借用；音频面板座C381127，预焊线束待报价。本次成果在PR #9任务分支，未宣称合入main。

**2026-10-29 基线复核更正：传感板暂停投产。** 实际S1 Gerber底层地铜到22个非地排针焊盘最小间距约0.162858mm，低于保留门限0.1651mm；此前原生DRC0、5μm图形比对与较低通用门限未覆盖该严格条件。可继续询价，先不按本版传感板付款生产。旧冻结包字节保留用于追溯，不能据其中的PASS或READY文字忽略本更正。详见基线`evidence/retained-clearance-gate-audit.json`。

**2026-10-29 硬件交付接续**：先读[当前交付基线](project/DELIVERY-BASELINE-20261029.md)。冻结Control88 R2×1与Sensor14Bank S1×6及送厂资料；采购报价、固件与整机验收仍未完成。任务分支候选不自动成为main。

# 项目工作入口

**2026-10-27 当前入口**：先读`project/CONSOLIDATION-20261027.md`。本次用户已直接授权整合并合入main；不扩展为其他未来PR的自动合并授权。模块方案／951载板／14路小板和恢复检查点分别判断，35段限定口径批准不等于制造放行。

**当前协作工程：先读`project/ENGINEERING.md`及`project/COLLABORATION-CHECKPOINT-20261024.md`，执行`python tools/scripts/engineering.py check`。最新开发候选位于`fpga/current/`、`hardware/current/`、`host/current/`；根目录旧源码及v1/v2恢复只作历史。音乐黄金差异、硬件未连通和实体兼容缺口必须随任务交接。**

**main长期入口：先fetch核实目标仓库实际main，再读`project/DESIGN-CURRENT.md`、`project/PRODUCT-SPEC.md`、`project/governance.json`、`project/decisions.json`及`project/producers.json`。仓库已由用户公开，名称internal不表示私有。用户已取消J11实体音乐可视化屏、保留J10；此项覆盖旧双屏红线。固定源码归档、活跃未发布源和已验证源必须分开，旧PASS不继承。快速获取见`project/QUICKSTART.md`。**

新Agent读`project/AGENT-START.md`与`project/handoff.json`，执行`python tools/scripts/project_control.py check --remote --fresh-entry`及`python tools/scripts/design_governance.py status --remote`。在本机继续功能工作前加`--live`核对声明的活跃源；源不可访问/变化/审阅过期必须明示并处理，不视为通过。日期分支仅兼容，v1/v2标签仅复现；实际main唯一权威。不能只看旧README、目录时间戳或继承的source-identity就实施。

先读 `project/CURRENT.md` 和 `project/state.json`，再读协作板。入口身份检查：`python tools/scripts/project_control.py check`；完整保全内容核验加 `--full`。源码捕获不等于产品验收。

命名分支与远程提交是交接必填项。共享开发核实internal的实际URL与仓库身份后推送；旧origin/public指向另一个仓库，不能按remote名称混用。公开仓库不得提交令牌、完整私聊或账号配置。

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
