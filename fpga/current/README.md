# FPGA 当前开发候选

本目录发布来自M1活跃源的可编辑检查点，确切输入及截止时间见`../../project/versions/engineering-sources-20261023.json`。106项RTL/表/约束输入，加构建脚本、测试、参考模型、力度旧表及黄金轨迹。`upstream-notes/`是原作者历史记录，用户决定与当前边界以仓库`project/DESIGN-CURRENT.md`为准。

`tdm_ship_owned`是16路旧pad包装，J10、84节点及完整实体编辑/录放未接成完整产品；`rtl/joint_timing_top`是结构探针。两者均不能因名字或路由完成而获得下载授权。不要改写旧`src/rtl`或使用它的构建命令来验证本候选。

从仓库根目录执行：

```powershell
python tools/scripts/engineering.py check
python tools/scripts/engineering.py test --area fpga --output D:/FPGA-Project/review/my-fpga-run
```

输出目录必须不存在。工具导出所有输入并校验解压黄金轨迹，运行力度表一致性、七项专项仿真、三组历史音乐逐字节对照和音高参考/故障反例。测试结果只覆盖实际运行配置，不继承原作者PASS。

依赖Python 3.8+、Icarus Verilog及vvp；通过`FPGA_IVERILOG`、`FPGA_VVP`指定可执行文件，统一入口也会查询PATH。完整PnR在导出目录运行`python build_product.py build_my_run full 1`，通过`FPGA_GOWIN_GW_SH`指定Gowin 1.9.11.03 Education的gw_sh。需要检查实际时序报告；生成码流不等于时序通过。所有操作只在自己的新导出目录运行。

黄金轨迹以`.tsv.gz`存储，导出时恢复原路径；不要直接在本目录运行旧检查脚本。`prepare*.py`、`seal_delivery.py`及原始审计脚本保留追溯用途，未作为本次支持入口。板测/串口脚本须另获实际硬件操作授权。

维护者：本轮管理会话负责发布输入和接手工具；原独立FPGA会话ID尚未确认。后续功能任务认领本仓库的隔离分支和路径，不能直接接管原D盘工作区。变更后更新输入清单、测试记录和producer远程提交，经PR交回。
