# 951ce88a PCB施工与恢复检查点

这是可恢复、可继续审查的施工版本；状态为**部分实现**，未完成整板或制造验收。原生板与离线候选分别封存，禁止把离线进度算作原生改善。

- `native/`：完整19文件可编辑工程，含14张原理图、工程描述、PCB、面板和配置。PCB SHA256为`951ce88a1a2fcc2d758f9a53222a400cbddd3bc5b689cc2a37c98b8303d9ca4d`。227件、649孔、42项未连通、12个开放网。
- `offline/`：IOtail-cleanup当前候选、期望几何、接地参考上下文和原始证据。62条新线、24个新孔，MUX仍为4岛；**不可导入原生**。文件中旧绝对路径只作出处，运行旧脚本前必须适配到新的独立目录，不能重放终态apply。其中两个大JSON（plane-context 80.9MB、input-cache 55.9MB）字节存于Release `pcb-951-full-20261025`，其余15项在树内。
- `evidence/`：ADDR2原生保存重开验证和来源入口；本次只核对字节，没有重新执行CAD、DRC或实物测试。
- `procurement/`：951同版227行坐标及采购上下文，仍为草稿；价格、库存、显示模组配置和PCBA报价未刷新。
- `recovery/`：完整515,422,319字节恢复ZIP的11个顺序分卷，保留全部原生父恢复链和离线历史上下文。分卷不裁减原ZIP内容。**分卷字节存于Release `pcb-951-full-20261025`，不进Git树**，`manifest.json`记录每个分卷的字节数与SHA256，`external_storage`声明Release位置与合并后SHA。`archive-inventory.json`列出顶层37成员。
- `manifest.json`：73项交付文件的字节数、SHA256、来源和分卷顺序，其中60项在树内、13项标`storage: "release"`。逐项核对了原owner入口声明的38个原生/回退文件，以及当前16项候选证据SHA。

外置判据：单文件超过50MB，或整卷归档。仓库因此从728MiB降到106MiB，而身份仍可逐项追溯。

在仓库根目录校验：

```powershell
python tools/scripts/pcb_checkpoint.py                 # 树内60项逐字节核对，外置项核对声明
python tools/scripts/pcb_checkpoint.py --git-ref HEAD   # 再加Git blob字节核对
# 需要复验外置622MiB时，先取回字节再跑强模式：
gh release download pcb-951-full-20261025 --dir hardware/checkpoints/pcb-951ce88a-20261025 --pattern 'archive.part*' --pattern '*.json'
python tools/scripts/pcb_checkpoint.py --require-external
python tools/scripts/pcb_checkpoint.py --restore-archive D:/FPGA-Project/review/new-pcb-recovery/checkpoint.zip
```

恢复命令要求目标ZIP不存在；合并分卷后再验证完整SHA。解压旧恢复ZIP应使用新目录，原有session、apply文件和绝对路径不构成新CAD操作授权。最新规划见`project/PCB-RESOLUTION-PLAN-20261025.md`。

旧`hardware/current/`及341项工程清单保持原样，继续复现e098历史版本。本检查点的校验PASS仅表示来源和恢复字节一致。音乐黄金差异、主机与当前FPGA实体兼容缺口仍未关闭。
