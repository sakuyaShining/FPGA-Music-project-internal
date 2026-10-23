# 当前设计与实现入口

**唯一发布入口：私有仓库的实际远程main。**设计登记见[design-state.json](design-state.json)，已确认决定与沿革见[decisions.json](decisions.json)，实时性与审阅期限见[governance.json](governance.json)。跨会话维护流程见[MAINTAINING-MAIN.md](MAINTAINING-MAIN.md)。日期分支与冻结标签用于兼容/追溯，不定义最新。

当前审阅记录以`governance.json`指向的观察时间为准；13:07初审、显示路线澄清及晚间协作接手审阅分别保留。先运行`python tools/scripts/design_governance.py status --remote`；本机能访问活跃源时加`--live`，否则不能声称实时源已同步。新变化或到期会要求重新审阅。源码可恢复归档仍是12:23的v2，不把新观察自动写成新代码验收。多人协作与离线任务见[COLLABORATING.md](COLLABORATING.md)。

**本会话最新直接确认**：“取消独立可视化小屏，保留 J10 触控屏及现有显示控制器路线”。[原话记录](reviews/20261023-display-clarification/evidence/current-user-confirmation.json)覆盖另一会话`DECISIONS-20261023.md`中“RA8875已放弃”的解释。RA8875继续作为现有J10路线候选，具体SKU/CTP、电气/机械仍待签收；不据该外部记录重排PCB接口或取消右手图形交互。

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
| v2可恢复FPGA候选 | 复位/POR、逐通道力度、启动默认值、strike/hybrid和`tdm_ship_owned`包装；12:23归档105项构建输入 | 固定恢复检查点，不叫当前活跃源；不继承旧100输入PASS |
| **D盘活跃FPGA源，截止当前review时间** | v2之后新增双段衰减、逐槽力度表及生成器、UART试听工具和设计/采购提案；完整观察与差异见当前review | 尚未发布为新的完整源码归档/产品顶层；本轮只读审阅，未重跑作者仿真/PnR/板测 |
| 硬件保留检查点 | `aaa62f2…`，记录为37项未连通/6网，已有原生恢复ZIP | 仍未放行，不是可制造整板 |
| 硬件活跃施工副本 | 晚间review观察：`FPGA-Music-U9ControlWork-20261023`、`e098c5db…`、47项未连通/13网、227件616孔；作者记录BUS_MOSI闭合，仍有9个控制网待恢复，3件Bottom SMT | 该数量有截止时间；不与37版混用或晋升，不表示制造放行/实物验证；旧单面装配输出已过时，禁止重放历史事务 |

**`tdm_ship_owned`这个名字不证明完整产品顶层已完成。**源码默认`FINGER_EXPR=0`、`RIGHT_TIMBRE=0`、`LEGACY_PAD=1`，暴露16路直连pad并把外部控制接口接常量；尚未接成84节点MUX、J10、EEPROM/TF和全部实体交互的完整载板顶层。原探针仍含`music_visualizer`；取消实体屏尚未在全部RTL/profile中落地。不能直接删除子树后沿用原音乐、布线或板测结论。

## 3. 最近会话新增的设计信息

本次归档含`ARTICULATION-AS-NOTE-PROPERTY`、`ARTICULATION-RUNTIME-SPEC`、`RUNTIME-EDIT-AND-ARTICULATION`、`GENERAL-INSTRUMENT-GAPS`、`NIGHT-20261023-VELOCITY`和`STRIKE-MODE-20261023`等原文。

