# FPGA 当前开发候选

本目录发布来自M1活跃源的可编辑检查点，确切输入及截止时间见`../../project/versions/engineering-sources-20261023.json`。106项RTL/表/约束输入，加构建脚本、测试、参考模型、力度旧表及黄金轨迹。`upstream-notes/`是原作者历史记录，用户决定与当前边界以仓库`project/DESIGN-CURRENT.md`为准。

`tdm_ship_owned`是16路旧pad包装，J10、84节点及完整实体编辑/录放未接成完整产品；`rtl/joint_timing_top`是结构探针。两者均不能因名字或路由完成而获得下载授权。不要改写旧`src/rtl`或使用它的构建命令来验证本候选。

`tdm_ship_owned` 的 v1 码流使用说明见[91号文档](../../docs/02-技术方案/91-产品规格与使用规则-v1-20261024.md)：引脚表、引导序列、UART 寄存器协议、烧录步骤与 Verify Failed 判据、五栏验收。**该文档给出烧录指引，与本文上一句「未获下载授权」需由治理层对齐，在授权明确前按未授权处理。** 另注意其标题含「产品规格」，实际定位是 v1 码流说明；产品规格以 `project/PRODUCT-SPEC.md`（R01–R12）为准。

载板「J6 pin → FPGA pin」这一层从未验证，且 csv 中 15–20 与官方 LED 定义冲突，详见[引脚映射核对](../../hardware/current/context/pin-map-audit-20261024.md)。v1 是 16 电极直连，载板是 6 路 SENSE + 扫描链，两套 RTL 不通用。

从仓库根目录执行：

```powershell
python tools/scripts/engineering.py check
python tools/scripts/engineering.py test --area fpga --output D:/FPGA-Project/review/my-fpga-run
```

输出目录必须不存在。工具导出所有输入并校验解压黄金轨迹，运行力度表一致性、七项专项仿真、三组历史音乐逐字节对照和音高参考/故障反例。测试结果只覆盖实际运行配置，不继承原作者PASS。

依赖Python 3.8+、Icarus Verilog及vvp；通过`FPGA_IVERILOG`、`FPGA_VVP`指定可执行文件，统一入口也会查询PATH。完整PnR在导出目录运行`python build_product.py build_my_run full 1`，通过`FPGA_GOWIN_GW_SH`指定Gowin 1.9.11.03 Education的gw_sh。需要检查实际时序报告；生成码流不等于时序通过。所有操作只在自己的新导出目录运行。

黄金轨迹以`.tsv.gz`存储，导出时恢复原路径；不要直接在本目录运行旧检查脚本。`prepare*.py`、`seal_delivery.py`及原始审计脚本保留追溯用途，未作为本次支持入口。板测/串口脚本须另获实际硬件操作授权。

维护者：本轮管理会话负责发布输入和接手工具；原独立FPGA会话ID尚未确认。后续功能任务认领本仓库的隔离分支和路径，不能直接接管原D盘工作区。变更后更新输入清单、测试记录和producer远程提交，经PR交回。
