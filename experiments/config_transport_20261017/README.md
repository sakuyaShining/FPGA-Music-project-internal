# 配置接合实验75 · 当前入口

版本：config-transport-20261017-v0；整体部分实现，联合综合失败，尚无可上板码流。

- 实现/范围/实际验证：[75号报告](../../docs/02-技术方案/75-配置可靠传输与GUI接合验证-2026-10-17.md)。
- 当前源码：src/、rtl/、host/、gui/；源GUI启动为上一层launch_gui.cmd。原发行exe和原工程保持。
- 新协议能力：75/1，当前板载72号码流不能上传。GUI离线可查看，不可当作本轮板验。
- 最终检查：python experiments/config_transport_20261017/check_stage.py serial（或core/gui），从仓库根运行。
- 资源：python experiments/config_transport_20261017/run_synthesis.py 新目录名；当前selected20767Logic/20736失败。失败目录保持原貌。
- 交付身份：python experiments/config_transport_20261017/check_delivery.py；只核验记载文件身份，不替代功能检查。
- 下一步：有逐拍/故障回归的联合资源优化，然后对应板级包装、PnR和SRAM试听；非易失、录放等仍待实现。

原型保留旧音参数、新音用已发布数据。双入口资源与串口独占资源有区别，未替用户冻结实体编辑/分层/存储语义。
