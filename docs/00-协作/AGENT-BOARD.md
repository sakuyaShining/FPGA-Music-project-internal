# Agent 协作板

## 2026-10-27 实体交付接续认领

- 用户在会话`01a17cd7-710c-7be3-be62-6537a4a702b6`要求接续硬件聊天，今晚推进全部可完成工作，并明确由本会话获取屏幕资料和完成选型。
- 独立分支`codex/hardware-delivery-20261027`，基点main`0f2ff18f`；只写本工作树的`hardware/current/module-plan/manufacturing/`、选型/接线交付及相应入口/审阅。原owner活跃CAD目录、06df、D盘FPGA生产源只读；不重放终态CAD作业，不修改GPIO或产品音乐规则。
- 桥接49620在线但没有连接窗口；旧客户端快捷方式目标不存在，等待用户打开可用客户端。已有源617f550e离线核验；原生制造导出、物理层叠及最终CPL仍须验证。
- 订单、付款、供应商外发消息、烧录与制造放行无新增授权。

**2026-10-27 本次整合**：会话`01a17cd7-710c-7be3-be62-6537a4a702b6`仅在独立整合分支处理入口／治理／硬件发布副本，用户直接授权main合并。原A/B/C owner、活跃RTL和CAD写入权不变。详见`project/CONSOLIDATION-20261027.md`。

## 2026-10-24 Immutable-frame接合限定增量

- 4d37继续同一已认领input副本/工具/入口范围：帧冻结、seen/blocked、坏帧/标定/序号/看门狗与全token接触命令端点接合；默认26联系人和四层小接口、背压与未完成起音期间松手取消均有独立语义对照。
- 源基点82d37271751aac797c371ec5b46c8b245fd59ea9，仍使用原任务分支/PR4；新版本及证据入口project/versions/note-frame-source-20261024.json。原current、D盘owner/06df/硬件handoff只读。
- 仍是捕获接口格式的帧刺激和分配回包替身，不是实体扫描/完整finger消费者/曲谱或真实音频顶层。新全约束单元PnR同样route80%工具0xC0000005，无STA；保留失败，不重跑旧17组。
- 下一手必须将完整层anchor/确认映射接到实际finger消费端和真实分配/renderer，再接曲谱背压/自动OFF及全顶层时序。D-019不重问；P-020与其余未冻结产品规则不默认采纳。main仍由用户合并。

## 2026-10-24 Contact RTL命令端点限定增量

- 4d37继续原A轴已认领副本：新增input/rtl/note_contact_adapter.v、周期对照/定向故障及独立PnR脚本；没有改三个current、D盘原FPGA或06df。
- 源基点ad57967a95f9391b74fe3e5a89ffd1b144a2bbfc，仍使用codex/current-engineering-sources-20261023/PR4；最终源提交以实际PR head解析，精确清单见project/versions/note-contact-transport-20261024.json。
- 已实现命令级全局token、全层运动/退场、按住不重触发、取消与回包/复用竞态；三个独立RTL/oracle场景和5项指定字段反例通过。不是实际扫描器/曲谱/音频整机接合。新单元全约束PnR在route80%进程0xC0000005、无STA，失败必须交接。
- 新硬件owner交回文档报告951ce88a/42项12网/227件649孔，但其完整审阅因ADDR2/Inner16闭集铜集合差异失败；旧entry的运行标志与终态失败不一致，不继承原a3a258检查点或签收制造。本会话只保全/登记证据，不运行CAD或复开几何作业。
- 下一手：实际immutable-frame源和完整层finger消费端、曲谱背压/自动OFF、完整顶层与时序/实体验收。D-019不重问；P-020仍未批准。main合并仍只由用户操作。

> **这是什么**：多个 agent 同时推进本项目时的唯一协调入口。
> **不是什么**：`notes/agent-collaboration-log.md` 是给评委看的人机协作评分素材（AMD 2026「大模型协作与技能包 15 分」），记录的是"用户采纳/否决了什么"，**不要**往里写 agent 之间的调度信息。
>
> 本文件必须**提交在 `main`**。新工作树先fetch核对目标仓库实际main；用户已公开该仓库，名称internal不表示私有。日期分支仅兼容，候选管理PR须明确尚未发布。禁止从旧提交（如`2770e63`）推断当前设计。

管理覆盖更新：2026-10-23（见§11）。接手先查main、governance及producer登记；旧交接的施工数字与日期分支不是实时状态。

