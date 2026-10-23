# 2026-10-24 协作工程检查点

本检查点将三个领域的可编辑候选、依赖、输入清单和隔离验证入口放在同一仓库，供限定任务接手。它是源码交接检查点，完整产品仍未验收。发布状态以包含本页的实际远程提交和PR为准；任务分支不自动等于main。

## 从哪里开发

| 领域 | 当前目录 | 原来源 | 接手边界 |
|---|---|---|---|
| FPGA | `fpga/current/` | D盘M1候选，106项RTL/表/约束及测试/脚本/黄金数据 | 受限包装、结构探针、完整产品目标分开；历史音乐黄金回归有差异 |
| 硬件 | `hardware/current/` | 06df及保存U9ControlWork原生工程 | 当前保存PCB为e098c5db…，施工记录47项未连通/13网；未放行制造 |
| 主机 | `host/current/` | ca03，host-workbench-20261015-11 | 离线回归通过；与当前FPGA及实体载板的兼容性未验证 |

原始主要捕获时间：北京时间2026-10-23 23:35:23。清单保存在`versions/engineering-sources-20261023.json`；ID保留原捕获日期，补充依赖和适配分别记录。此后生产目录变化由独立观察报告，不自动进入本检查点。

## 实际验证及限制

结果和日志见`reviews/20261024-engineering-publication/validation/`及该目录review.json。

- 工程输入和导出校验覆盖三个领域，黄金数据解压后再核对哈希；不依赖原D盘才能读取候选。
- FPGA力度表校验、七项专项仿真、音高参考/故障反例按独立输出执行。历史音乐黄金回归未通过：首个compat轨迹第6662拍出现数值差异。不得替换黄金数据、跳过判据或把该结果称为全绿；其后layers/sensor轨迹未由原串行脚本执行。
- 导入的`tdm_top_owned.v`曾因`r_vel_sens`在过程使用之后声明而不能由Icarus完成elaboration。本检查点只把声明提前、保留同一连续赋值；新哈希与上游哈希均登记，原owner源码未改。该修改没有新PnR/STA/板验。
- 主机首次离线测试发现缺少`check_workbench_retrigger.py`，现已从同一ca03来源补齐并保留来源哈希，再执行全套离线测试。
- 硬件从保存原生源导出并核对字节；本轮未启动CAD或重跑DRC。37项保留版与47项施工版不混用，旧CPL/单面装配报价仍不适用于当前改位。
- 既有22个恢复检查点、18,277项输入、5,845个唯一Git blob已完整校验；这是历史保全完整性，不能签收新功能。

## 在新目录复现

从已发布检查点对应的提交或PR任务分支取得仓库，先执行：

```powershell
python tools/scripts/engineering.py check
python tools/scripts/engineering.py export --area hardware --output D:/FPGA-Project/review/my-hardware
python tools/scripts/engineering.py test --area fpga --output D:/FPGA-Project/review/my-fpga
```

FPGA测试需要Icarus Verilog及vvp；设置`FPGA_IVERILOG`、`FPGA_VVP`或放在PATH。返回非零的历史音乐对照是本检查点已知失败，必须保留并作为专项任务处理。

主机本轮实际使用Windows、Python3.8.6、PyQt5 5.15.11、Qt5 5.15.2、pyserial3.5和numpy1.24.4。独立环境安装依赖后复现：

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r tools/requirements-engineering-host.txt
.venv/Scripts/python.exe tools/scripts/engineering.py test --area host --output D:/FPGA-Project/review/my-host
```

输出目录必须不存在，测试只在导出副本运行；没有板卡、串口、下载或CAD操作。每次结果绑定SOURCE-ORIGIN.json的实际输入，不因manifest后来补充其他领域就继承或撤销本领域验证。

## 采购信息的适用范围

`fpga/current/upstream-notes/`保留WorkBuddy原文作来源证据，其中`JLCPCB-ORDER-PACKAGE`、`POST-PCB-BOM`和`AUX-SCREEN-PRODUCT-BOM`依据53件四滑条小样推断整板为空，不能代表当前整板。采购应先读`hardware/current/context/purchase-preparation-20261021-r1/current-board-procurement.json`，其227件、215SMT+12通孔、36料号绑定e098c5db…原生板；同目录旧README/CPL属于历史上下文，不能覆盖当前机器清单。目录未包含旧README所引用的外部工作簿，不声称其已交付。

屏幕SKU/CTP/线束、机械、工厂供料与双面装配报价仍未关闭。本检查点不认可旧文档的实时库存、整机总价或引脚重新分配。用户关于AUX、独立键与编辑模式的原话须与硬件及当前设计登记逐项接合；提案不能自动改电路。

## 可以分配的任务

1. FPGA：先定位compat音乐黄金差异，明确是允许的新行为还是回归；保持旧黄金，交回最小修复/判据依据及源身份。
2. 主机：基于11版梳理与当前FPGA寄存器、命令、音色配置的接口差异；离线测试通过不代替实体协议验收。
3. 硬件审阅：对保存副本核对当前网表/BOM/接口与采购文档；原施工owner继续写06df，不直接接管其会话或重放事务。
4. 显示与实体编辑：明确J10驱动、84节点MUX、EEPROM/TF和产品顶层的接口合同及验收条件，再实施接合。

每位协作者认领一个领域、命名任务分支和文件范围，通过私有内部仓库PR交回源码、测试与未验证项。历史v1/v2仍可复现；完整产品缺口、源码身份与持续施工的新变化分别判断。
