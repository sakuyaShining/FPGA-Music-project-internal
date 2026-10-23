# 快速取得当前已发布设计

仓库：`https://github.com/sakuyaShining/FPGA-Music-project-internal.git`（已核对private）。

在新目录取当前发布分支；现有脏目录不能强制覆盖：

```powershell
git clone --origin internal --branch codex/project-management-20261022 --no-single-branch https://github.com/sakuyaShining/FPGA-Music-project-internal.git D:/FPGA-Project/review/current-design
```

进入该目录，执行：

```powershell
python tools/scripts/project_control.py check --full --remote --fresh-entry
```

先读`project/DESIGN-CURRENT.md`，再读`AGENT-START.md`、`handoff.json`和协作板。机器登记为`project/design-state.json`。

已有这版工具，可用`python tools/scripts/project_control.py get-latest --output <不存在的新目录>`完成克隆、完整校验及私有internal默认推送设置；不会切换或覆盖现有工作树。

更新专门用于阅读、没有本地修改的入口工作区时，先看`git status --short`，再`git fetch internal`与`git merge --ff-only internal/codex/project-management-20261022`。存在本地修改或分叉则另取新目录，保留原任务分支；禁止reset/clean/强推来通过检查。

冻结标签仅用于复现，不能当作永远最新。用户已授权本次代理合并PR #1；是否已经合入以GitHub实际PR状态和main提交为准。main包含当前入口后，普通默认clone可直接使用；读取旧本地main仍必须取回远程并通过fresh-entry检查。
