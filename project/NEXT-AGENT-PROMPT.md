# 可直接交给下一位Agent的启动指令

接续FPGA-Music-project。内部仓库为https://github.com/sakuyaShining/FPGA-Music-project-internal.git；实时发布入口分支为codex/project-management-20261022，本批冻结标签handoff/20261023-design-v2仅用于复现。main在PR #1合入前仍可能是旧入口。

按project/QUICKSTART.md在新目录取得发布分支，执行`python tools/scripts/project_control.py check --full --remote --fresh-entry`。先读project/DESIGN-CURRENT.md、design-state.json、AGENT-START.md、handoff.json、CURRENT.md、AGENTS.md和协作板，再读38/39/49号文档。版本不匹配先修复归属，不用旧文件替代，禁止reset/clean覆盖脏工作区。

最新观察FPGA源码用`project_control.py restore-design --area fpga --output <新目录>`恢复。105项构建输入及新测试/设计说明是未合并候选；旧100输入源的engine/pitch PASS不签收它。先读恢复生成的AGENTS.md/PRESERVATION-ORIGIN.json；原README、source-identity及INFO-BASELINE包含过时信息。原作者仿真/PnR/板测按实际source/run复核，本管理批未重跑。tdm_ship_owned名字不代表84节点/J10/存储完整载板顶层已接合。

重现旧100输入时才用m1-work+v1登记增量；保留v1黄金测试。硬件上下文和原生恢复ZIP可用restore-design --area hardware-context取回，仅恢复所列文件，不导入CAD；活跃硬件由原owner继续，总入口缓存与下级施工状态须核对实际原生哈希。

当前用户决定：取消J11实体音乐可视化屏，保留J10右手泛音触控屏；原话及会话turn已归档，覆盖旧双屏红线。保持Nano20K、32×16、四层、逐音滑条与独立八度条、84节点硬件能力、录放与非易失等其他目标。不擅自改音乐语义、减其他功能、改PCB接口、下载或制造放行。

在自己的命名任务分支导入选定源并先提交起点，适配独立输出。说明源提交、归档SHA、验证边界、owner和下一步；不覆盖其他owner。收工commit并核对private internal远程，再更新入口；未登记的未来变化不属于本批已发布版本。