最初建立：2026-10-22 00:55（WorkBuddy）

---

## 1. 轴与所有权

项目当前有三条可并行的轴。**一个 agent 在同一时间只认领一条轴**，跨轴必须先改本表。

| 轴 | 内容 | 当前所有者 | 独占路径（只有所有者可写） |
|---|---|---|---|
| **A · 原生产逻辑时序与资源** | 音乐、M1、复位/力度/激发候选与完整载板顶层 | 独立FPGA会话，准确ID未登记；D盘源见producers.json | 未明确owner前不接管D盘原源；4d37对已捕获候选的限定副本范围另列，不覆盖原生产目录 |
| **A · 已捕获候选的验证与资源合同** | T02显式profile、独立幅度参考、NR01–NR07及后续隔离资源管理候选 | 本4d37会话，用户授权继续长任务 | `tools/scripts/music_profiles.py`、`tools/tests/test_music_profiles.py`、后续`experiments/note_resource_20261024/`；D盘原源只读，未授权覆盖其他owner。当前未修改三个current目录 |
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

### 2026-10-24 · Codex · Contact合同/反例与新v1资料隔离审阅
- 做了什么：从642b2df9干净候选安全pull main；用实际contact13位身份/完整组映射形成事务oracle，11项场景与共享资源模型交叉验证，256代次后旧OFF/移动、抢占后按住不重触发、全四层表达、取消与回绕均覆盖；三个故障版本在指定断言检出，不用导入失败或超时冒充。
- 在飞什么：这只是CONTACT-ADAPTER-CONTRACT与Python参考，不是RTL adapter、物理扫描/PCM或新PnR签收。首轮校验器把Windows CRLF的OK误拒，原FAIL/旧工具保留，修复换行判据并完整新目录重跑。
- 卡在哪：上游新增五份建议文档和单独91规格入档源；目录名authoritative及其分支不替代main。另登记只读fpga-v1-intake producer、未知owner明确保留；v1缺84/J10/逐指/EEPROM/TF，文件SHA匹配不构成下载授权。引脚审计后文已撤回前文测量/LED结论，不能只照前段改PCB或发出错误阻塞判断。
- 需要对方什么：不执行上游删除/改remote/删preserve分支/授权下载或忽略verify建议；不接管D盘/06df。原生a3a258/49项13网仍未制造/实物UNMEASURED。新源审阅与功能验收分开；完整hold修复异常未解决，P-020及其他未决音乐行为不自裁。
- 下一手从哪读：project/reviews/20261024-contact-contract-intake/ASSESSMENT.md、input/CONTACT-ADAPTER-CONTRACT.md及verify_contact_contract.py；源基线642b2df9，精确发布commit取PR4实际head。下步按oracle实现真正ready/valid/contact全层绑定并逐项回归，main仍只由用户合入。

### 2026-10-24 · Codex · 路由异常触发条件收口，未修复
- 做了什么：从4036d84a安全fetch/pull main；17项PnR对照保留7完成/9访问异常/1不确定。原路由器的data输入min-delay触发异常；保留全部约束、关闭自动hold修复可路由但hold为-1.402ns，明确失败，不当成解决方案。
- 在飞什么：同拍shell输入注册已做24000拍完整状态/输出的一周期对照，错位load反例cycle58检出，但完整约束仍崩溃；显式总线位名及另一布局/路由策略也失败。未修改产品RTL或三个current目录，下一步接真实contact/曲谱的逻辑生命周期与表达归属，完整时序阻塞独立保留。
- 卡在哪：PR4候选未合main；硬件四份上下文有UNREVIEWED_DRIFT，旧观察期限不因本次诊断自动续期。最小clock-only案例日志结束但vendor句柄不发信号，核实身份后只终止等待的自有supervisor，aborted保留、不算PASS。
- 需要对方什么：不接管原D盘/06df，不改PCB接口。先保留完整min-delay/hold判据，再研究有证据的修复路径；不重复原样空跑，不下载、Flash或制造。个人磁盘数据不再处理；C盘已恢复数GiB，但本会话不归因于自己的清理。
- 下一手从哪读：project/reviews/20261024-router-crash-diagnosis/summary.json、input/README.md及RESUME；源基线4036d84a，新源/证据由同一PR4交回，实际发布提交须查询PR head。main仍100b35b，只由用户合入。

