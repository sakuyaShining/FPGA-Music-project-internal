# 工程与资料地图

当前main为发布入口；先pull并核对提交。产品目标读`PRODUCT-SPEC.md`，工程读`ENGINEERING.md`，任务读`WORK-PLAN.md`，勘误读`corrections.json`。不要按目录日期或旧HEAD选最新版。

| 资料层级 | 接手位置 | 原来源/职责 | 不可混用的范围 |
|---|---|---|---|
| 当前可编辑FPGA候选 | `fpga/current/`，253项清单文件 | D盘M1捕获，106项RTL/表/约束，另含脚本/测试/参考/黄金数据 | 完整产品顶层未接合，音乐黄金有已记录失败；原生产目录后续变化不会自动进仓库 |
| 当前保存硬件候选 | `hardware/current/native/`、`context/`，50项 | 06df/U9ControlWork保存源e098c5db… | 47项未连通/13网，不能直接制造；37项保留基线是另一份源；旧会话句柄禁止复用 |
| 当前主机候选 | `host/current/`，38项 | ca03，host-workbench-20261015-11 | 已含重奏测量测试依赖；离线100项通过，当前FPGA协议兼容未板验；其他GUI分支未批量合并 |
| 活跃生产目录 | `producers.json`声明的FPGA和硬件根 | 原owner继续工作，实施前运行`status --live` | 只读比较声明范围；本地图谱不授权接管原目录，不宣称包含未保存CAD状态 |
| 资源管理增量候选 | `experiments/note_resource_20261024/`及`versions/note-resource-candidate-20261024.json` | 4d37限定副本，D-019资源合同 | 32组/四层分配协调器单元与独立综合，不改341项工程源；尚缺真实音乐后端、包络结束和曲谱/触摸接合，不能替代完整顶层 |
| 资源真实音频后端增量 | `experiments/note_resource_20261024/audio/`及`versions/note-resource-audio-20261024.json` | 4d37限定副本，真实TDM/包络 | 512分量事务发布/退场/自然结束局部验证；仍是测试台提供分量，实际槽/音符生成及手指/曲谱待接，无PnR/STA/实体签收 |
| 历史已接合音乐/主机 | 66a4/07及各自清单 | `workspace-preservation-20261022.json` | 旧板验只绑定旧输入；安全修复候选另看instrument-engine-safety |
| 其他候选 | 6e70、a61b、4c43、WorkBuddy分支等 | 22个preserve分支及原工作树 | 未提交文件需与快照逐项比对；保全不是合入产品，禁止批量merge代替审查 |
| 旧根源码 | `src/rtl`、`src/gowin`、`tools/host` | 历史复现入口 | 不能代替三个current目录，不删除其旧证据 |
| 历史恢复 | v1/v2、`project/archives/`及旧handoff字段 | 固定检查点；v2为10月23日12:23 | 恢复不继承新测试，也不等于实时最新 |
| 作者设计与采购原文 | `fpga/current/upstream-notes/`、硬件context旧README | 保留提案、估算和沿革 | 按`corrections.json`排除过时双屏、小样、bank解释和旧PASS；不能直接下单 |

341项身份由`versions/engineering-sources-20261023.json`定义；字节来源、两处适配及失败记录见`reviews/20261024-engineering-publication/`。更新一项功能必须产生新的源身份与对应结果，不能仅更新哈希继承旧PASS。

## 外部协作者最短路径

1. 克隆main；已有无本地修改的任务目录先`git pull --ff-only internal main`，remote名称不同则核实URL后调整；脏目录停止并保全，不能reset/clean。
2. 运行工程/治理检查，按任务选一个领域，导出到新目录；原生产目录不可见时只依赖已发布检查点，不声称实时同步。
3. 任务卡填写owner、允许写路径、源提交/清单、接口依赖与验收条件。按`WORK-PLAN.md`的任务边界交回源码、日志和未验证项。

下载/制造仍需单独授权。仓库现在公开；公开读取不等于获得直接推main的权限，协作者仍通过任务分支或fork PR交回。
