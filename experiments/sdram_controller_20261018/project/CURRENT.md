# 当前存储控制实验 · SDRAM80

版本sdram-controller-20261018-v0，整体部分实现。报告：../../../docs/02-技术方案/80-SDRAM单事务控制与时序模型验证-2026-10-18.md

- SDRAM单事务控制/模型：记载范围已验证，真实时序/引脚/时钟/PnR/板验待验证或待实现。
- 联合20114Logic/31BSRAM，余622Logic/15BSRAM。
- FIFO到SDRAM环形区/仲裁尚未接入；TF/文件/非易失/最终混音仍待实现。
- 原音乐/双FIFO源码保持79号；本轮没有重跑其全部既有回归。
- 未下载/开COM/访问Flash或介质，板上仍76号，GUI用../envelope_resources_20261017/launch_gui.cmd。
- 此目录没有合格板级镜像。测试check_sdram.py，身份verify_delivery.py。
