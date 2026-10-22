# 当前存储实验 · PCM双向缓冲79

版本pcm-buffer-20261018-v0，音乐引擎沿用78号，录放整体部分实现。
报告：../../../docs/02-技术方案/79-录放双向缓冲与停顿边界验证-2026-10-18.md

- 两路1024×16FIFO/错误保护：限定数字测试与联合综合已验证，无PnR/板验。
- 联合20082Logic/31BSRAM，余654Logic/15BSRAM。
- 新增缓冲不是SDRAM/TF控制器、文件保存或混音；这些仍待实现。
- 无下载/COM/Flash/介质访问，板上仍76号，GUI继续../envelope_resources_20261017/launch_gui.cmd。
- 验证check_fifo.py、check_buffers.py；身份verify_delivery.py。冻结引擎在engine/，原78号不修改。
- 下一步SDRAM控制与缓冲调度、后端会话隔离/资源验证，再接TF、非易失、录放/事件轨。
