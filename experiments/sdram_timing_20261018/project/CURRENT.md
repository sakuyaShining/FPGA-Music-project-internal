# 当前SDRAM时序/板验实验 · 81

版本sdram-timing-20261018-v0。完整产品部分实现，报告../../../docs/02-技术方案/81-SDRAM时序排查与板级读写验证-2026-10-18.md

- 先备份109项，修复前再备份194项；原80号/音乐引擎/GUI/快照保持。
- 注册命令引脚/1:1 PLL、声明I/O包络PnR和反例：限定范围已验证。
- 正常setup/hold +5.704/+0.225ns；加严+4.204/+0.037ns，确切die/封装延迟/原始PLL输入警告仍待验证。
- 实体8MiB两图案、两次配置重测共33554432半字操作无错；当前室温/供电，不替代长期/温压/示波器资格。
- 已恢复76号音乐配置固件，身份/512拍/2048零PCM已验证；GUI仍../envelope_resources_20261017/launch_gui.cmd。
- 无Flash或TF访问。无新物理S2/模拟音质结论；SDRAM不能断电保留。
- FIFO环形调度、TF/文件/非易失/最终混音待实现；完整音乐＋新控制器资源/PnR待验证。
- check_hardware_evidence.py只离线审计。notes中的bench_hardware.py实际下载后恢复，勿混入普通回归。
- verify_delivery.py仅身份核验；不得据PASS宣布完整产品完成。
