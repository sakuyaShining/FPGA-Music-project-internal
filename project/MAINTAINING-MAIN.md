# main长期维护合同

## 权威与启动

仓库`FPGA-Music-project-internal`（用户已公开）的实际远程`main`是唯一已发布设计入口。日期分支、冻结标签、文件mtime和会话记忆均不能替代它。新Agent先检查本地状态，在干净入口目录`git pull --ff-only internal main`，再读`AGENTS.md`、`DESIGN-CURRENT.md`、`PRODUCT-SPEC.md`、`SOURCE-MAP.md`、`WORK-PLAN.md`、`governance.json`、`decisions.json`、`producers.json`及协作板。不得提交完整会话、令牌或账号配置。

```powershell
python tools/scripts/project_control.py check --full --remote --fresh-entry
python tools/scripts/design_governance.py status --remote
python tools/scripts/design_governance.py status --remote --live
```

第一条核验身份与审阅期限；第二条查看已发布审阅、未合并WIP及生产分支登记；第三条额外只读检查本机活跃工程。**`--live`源不可访问、文件有新增/修改/删除或审阅到期，返回非零并明确原因。**云端不能查看本机D盘，必须显示未检查，不能写成已实时同步。

读取历史快照可以继续研究，但须明确所选源身份与截止时间。开始修改某一功能前，要确认对应owner、来源和任务分支；检查本身从不授权接管他人目录或签收完整产品。

## 三类事实分开维护

1. `decisions.json`保存稳定ID的已确认决定、提案与被替代决定，绑定证据文件及SHA256。确认新决定要写人类出处/源文档和supersedes，不能删除旧决定来掩盖沿革。没有原始确认的实现选择仍是候选。机器会检查多重当前决定、覆盖链循环和当前scope与已确认事实冲突。
2. `producers.json`声明活跃源、owner、观察范围、可恢复来源、发布分支/精确commit和观察有效期。新增会话/工作区必须登记；owner未知、未发布代码、不可访问源都必须明示。暂停观察需有原因及后续恢复条件，不能为消除过期提示把活跃源随意改成dormant。
3. `governance.json`指向不可覆盖的审阅记录和受控文件指纹。审阅记录保留逐文件观察与对未登记变化的判断。设计审阅窗口24小时、活跃源观察窗口6小时是当前维护阈值，**不等于功能或硬件合格时长**；已确认设计不会因日期自动变成错误，但需要重新确认是否出现后续决定。

## 新信息怎样进入main

- 用户在任何会话改变目标：记录直接原话或明确来源，更新决定账本、当前设计、机器scope和冲突标记。未决项写“讨论中/待实现”，不能把Agent建议直接批准为产品语义。
- 功能owner收工：使用命名任务分支提交RTL、表、约束、主机协议、构建/验证脚本及输入清单；核实目标仓库URL后推送有权限的任务分支，或经fork提交PR，登记实际远程commit和对应结果。旧source/profile的PASS不能继承。
- 先产生新观察（不会续期）：

```powershell
python tools/scripts/design_governance.py observe --output <新的审阅目录>/observation.json
```

- 人工审阅变化，保全必要设计证据，区分实现WIP/新提案/已确认决定/验证结果，写新的review.json。需要新源码快照时先评估与适当核验，再使用新ID；旧归档不覆盖。仅改日期或复制旧PASS不能解除漂移。
- 更新governance指针、review SHA、受控文件SHA及各入口，提交管理PR。CI验证候选的结构、证据、冲突与期限；用户按协作板批准main合并。合入后从真实main复验，保留结果。其他owner持续变化时保持未登记WIP标志，不声称无限实时同步。

## 自动发现失效

GitHub在main push、PR和手动运行时检查；另每6小时计划检查一次审阅有效期。到期会失败，**不会自动改日期、采纳设计、重写归档或替owner验收**。计划任务实际运行受GitHub调度影响，手动命令直接按当前时间判断，不能以最近一次CI绿灯永久放行。

main push还将旧`codex/project-management-20261022`兼容入口只快进到实际main，使v2旧工具不会永远盯住不动的日期分支。该job核对完整仓库名及不可变仓库ID `1404161021`，不再要求private；分叉则失败，禁止force-push。新工具始终直接核对main，旧标签不移动。

GitHub检查不能发现从未登记、也未提交的新会话决定；长期可靠需要每个会话履行上述交回合同。当前不把服务器合并保护、多人owner确认或完整备份默认视为已经落实。
