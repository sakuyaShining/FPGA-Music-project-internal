# 当前录放SDRAM数据搬运实验 · 82

版本sdram-stream-20261018-v0，完整产品部分实现。报告../../../docs/02-技术方案/82-录放缓冲与SDRAM环形调度接合-2026-10-18.md

- 101输入先备份，原音乐/GUI/双FIFO与旧交付保持；SDRAM控制器同81号。
- 新增两个256KiB默认环形区、四客户轮转、独立clear握手/在途清退，停止采入继续排空。
- 数字调度680016拍/6341clear，双后端整链/异常恢复与四个故障反例已验证。
- 正常工具结束的新联合综合20422Logic/31BSRAM，余314Logic/15BSRAM；无新PnR/板验。
- 回放为独立PCM逻辑输出，未接最终混音/DAC。TF/文件/事件轨/非易失/录放GUI命令仍待实现。
- 新调度实体路径已实现待验证；本轮未开COM/下载/访问Flash或TF，板上仍76号。
- 先做调度板验/联合时序及资源恢复，再接媒体和回放音频；旧81号时序不外推新顶层。
- check_arbiter.py/check_stream.py/check_fault_recovery.py为数字验证，verify_delivery.py只核身份。
- synthesis_buffered_final有interruption.json，不得因表面exit0作为合格构建；选定buffered_retry。
