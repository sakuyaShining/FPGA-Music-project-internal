# 可直接交给下一位Agent的启动指令

请接续FPGA-Music-project，但先确认最新交接身份。内部仓库是https://github.com/sakuyaShining/FPGA-Music-project-internal.git；本批管理入口分支是codex/project-management-20261022，冻结标签是handoff/20261022-management-v1。main在管理PR合并前仍可能只含旧入口，不要从旧main推断最新实现。

取回并阅读该入口分支的project/AGENT-START.md、project/handoff.json、project/CURRENT.md、AGENTS.md和协作板；执行project_control.py check --remote --fresh-entry，首次接手再加--full。版本不匹配时先停止实施，不用旧文件替代。

继续FPGA M1工作时，使用登记的m1-work检查点加未验证M1源增量；用restore --snapshot m1-work --with-source-delta恢复到新审阅目录，然后在自己的命名Git任务分支中导入有效构建输入并提交起点。保留原黄金轨迹和测试约束，不覆盖其他owner或复用旧构建输出。旧的M1 README、原4d37的路由/STA与历史板验不能签收这一份源。

当前完整功能产品顶层尚未实现并验收。不得削减既定功能、更换Nano20K、修改PCB接口、下载码流或制造放行。先说明你实际选用的源提交、增量SHA、验证边界和当前任务，再继续工作；收工提交并核对internal远程，更新交接入口。
