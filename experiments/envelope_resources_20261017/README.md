# 当前入口 · 包络共享资源优化与配置板验76

版本envelope-resources-20261017-v0；限定优化/配置数字板验已验证，整机部分实现。

- 完整报告：../../docs/02-技术方案/76-包络共享资源优化与配置板验-2026-10-17.md
- 联合综合：20537Logic/11428寄存器/46BSRAM，仅余199Logic且无BSRAM余量，无整机PnR。
- 板级诊断：10495Logic/39BSRAM/14IO，内部setup+8.486ns、hold+0.074ns；SRAM实际下载，COM6/B配置能力75/1，当前活动0和零PCM。
- 使用上一层launch_gui.cmd启动隔离GUI；当前板上是配置诊断，旧73六用例命令不适用，原GUI/exe不覆盖。
- 配置仍仅通电有效；保存文件只写电脑。独立颤音/效果器、四层、录放/曲谱、实体显示/触控尚未完整接合。
- 验证：check_shared.py，check_stage.py core/serial/gui，check_board.py及nominal；均从仓库根加实验目录路径运行。
- synthesis_reference与synthesis_shared为公平资源对照；build_board为14脚诊断PnR，不混算资源。
- package/config-sram.fs为新镜像；两个rollback-*.fs保留原诊断/静音回退，均仅SRAM操作。
- 实际硬件记录见notes/envelope-resources-20261017/latest-hardware.txt；交付身份使用verify_delivery.py。

本轮没有新的物理S2按键实测或模拟音质结论。下一步缓存/存储资源账、非易失与伴奏录放；保持用户音乐规则边界。