### 2026-10-24 · Codex · 资源真实音频后端限定候选
- 做了什么：在认领的audio副本接真实512分量TDM/包络、统一音频边界发布/清退、自然结束反馈与复位静音围栏；546请求/4093PCM帧/4指定反例、旧路径177951拍对照和53 Python单测通过。
- 在飞什么：测试台仍提供分量；真实槽/音符生成器、指触/曲谱路由和完整NR07未接合。约0.5ms抢占淡出已向用户提问，尚未批准，不擅自固定音乐规则。
- 卡在哪：同版音频探针综合9749Logic/4122REG/11BSRAM/5DSP，不含完整产品外围/生成器；无PnR/STA/码流/板验。系统盘满曾中断观察，失败保留；只迁移自有测试虚拟环境至D盘并核对5048文件，不删历史源。
- 需要对方什么：原owner路径仍只读；设备接口和未决音乐规则分别交回。先接实际音符/完整槽数据与手指边沿，再做完整PCM/听感和同版时序，不能把即时清退当已合格防爆音。
- 下一手从哪读：experiments/note_resource_20261024/audio/README.md、project/versions/note-resource-audio-20261024.json与当前review；本轮基于33a1818，精确远程提交查询PR4。三个current目录未改，main仍由用户合入。

### 2026-10-24 · Codex · 共享实例资源协调器限定候选
- 做了什么：在已分配note_resource_20261024路径实现D-019协调器，32组/32实例/1–4层、尾音优先、原子资源预留/后端发布、迟到与重复身份保护、取消和背压；独立参考2045请求与3项定向变异检出。
- 在飞什么：当前只模拟PREPARE/PUBLISH/退场完成后端；真实音乐、包络结束、指触与曲谱适配和NR07尚未接合，不改D盘/06df/三个current源。
- 卡在哪：独立综合LUT6359→3035、REG2466→1590，但不是整机预算或时序通过；无新PnR、码流、下载或制造放行。加强背压监测时的失败保留，不删反例。
- 需要对方什么：后续限定副本提供可证明的装载/统一发布与包络结束反馈；来源内起音序号由入口合并器赋予，不能直接拿旧逐指8位代次冒充全局顺序。
- 下一手从哪读：experiments/note_resource_20261024/README.md、project/versions/note-resource-candidate-20261024.json及本批review；精确提交由实际PR head确认。

### 2026-10-24 · Codex · 资源规则确认与明确音乐profile
- 做了什么：用户逐项确认同等共享32组、整音符回收/新音完整起音、尾音优先例外；D-019替代旧严格FIFO，合同与NR判据见NOTE-RESOURCE-CONTRACT。
- 在飞什么：显式historical/current profile与三项定向故障反例；只在隔离导出目录执行。当前探针最多两层，不把四槽地址覆盖说成四层并奏已完成。
- 卡在哪：首轮current测试台存在声明顺序elaboration失败，保留attempt01后修复重跑；最终结果以本批review为准，不用编译失败冒充反例检出。
- 需要对方什么：保留D盘原owner边界；后续资源管理需真实包络结束/装载完成反馈及整机接合，不能只调整最多两层的数字。
- 下一手从哪读：project/NOTE-RESOURCE-CONTRACT.md、tools/scripts/music_profiles.py及governance当前review；不下载、无CAD/制造放行。

### 2026-10-24 · Codex · 长任务与T02隔离诊断
- 做了什么：用户确认产品复述准确；登记曲谱播放与现场并奏、溢出丢最早发声音符。每60分钟本线程续接，额度不足保全断点、不绕过。
- 在飞什么：本轮仅对已捕获候选做隔离T02诊断；不是认领D盘原FPGA实现路径。管理PR4仍由用户合入main。
- 卡在哪：当前默认力度配置使旧黄金不同且layers旧固定幅度断言失败；测试台vscale=0对照三组完全匹配，不能据此关闭产品力度或称新默认已验收。
- 需要对方什么：按OPEN-RULES关闭边界；新默认独立参考与完整产品接合仍需验证；不自动采用旧完整度加权抢占或播放降两层。
- 下一手从哪读：project/MUSIC-GOLDEN-DIAGNOSIS.md、project/OPEN-RULES.md及governance当前review；Git/额度/实验断点另存本机outputs/long-task-20261024/RESUME.md。

