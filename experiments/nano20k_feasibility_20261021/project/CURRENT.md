# Nano20K 完整功能可行性评估 · 2026-10-21

本轮在4d37独立工作树进行，源自主项目86号实验；硬件只读绑定06df的
`hardware/review-manufacturing-20261019/REGIONAL-WORK-IN-PROGRESS.json`。

完整结论与预算：本工作树`docs/02-技术方案/87-Nano20K完整功能可行性与预算-2026-10-22.md`。

- `budget.py` → `budget.json`、`resource-allocations.csv`：资源实测账、缺项的设计分配和时序算式。
- `check_renderer.py`：8388608组穷举像素对照和边界故障反例。
- `check_engine_compat.py`：三组原音乐逐拍轨迹985PCM。
- `check_joint.py`：两延迟音乐录入/读出、图案播放；使用内部force，不是产品协议。
- `build_board.py build_nominal_v0 nominal`：同86号结构探针、原CST/SDC、只改renderer的完整PnR。
- `audit_current.py` → `results.json`：严格记录退出码、路由、STA、源身份与失败，产品签收永远为false。
- `analyze_paths.py`：从真实STA抽取setup/hold逐节点表及网络/单元延时。

正常完整PnR已完成：654.58秒，路由/码流生成通过；后端20338Logic、10346CLS、32BSRAM、22.75DSP。
Setup −6.397ns、hold −0.048ns，时序FAIL。加严未运行，先修正常明确违例。
唯一renderer变更综合节省141Logic，其他源及约束保持；不把结构探针通过路由写成产品实现成功。

**不是可下载产品。** 保留32组×16分量、双显示目标、逐音滑条、四槽/完整分层目标、录放/非易失目标。
当前真实产品顶层仍缺少接口服务和功能，不能把本结构探针冒充全功能产品PnR。
复制自86号的其他脚本、reference和测试只作历史参考，其旧审计断言及目录不适用于本轮。
原主项目、06df硬件、GUI、约束和历史交付保持；本轮没有串口、下载、Flash、TF或PCB写操作。

大产物在`D:/FPGA-Project/codex-builds/nano20k-feasibility-20261021/`，通过本目录的build/evidence联接读取。
复制交付时须包含D盘产物或按脚本重跑；它们不随普通Git源码自动携带。
