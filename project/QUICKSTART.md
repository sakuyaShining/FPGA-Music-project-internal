**2026-10-29 基线复核更正：传感板暂停投产。** 实际S1 Gerber底层地铜到22个非地排针焊盘最小间距约0.162858mm，低于保留门限0.1651mm；此前原生DRC0、5μm图形比对与较低通用门限未覆盖该严格条件。可继续询价，先不按本版传感板付款生产。旧冻结包字节保留用于追溯，不能据其中的PASS或READY文字忽略本更正。详见基线`evidence/retained-clearance-gate-audit.json`。

**2026-10-29 硬件交付基线更新**：送厂与采购接续先读[DELIVERY-BASELINE-20261029.md](DELIVERY-BASELINE-20261029.md)。当前为Control88 R2×1 + Sensor14Bank S1×6，制造源核验已完成，可交厂家DFM/SMT审单报价；屏幕/附件报价、固件接合、实物及整机验收仍待完成。下文旧日期的951载板和早期小板状态仅适用于各自历史版本。本更新仍是任务分支候选，main发布以实际合入为准。

# 快速取得当前已发布设计

当前可开发的工程、依赖和验证命令见[ENGINEERING.md](ENGINEERING.md)。克隆后先执行`python tools/scripts/engineering.py check`，再按[协作检查点](COLLABORATION-CHECKPOINT-20261024.md)选择一个领域；不要直接在历史`src/rtl`或`tools/host`继续最新实现。

多人协作或不授予仓库权限的离线任务，见[COLLABORATING.md](COLLABORATING.md)。

仓库：`https://github.com/sakuyaShining/FPGA-Music-project-internal.git`（用户已公开，读/克隆不需邀请；直接推送仍需权限，外部协作者可fork后提交PR）。

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

已有这版工具，可用`python tools/scripts/project_control.py get-latest --output <不存在的新目录>`完成克隆、完整校验及internal默认推送设置；不会切换或覆盖现有工作树。产品与待办先读PRODUCT-SPEC.md、SOURCE-MAP.md及WORK-PLAN.md。

更新专门用于阅读、没有本地修改的入口工作区时，先看`git status --short`，再`git pull --ff-only internal main`。存在本地修改或分叉则先保全并另取新目录，保留原任务分支；禁止reset/clean/强推来通过检查。任务分支上有自己的提交时，不把pull失败当作覆盖本地成果的理由。

PR #1已合入main；后续入口同样通过管理PR维护。冻结标签仅用于复现。旧日期分支为只快进兼容入口；新工具直接核对实际main。维护合同、有效期及owner交回步骤见`project/MAINTAINING-MAIN.md`。

最新4d37隔离增量从`experiments/note_resource_20261024/audio/renderer/README.md`及`project/versions/note-partial-renderer-20261024.json`接手：真实四槽/音符分量→PCM已限定验证，尚缺手指/曲谱源、激发自动OFF、完整顶层/PnR/STA。T02与D-019三项已收口，不重复定位或重问；P-020短淡出仍未批准。新硬件原生a3a258/49项13网的只读保全与旧hardware/current e098/47项必须分开。PR4候选不等于main。