- 激发模式文档记载sustain/strike/hybrid作为演奏态音符属性、与音色频谱区分，strike按分量序号生成衰减梯度；候选RTL使用0x38–0x3F，默认关闭，新音装载/显式刷新行为另列。这里保存原作者方案和实现，不替用户冻结全部参数与音乐语义。
- 新候选有复位生成、逐通道力度和寄存器启动修复。电容测量值不等于已验证的物理压力；16路直连测试不签收84节点MUX载板。
- **双段衰减状态已更新**：新源增加`d2_lvl/d2_k`及0x5D–0x5F全局参数、默认关闭，作者报告7/7仿真及反例。原文保存在[DECAY2记录](reviews/20261023-main-authority/evidence/fpga/DECAY2-20261023.md)。本轮未复验；全局第二段及参数值是该候选的实现选择，不替用户批准音乐语义或裁减逐分量能力。状态为“已实现待验证”。
- A6短命令、编译器至主机设备通路、EEPROM等缺口继续跟踪，不能用新包络功能代表实体编辑/录放完成。
- 编辑是否可依赖电脑、尾音/抢占、激发默认值、现场/回放修饰对象等仍需原始用户决定或验收。文档中的“做不出来”“唯一可行形态”和优先级建议不自动成为用户批准的功能降级。
- `INFO-BASELINE-20261023.md`仍写双屏、旧GPIO零余量和旧Git状态；它是被保留的历史说明，**不能因标题日期较新就凌驾本入口**。新顶层CST的reset/LED/pad与载板接口也不能直接混用。
- 晚间新增的`AUX-SCREEN-PRODUCT-BOM-20261023.md`用旧四滑条小样推断“PCB为空”，与当前载板施工不符；其GPIO重排、缩减sense通道、按键扩展和AUX单路建议不构成已批准接口。采购价格/SKU和元件配置也未经本轮验证，不据此下单或修改PCB。
- `ACCEPTANCE-CRITERIA`及`DERISK-PLAN`中的Q1–Q6选择、阶段裁剪和降险建议尚缺本入口可追溯的直接人类确认；保持提案身份。`LAYER4-RULES-DRAFT`对双bank的解释还与`EDIT-MODE-DESIGN`冲突，实施前核对RTL。逐槽力度表作者报告的PnR数字仅属于受限包装，不签收完整产品，也未由本轮复验。
- 接手依赖缺口：新`gen_vel_wtab.py`读取`engine/src/vel_wtab.hex.bak-20261023`保留slot0；该后缀未包含在当前producer观察白名单及旧v2归档中。需要owner交回此确切基线及哈希，不能让协作者用新表代替旧表重新生成。观察清单是声明范围，不能声称全部依赖已齐备。新`POST-PCB-BOM`关于电源/接口的缺失断言亦须与当前原生工程核对，不自动加入或重做现有电路。

## 4. 快速取得已发布设计及源码

首次克隆，目标目录必须不存在：

```powershell
git clone --origin internal --branch main --no-single-branch https://github.com/sakuyaShining/FPGA-Music-project-internal.git D:/FPGA-Project/review/current-design
```

已有当前入口工具时，可一步克隆并完整核验到新目录：

```powershell
python tools/scripts/project_control.py get-latest --output D:/FPGA-Project/review/current-design-verified
```

在取得的目录执行`python tools/scripts/project_control.py check --full --remote --fresh-entry`。需要恢复**12:23的v2固定源**时：

```powershell
python tools/scripts/project_control.py restore-design --area fpga --output D:/FPGA-Project/review/fpga-observed-20261023
python tools/scripts/project_control.py restore-design --area hardware-context --output D:/FPGA-Project/review/hardware-context-20261023
```

恢复目录先读新生成的`AGENTS.md`与`PRESERVATION-ORIGIN.json`。硬件输出只含所列上下文和既有原生恢复ZIP，不是完整活跃硬件目录，也不会导入CAD。FPGA原始构建脚本含绝对路径；先在自己的命名分支适配新输出目录，再实施或验证。回归黄金数据仍从v1包恢复，不用新候选测试覆盖旧黄金。

**“最新”指实际main已经登记且仍在审阅有效期内的设计信息，不包括未登记会话或未来修改。**检查输出分别报告发布身份、审阅到期、活跃源可见性及未发布WIP。活跃源变化需owner交回后审阅，不能只改日期或覆盖快照消除漂移。v1/v2标签保持固定；旧管理分支由兼容job只快进同步main，新工具直接核对main。
