# 新Agent启动入口：先确认版本，再实施

本次交接以`project/handoff.json`为机器入口，以本页为启动流程。**“最新”指总入口登记并保全的检查点，不是任意目录的最后修改时间。活跃目录之后的修改必须另行登记。**

## 1. 避免读到旧入口

此批入口分支为`codex/project-management-20261022`，冻结交接标签为`handoff/20261022-management-v1`。main在本管理PR合并前仍是旧入口；不能只读main旧README就开始实现。

先核对远程URL。当前老仓库的origin/public是对外地址，internal才是内部开发仓库；新克隆的origin则可能就是内部仓库。不要凭remote名称判断。

```powershell
git ls-remote --heads https://github.com/sakuyaShining/FPGA-Music-project-internal.git refs/heads/codex/project-management-20261022
```

在独立的管理入口工作区取回并读取该分支。已有脏工作区先保全，禁止reset --hard、clean或强制checkout。需要新工作区时使用已核对的管理分支作为来源，创建自己的命名任务分支，避免覆盖其他owner。

```powershell
python tools/scripts/project_control.py check --remote --fresh-entry
python tools/scripts/project_control.py check --full --remote --fresh-entry
```

检查失败时停止实施，先修复版本归属。旧入口不含该检查参数而报错，同样不能视为通过。标签固定本次交接；未来交接需要更新登记和新标签，旧标签不能冒充实时最新。

## 2. 接手哪个领域

| 任务 | 使用的来源 | 不得混用 |
|---|---|---|
| 已验音乐行为与主机基线 | 66a4的07记录；安全候选另看instrument-engine-safety | 旧板验不能签收新安全修复或M1 |
| 继续M1资源/时序工作 | m1-work检查点 + 已登记的M1源增量 | 4d37原probe不是M1最新版；M1原README和旧报告不定义当前源身份 |
| 重现87号原结果 | 4d37检查点或v1便携包 | 原路由完成但STA失败，不是完整产品 |
| GUI/协议 | ca03、6e70的明确源版本 | 不默认已与M1接合 |
| 硬件/CAD | 06df入口、native来源/试作/R15检查点及后续增量记录 | pending原生文件、verified来源、旧R15不得合称同一版；禁止自动重放事务 |

负责人和接口边界见协作板。若同一目录仍有owner在写，另建隔离任务分支；不得直接接管其工作目录。每个owner同时只推进一个任务。

## 3. FPGA侧直接取得本次最新已保全源码

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

这是结构/音乐候选的继续开发入口，仍不是完整功能产品顶层。保留Nano20K、32×16、四层、双屏、逐音滑条、录放与非易失目标；不改PCB接口，不擅自削减功能、下载或制造放行。

## 4. 每次收工

提交源与清单，核对internal实际远程提交，更新当前profile/交接和下一步。新结果只绑定实际测试的源；新变化如果尚未接入总入口，明确标为未登记WIP，不能宣称下一位Agent会自动读到它。