### 2026-10-24 · Codex · 规格与接手入口收口
- 做了什么：先pull --ff-only internal main到100b35b；建立PRODUCT-SPEC、SOURCE-MAP、WORK-PLAN，登记直接用户出处与旧提案勘误，修复公开后旧入口同步的private断言。
- 在飞什么：仍在codex/current-engineering-sources-20261023管理分支；本轮通过新PR交回，main由用户合并。
- 卡在哪：T02音乐黄金差异、T03/T04硬件及制造闭环仍未解决；不把文档修正称作这些实现已完成。
- 需要对方什么：按WORK-PLAN认领单一任务与路径；FPGA原owner身份、硬件接口和音乐未决规则分别确认。
- 下一手从哪读：project/DESIGN-CURRENT.md及governance当前review；精确版本以包含本记录的Git提交及实际PR head为准。原owner目录和341项工程源未修改。

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

当时要求推之前确认private；该历史要求已被用户2026-10-24公开仓库的决定替代。现在核对实际URL和仓库身份，不以private作为推送前提。

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
- Authoritative publication: actual target repository main (public since the user changed visibility on2026-10-24). Dated branch is fast-forward compatibility only; v1/v2 tags remain immutable.
- Decisions: project/decisions.json records accepted/proposed/superseded items with evidence; D-010 directly confirms retain J10 and existing controller route, superseding the external RA8875 cancellation interpretation.
- Freshness: project/governance.json/current review, 24h design review and6h active observations; --live detects actual local drift, missing roots are not green. Observe does not renew a review.
- Handoff: project/MAINTAINING-MAIN.md and NEXT-AGENT-PROMPT.md. Active unpublished code, FPGA owner identity gap and unvalidated hardware remain explicit. main merge still needs user approval for this new PR.

## 12. 2026-10-24 真实分量生成器限定交回

- 做了什么：4d37仍只写已认领experiments/note_resource_20261024及入口/证据；真实四槽表、音符上下文快照、分量生成与32组TDM接通。修复高倍率力度符号回绕、直接生成器配置/音符同时valid互等；旧源不改。
- 版本：任务分支codex/current-engineering-sources-20261023，源基点bff7c4e9d9de90be01ae2629a1472c78dfb29f9d；新提交由目标仓库PR4实际head解析，逐文件身份见project/versions/note-partial-renderer-20261024.json，不借main名义签候选。
- 验证：最终renderer03各16384分量×2、4幅度反例、独立5136装载/4080PCM帧；力度2097152向量、默认524288项兼容；并发互等旧RTL指定断言检出；60Python测试。同版综合11515Logic/4865REG/14BSRAM，未PnR/STA/下载/板验。
- 在飞什么：本轮所有03仿真/综合已终态；D盘原FPGA与06df只读。原硬件owner新保存a3a258局部ADDR1/49项13网，不抢占其CAD、路由或PCB范围；恢复ZIP另保全，341个current文件不变。
- 下一手：实际手指/曲谱事件源与身份/被抢占按住不重触发、激发自动OFF、独立PCM/瞬变、完整顶层/资源/PnR/STA；P-020短淡出待人类回复，其余未冻结边界继续成熟问答。产品未完成，main仅由用户合入。

## 13. 2026-10-24 双来源身份路由增量

- 做了什么：4d37只在原已认领experiments/note_resource_20261024/input及入口/证据实施两来源tag/轮转/响应路由，补排队取消；不改341个current、D盘owner或06df。
- 版本：源基点6e899f87a3fb1b1d601f6921a9b0a4ede31c2f75，任务分支codex/current-engineering-sources-20261023/PR4，最终提交以该PR实际head解析；输入及证据见project/versions/note-input-router-20261024.json。
- 验证：24000拍/3路由反例；547真实请求/5136独立装载与专门取消反例；68单测。最终同源综合11722Logic/4974REG/14BSRAM；PnR03/04在route80%进程0xC0000005，STA未生成，不签收。
- 在飞什么：旧工程已有轮转，缺口是新身份/多层接口不能盲接；物理contact/曲谱文件/多层手指表达和自动OFF仍缺。硬件只读审阅新离线antipad模型校正/局部候选，原生仍a3a258/49项13网，未导入/未制造。
- 下一手：先定位同源最小路由进程失败，保留现有反例与原约束；接contact生命周期/全部层绑定和曲谱背压，补同拍实际PCM及完整顶层验收。P-020无答复不默认实施，不重问D-019。
