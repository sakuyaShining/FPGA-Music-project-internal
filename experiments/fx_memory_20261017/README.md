# 当前源码入口 · 效果器单读口77

版本fx-memory-20261017-v0，整体部分实现。数字优化/回归/综合已验证，新RAM实体路径已实现待验证。

- 报告：../../docs/02-技术方案/77-效果器单读口与存储资源账-2026-10-17.md
- 联合综合：20635Logic/11592寄存器/28BSRAM，剩101Logic/18BSRAM；只换fx_delay，原功能/调度逐拍保留。
- 已验：两轮60万拍FX旧参考、错位反例、core/serial回归；新板级包装仿真及内部PnR通过，尚未下载。
- 板上和GUI继续使用76号；此目录package/仅继承76号旧包，不能当77号新码流。
- 新候选码流在build_board_memory/impl/pnr/board_config.fs；无新串口/Flash/介质访问或采购。
- 资源账：evidence/memory-inventory.json与memory-owners.csv；预算方案不等于已实现存储。
- 原效果器调度与时间注释不符/启动未知另列，保持现状的PASS不表示音乐时间目标完成。
- 验证命令见check_fx.py、check_stage.py core/serial、check_board.py及nominal；交付身份用verify_stage77.py。
- 下一步：RAM换逻辑余量，再推进非易失与TF/SDRAM伴奏录放。存储/四层/独立效果/实体显示触控等缺口保持。
