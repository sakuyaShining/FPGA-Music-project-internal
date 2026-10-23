# 当前设计与实现入口 · 2026-10-23 v2

设计版本：`design-20261023-v2`。机器登记见[design-state.json](design-state.json)，归档输入及逐文件哈希见[latest-design-inputs-20261023.json](versions/latest-design-inputs-20261023.json)。本页汇合本会话、硬件会话与D盘FPGA工作区；不以会话记忆、目录时间或旧README定义最新版本。

## 1. 已核对的最新产品范围

| 项目 | 当前决定与边界 |
|---|---|
| 平台与合成 | Tang Nano20K；32组×16分量，各乐器层共享32组；保留四槽分层目标，不变成每层32组 |
| 左手 | 两排逐音滑条＋独立八度档条；逐指音高表达。硬件保持84电极能力；25/26音位及端点映射须按已登记接口核对，不凭84反推最终音符规则 |
| 右手 | 保留J10泛音构造触控显示链；7英寸候选、分区竖直推子、全和弦连续修饰、松手保持、RESET平滑恢复。具体模组SKU/CTP/电气/线束和机械尚未全部签收 |
| 实体音乐可视化屏 | **用户已取消。J11/MSP2401及视觉专用支路不再属于当前实体范围。**旧双屏预算、双屏红线与不许取消小屏的旧文字在这一项被覆盖；不是把两屏合并，也不取消J10 |
| 编辑与保存 | 自定义乐器、实体编辑、断电保留目标继续；编辑草稿、保存定义、运行修饰、在响实例分离 |
| 录放 | 演奏实际声音录制/播放、播放期间现场演奏目标继续；SDRAM仅缓冲，TF文件和事件配对仍有缺口 |
| 接口与权限 | 按最新已授权硬件接口继续，不能把旧J11接口重新接回；本轮管理整理不再改电路或产品RTL，不下载、不制造放行 |

取消小屏的直接人类原话、会话与turn ID已保存在[决定出处](versions/design-decision-20261023.json)。该决定比38/39/49/87号及旧协作板的双屏要求更新；其他功能不由本次整理裁减。PC辅助可视化也不能据此自动删去。

## 2. 实现版本必须分开读取

| 来源 | 当前事实 | 不得推导的结论 |
|---|---|---|
| 66a4 / 07及安全修复候选 | 已有音乐/主机基线与各自专项验证记录 | 不代表当前实体功能完整，也不继承到新源 |
| 4d37原87号结构探针 | 路由完成、setup −6.397ns / hold −0.048ns；历史双屏输入 | 不作为当前产品预算或合格码流 |
| 10月22日M1登记源 | 原100项输入，engine/pitch专项曾通过；仍可按v1恢复 | 不叫今天实时最新，不签收后续新增代码 |
| **本次观察到的D盘FPGA候选** | 复位/POR、逐通道力度、启动默认值、strike/hybrid寄存器及测试；新增`tdm_ship_owned`包装。归档时105项构建输入，相对原登记8项修改、1项删除、6项新增 | 未合并；源作者报告的仿真/PnR/板测须按对应run/source复核，本次未重跑，不继承旧PASS |
| 硬件保留检查点 | `aaa62f2…`，记录为37项未连通/6网，已有原生恢复ZIP | 仍未放行，不是可制造整板 |
| 硬件活跃施工副本 | `FPGA-Music-U9ControlWork-20261023`，继续由硬件会话推进；来源记录之间存在更新先后差异 | 施工DRC数字不能与37版混用或当作质量晋升，禁止重放历史事务 |

**`tdm_ship_owned`这个名字不证明完整产品顶层已完成。**源码默认`FINGER_EXPR=0`、`RIGHT_TIMBRE=0`、`LEGACY_PAD=1`，暴露16路直连pad并把外部控制接口接常量；尚未接成84节点MUX、J10、EEPROM/TF和全部实体交互的完整载板顶层。原探针仍含`music_visualizer`；取消实体屏尚未在全部RTL/profile中落地。不能直接删除子树后沿用原音乐、布线或板测结论。

## 3. 最近会话新增的设计信息

本次归档含`ARTICULATION-AS-NOTE-PROPERTY`、`ARTICULATION-RUNTIME-SPEC`、`RUNTIME-EDIT-AND-ARTICULATION`、`GENERAL-INSTRUMENT-GAPS`、`NIGHT-20261023-VELOCITY`和`STRIKE-MODE-20261023`等原文。

- 激发模式文档记载sustain/strike/hybrid作为演奏态音符属性、与音色频谱区分，strike按分量序号生成衰减梯度；候选RTL使用0x38–0x3F，默认关闭，新音装载/显式刷新行为另列。这里保存原作者方案和实现，不替用户冻结全部参数与音乐语义。
- 新候选有复位生成、逐通道力度和寄存器启动修复。电容测量值不等于已验证的物理压力；16路直连测试不签收84节点MUX载板。
- A6短命令、编译器至主机设备通路、双段衰减、EEPROM等仍有待实现项；具体按新源及相应报告核对。
- 编辑是否可依赖电脑、尾音/抢占、激发默认值、现场/回放修饰对象等仍需原始用户决定或验收。文档中的“做不出来”“唯一可行形态”和优先级建议不自动成为用户批准的功能降级。
- `INFO-BASELINE-20261023.md`仍写双屏、旧GPIO零余量和旧Git状态；它是被保留的历史说明，**不能因标题日期较新就凌驾本入口**。新顶层CST的reset/LED/pad与载板接口也不能直接混用。

## 4. 快速取得已发布设计及源码

首次克隆，目标目录必须不存在：

```powershell
git clone --origin internal --branch codex/project-management-20261022 --no-single-branch https://github.com/sakuyaShining/FPGA-Music-project-internal.git D:/FPGA-Project/review/current-design
```

已有当前入口工具时，可一步克隆并完整核验到新目录：

```powershell
python tools/scripts/project_control.py get-latest --output D:/FPGA-Project/review/current-design-verified
```

在取得的目录执行`python tools/scripts/project_control.py check --full --remote --fresh-entry`。需要本批新观察源时：

```powershell
python tools/scripts/project_control.py restore-design --area fpga --output D:/FPGA-Project/review/fpga-observed-20261023
python tools/scripts/project_control.py restore-design --area hardware-context --output D:/FPGA-Project/review/hardware-context-20261023
```

恢复目录先读新生成的`AGENTS.md`与`PRESERVATION-ORIGIN.json`。硬件输出只含所列上下文和既有原生恢复ZIP，不是完整活跃硬件目录，也不会导入CAD。FPGA原始构建脚本含绝对路径；先在自己的命名分支适配新输出目录，再实施或验证。回归黄金数据仍从v1包恢复，不用新候选测试覆盖旧黄金。

**“最新”指该分支已经发布并登记的设计，不包括其他会话尚未登记的未来修改。**本批归档逐文件重读核验，不声称跨文件/原生事务原子快照。活跃硬件与FPGA后续变化需owner继续登记。main在PR #1合入前仍为旧入口；v1标签固定旧检查点，v2标签固定本批，实时接手始终取发布分支。
