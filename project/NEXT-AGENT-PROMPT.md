# 可直接交给下一位Agent的启动指令

接续FPGA-Music-project。内部仓库为https://github.com/sakuyaShining/FPGA-Music-project-internal.git；唯一发布入口是实际远程main，先fetch再核对。日期分支只兼容旧工具，v1/v2标签仅用于固定复现，不能定义实时最新。

按project/QUICKSTART.md在新目录取得main，执行`python tools/scripts/project_control.py check --full --remote --fresh-entry`和`python tools/scripts/design_governance.py status --remote`。先读project/DESIGN-CURRENT.md、governance.json、decisions.json、producers.json、MAINTAINING-MAIN.md及AGENT-START/handoff/CURRENT、AGENTS和协作板，再读38/39/49号。不可用旧版本、过期记录或reset/clean覆盖来通过检查。

`restore-design --area fpga`恢复12:23的v2固定105输入候选，不是当前活跃源。13:07审阅已发现新增双段衰减及源/测试修改，详见governance当前review；不把这些作者报告当成本轮复验。继续本机功能工作前运行`design_governance.py status --remote --live`，源不可见/新增/修改/删除则要求owner交回及新审阅。旧100输入PASS不签收后续源；tdm_ship_owned名称不代表84节点/J10/存储完整载板顶层已接合。

重现旧100输入时才用m1-work+v1登记增量；保留v1黄金测试。硬件上下文和原生恢复ZIP可用restore-design --area hardware-context取回，仅恢复所列文件，不导入CAD；活跃硬件由原owner继续，总入口缓存与下级施工状态须核对实际原生哈希。

当前用户决定：取消J11实体音乐可视化屏，保留J10右手泛音触控屏；原话及会话turn已归档，覆盖旧双屏红线。保持Nano20K、32×16、四层、逐音滑条与独立八度条、84节点硬件能力、录放与非易失等其他目标。不擅自改音乐语义、减其他功能、改PCB接口、下载或制造放行。

在自己的命名任务分支导入选定源并先提交起点，适配独立输出。说明源提交、归档SHA、验证边界、owner和下一步；不覆盖其他owner。收工commit并核对private internal远程，再更新入口；未登记的未来变化不属于本批已发布版本。
