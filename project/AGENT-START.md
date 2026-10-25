# 新Agent启动入口：先确认设计，再确认源版本

**2026-10-25 PCB接续候选**：最新951原生施工检查点及完整恢复链见`hardware/checkpoints/pcb-951ce88a-20261025/`，计划见`project/PCB-RESOLUTION-PLAN-20261025.md`；原hardware/current的e098保留历史。此任务分支未合入main，未新增CAD/DRC/实物验收。用户已授权向当前Public internal直接同步，覆盖旧private-only推送条件。

当前工程候选已展开到`fpga/current/`、`hardware/current/`和`host/current/`。先读[ENGINEERING.md](ENGINEERING.md)与[协作检查点](COLLABORATION-CHECKPOINT-20261024.md)，校验输入并选择限定任务。以下v1/v2恢复步骤仅用于历史复现，不是本批最新工程。

外部成员和离线补丁接手方式、任务卡及交回要求见[COLLABORATING.md](COLLABORATING.md)。

**先读[当前设计](DESIGN-CURRENT.md)、`governance.json`与`decisions.json`。实际远程main为唯一已发布入口。用户取消J11实体可视化屏、保留J10泛音触控屏的决定继续有效；旧双屏说明不能覆盖它。**

快速克隆及完整检查见[QUICKSTART.md](QUICKSTART.md)。`restore-design`恢复的是v2固定检查点，不能称为活跃源最新；13:07审阅已发现后续双段衰减及硬件施工变化，见governance当前review。恢复先读新生成的来源清单，旧README/source-identity不定义本次验收。

本次交接以`project/handoff.json`为机器入口，以本页为启动流程。**“最新”指总入口登记并保全的检查点，不是任意目录的最后修改时间。活跃目录之后的修改必须另行登记。**

## 1. 避免读到旧入口

发布入口为实际远程`main`。v1/v2标签复现旧检查点，日期管理分支仅兼容旧工具。新工具不得再用日期分支代替main检查。

先核对远程URL。当前老仓库的origin/public是对外地址，internal才是内部开发仓库；新克隆的origin则可能就是内部仓库。不要凭remote名称判断。

```powershell
git ls-remote --heads https://github.com/sakuyaShining/FPGA-Music-project-internal.git refs/heads/main
```

在独立入口工作区fetch并读取main。已有脏工作区先保全，禁止reset --hard、clean或强制checkout。需要新工作区时使用已核对main作为来源，创建自己的命名任务分支，避免覆盖其他owner。

```powershell
python tools/scripts/project_control.py check --remote --fresh-entry
python tools/scripts/project_control.py check --full --remote --fresh-entry
python tools/scripts/design_governance.py status --remote
python tools/scripts/design_governance.py status --remote --live
```

检查失败先修复归属/审阅，不直接实施。`--live`在本机比对声明范围内的新增/修改/删除；不可访问或源已变化时报告UNOBSERVED/UNREVIEWED_DRIFT。跨机器阅读可用已发布记录，但不得把未观察源写成已同步。过期也非通过；observe仅生成新观察，不续期。更新合同见MAINTAINING-MAIN.md。

## 2. 接手哪个领域

| 任务 | 使用的来源 | 不得混用 |
|---|---|---|
| 已验音乐行为与主机基线 | 66a4的07记录；安全候选另看instrument-engine-safety | 旧板验不能签收新安全修复或M1 |
| 继续活跃FPGA工作 | producers.json的owner/源与当前review；未登记的新源由owner交回 | v2的105输入只是固定可恢复源；后续双段衰减未因此获得新归档或验收 |
| 重现10月22日M1检查点 | m1-work检查点 + v1已登记源增量 | 这是历史100输入，不再称实时最新；M1原README和旧报告不定义新源身份 |
| 重现87号原结果 | 4d37检查点或v1便携包 | 原路由完成但STA失败，不是完整产品 |
| GUI/协议 | ca03、6e70的明确源版本 | 不默认已与M1接合 |
| 硬件/CAD | 先读当前design-state所列06df活跃入口和本批硬件上下文 | 旧06df/native/R15是历史恢复；总入口缓存与下级施工源可有差异，须由owner核对真实原生哈希，禁止自动重放 |

负责人和接口边界见协作板。若同一目录仍有owner在写，另建隔离任务分支；不得直接接管其工作目录。每个owner同时只推进一个任务。

## 3. 复现历史100输入FPGA检查点

先读handoff.json中的`fpga_handoff`及源截止时间，再恢复到**新的审阅目录**：

```powershell
python tools/scripts/project_control.py restore --snapshot m1-work --with-source-delta --output D:/FPGA-Project/review/m1-handoff-20261022
```

该命令校验基底和增量哈希，只对M1源执行增量叠加，不对PCB或原生工程重放变更。输出的AGENTS.md和PRESERVATION-ORIGIN.json是本恢复目录入口。继承的source-identity、README、M1说明与历史证据用于追溯，不能覆盖新来源身份或继承为新验收。

**在受控命名分支中开始实施：**

1. 使用便携包工具在自己的Git工作树下创建新的实验目录，保留原黄金轨迹、TB和参考模型；包内WORKFLOW.md给出了适配命令。不要把新开发源码放回codex-builds。
2. 将上述恢复源的`engine/src`、`engine/rtl`、`rtl`和`constraints`中100个构建输入导入该实验，逐项记录SHA256；不要覆盖便携包的受保护测试、黄金数据或模型。
3. 将新实验源码、约束、配置、验证入口与来源清单提交为起点检查点，再做功能或优化修改。大黄金数据可从受跟踪交接ZIP重建；不得让其唯一副本留在被忽略目录。
4. 在新的证据/run ID下运行相应回归；新RTL/profile需要新的完整PnR与STA。没有新结果就写待验证，不引用旧source/profile的PASS。

这是历史结构/音乐候选的恢复流程，仍不是完整功能产品顶层。当前目标以DESIGN-CURRENT.md为准：保留Nano20K、32×16、四层、J10触控屏、逐音滑条、录放与非易失；用户已取消J11实体音乐可视化屏。本流程不自动改RTL或PCB接口，不擅自削减其他功能、下载或制造放行。

## 4. 每次收工

提交源与清单，核对internal实际远程提交，更新当前profile/交接和下一步。新结果只绑定实际测试的源；新变化如果尚未接入总入口，明确标为未登记WIP，不能宣称下一位Agent会自动读到它。
