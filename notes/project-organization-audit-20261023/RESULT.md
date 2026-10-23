# 当前设计与Git接手修复 · 2026-10-23

本轮继续管理轴，未修改其他会话的源码、CAD、Git索引或分支。发布分支沿用`codex/project-management-20261022`，本批设计版本`design-20261023-v2`，冻结标签`handoff/20261023-design-v2`。

## 纠正的上下文

- 从“查看 huangyongtao 最新进展”会话取得直接人类决定：取消实体音乐可视化屏，保留右手泛音触控屏。原话与turn ID进入Git；旧双屏红线在这一项被覆盖，其他功能不裁减。
- 06df原生施工已按J11取消/J10保留推进，37项保留基线与U9施工副本分别记录。总入口缓存与下级施工状态有更新先后差异；本轮不运行CAD，不晋升或制造放行。
- D盘M1目录已有新源码、测试、复位/力度/strike文档，旧project/CURRENT和INFO-BASELINE却仍有旧探针、双屏及Git状态。本次不根据标题日期采纳其中全部结论。
- 新归档包含586项：575项FPGA源/测试/上下文、11项硬件上下文/既有恢复ZIP。105项构建输入相对旧100项为8修改、1删除、6新增；归档时间及哈希见清单。活跃目录后续修改不自动进入该归档。
- `tdm_ship_owned`默认16直连pad、FINGER_EXPR/RIGHT_TIMBRE关闭及常量控制口，不能冒充84节点/J10/存储完整载板顶层。原作者专项仿真/PnR/板测是保留的来源记录，本管理批未重跑，也不继承旧100输入PASS。

## 可直接使用的入口

`project/DESIGN-CURRENT.md` → `project/design-state.json` → `AGENT-START.md`/`handoff.json`。快速克隆见`project/QUICKSTART.md`；转交其他会话用`project/NEXT-AGENT-PROMPT.md`。

`project_control.py get-latest --output <新目录>`从私有发布分支克隆，并完整核验远程检查点、归档及入口身份；不覆盖现有目录。`restore-design`按fpga或hardware-context恢复所列输入，写新来源清单，不执行原构建、CAD或下载。

自动检查配置在`.github/workflows/project-entry.yml`，覆盖入口、设计源指纹及全部保全内容。它是内容一致性检查，不是RTL/制造验收；服务端是否强制合并检查另论。实际远程运行与恢复结果见本批验证记录。

## 验证与剩余边界

22份历史快照18,277输入完整哈希及实际远程ref检查通过；新归档逐文件核验、FPGA/硬件上下文恢复后哈希核对通过。重复恢复/克隆到已有目录均拒绝，原恢复文件未改变。发布后的新克隆与自动检查结果单独登记，不能预填PASS。

main仍按协作板由用户合并PR #1。合入前必须显式取管理分支；v1/v2标签都是固定检查点，不叫实时最新。目录迁移、跨候选功能合并、完整产品PnR/STA、实物/制造验证均不属于本次管理验收。
