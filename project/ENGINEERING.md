# 当前工程与开发入口

**2026-10-25 PCB接续候选**：最新951原生施工检查点及完整恢复链见`hardware/checkpoints/pcb-951ce88a-20261025/`，计划见`project/PCB-RESOLUTION-PLAN-20261025.md`；原hardware/current的e098保留历史。此任务分支未合入main，未新增CAD/DRC/实物验收。用户已授权向当前Public internal直接同步，覆盖旧private-only推送条件。

本批为[2026-10-24协作检查点](COLLABORATION-CHECKPOINT-20261024.md)。输入完整性可复核；FPGA音乐黄金对照仍有差异，硬件未完成布线，主机与当前FPGA协议兼容未实体验证。使用任务分支审阅和改进，不视为成品。

| 领域 | 克隆后可读可编辑的目录 | 本次边界 |
|---|---|---|
| FPGA | `fpga/current/` | M1当前源、表、约束、脚本、测试和压缩黄金数据；受限包装与结构探针明确分开 |
| 硬件 | `hardware/current/` | 当前保存原生工程、施工证据、接口和采购上下文；未放行制造 |
| 上位机 | `host/current/` | ca03 11版源码/字体/离线测试；与当前FPGA的实体兼容尚未验证 |

旧`src/rtl`、`src/gowin`、`tools/host`保留历史可复现性，不能作为新任务的默认入口。历史实验、v1/v2恢复包不覆盖本次工程检查点。具体来源、逐文件哈希和捕获时间见`versions/engineering-sources-20261023.json`；补充的主机测试依赖和一处RTL声明顺序适配均有单独来源记录，未改原owner目录。

从用户授权的internal仓库实际main读取本页及DESIGN-CURRENT，再执行：

```powershell
python tools/scripts/project_control.py check --remote --fresh-entry
python tools/scripts/engineering.py check
python tools/scripts/design_governance.py status --remote --live
```

外部电脑无法读取原生产目录时，live会明确报告不可见。可依据本次发布检查点进行限定任务，但不能宣称未观察的生产目录已同步。当前设计决定、产品完成度、已发布输入完整性、活跃源漂移及测试结果分别判断。

`engineering.py export --area fpga|hardware|host --output <新目录>`恢复所选候选，验证所有字节并解压黄金数据；拒绝覆盖已有目录。`engineering.py test --area fpga|host --output <新目录>`增加实际隔离回归。每次使用不同输出目录，日志和SOURCE-ORIGIN.json绑定源清单。

FPGA回归需要Python、Icarus Verilog和vvp；可设置`FPGA_IVERILOG`和`FPGA_VVP`。上位机离线回归依赖见`../tools/requirements-engineering-host.txt`，在独立虚拟环境安装后执行。硬件export核对保存工程的字节身份，不启动CAD，也不重新证明DRC。

本轮管理owner负责发布检查点及工具，不接管原owner工作区。新协作者在命名任务分支中认领一个领域，修改对应current目录；同一领域多个任务须划定文件边界。收工交回源清单、实际远程commit、相应验证和未验证项。当前输入变化应重新登记与验证，禁止仅更新哈希来掩盖未审阅改动。
