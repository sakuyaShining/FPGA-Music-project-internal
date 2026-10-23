# 快速取得当前已发布设计

多人协作或不授予仓库权限的离线任务，见[COLLABORATING.md](COLLABORATING.md)。

仓库：`https://github.com/sakuyaShining/FPGA-Music-project-internal.git`（已核对private）。

在新目录取唯一发布入口main；现有脏目录不能强制覆盖：

```powershell
git clone --origin internal --branch main --no-single-branch https://github.com/sakuyaShining/FPGA-Music-project-internal.git D:/FPGA-Project/review/current-design
```

进入该目录，执行：

```powershell
python tools/scripts/project_control.py check --full --remote --fresh-entry
python tools/scripts/design_governance.py status --remote
```

先读`project/DESIGN-CURRENT.md`、`governance.json`和`decisions.json`，再读`AGENT-START.md`、`handoff.json`和协作板。本机可访问活跃源时另运行`python tools/scripts/design_governance.py status --remote --live`；不可访问显示UNOBSERVED，不继承本机实时结论。观察或审阅过期需更新正式审阅，不能只改日期。

已有这版工具，可用`python tools/scripts/project_control.py get-latest --output <不存在的新目录>`完成克隆、完整校验及私有internal默认推送设置；不会切换或覆盖现有工作树。

更新专门用于阅读、没有本地修改的入口工作区时，先看`git status --short`，再`git fetch internal`与`git merge --ff-only internal/main`。存在本地修改或分叉则另取新目录，保留原任务分支；禁止reset/clean/强推来通过检查。

PR #1已合入main；后续入口同样通过管理PR维护。冻结标签仅用于复现。旧日期分支为只快进兼容入口；新工具直接核对实际main。维护合同、有效期及owner交回步骤见`project/MAINTAINING-MAIN.md`。
