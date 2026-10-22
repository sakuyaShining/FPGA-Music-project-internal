# 联合探针资源调整 · 86

版本joint-probe-resources-20261019-v0；整机部分实现；报告../../../docs/02-技术方案/86-联合探针资源调整与布线失败边界-2026-10-19.md

- 85号引擎88文件/全部约束保持，仅替换探针输入历史为9个DSP寄存器与96拍RAM延迟。
- 普通寄存器11243→10760；综合20164Logic/32BSRAM，失败PnR20478Logic/10357CLS/22.75DSP。
- 10万拍全位历史对照、DSP/延迟故障反例及两延迟联合PCM回归通过；旧引擎回归继承身份，未重跑。
- 布局通过、路由FAIL，无有效联合时序、无新码流；加严构建未运行。0 unrouted不是PASS。
- v0/v1/v2路由失败、v3错误目标主动中止、v4最终路由失败，所有输入和日志保留。
- 结构扫描没有有效音乐命令协议，外部静音，禁止下载，bench_gate=false。
- 本轮COM6不存在、串口清单空，当前板状态未核实；最后成功确认76号，无下载/发音/Flash/TF操作。
- 当前源码已实现待验证，不是产品签收；下一步定位局部资源/路由与真实命令包装，保持音乐功能。
- 最终混音/TF文件/非易失/实体显示触控仍待实现或待验证，不据此确定双板/取消功能。
- 输出在D盘联接；证据/身份审计PASS不是路由/时序通过。

实际回归：check_scan_store.py、check_joint.py；资源账：resource_map.py。
审计：audit_candidate.py build_nominal_v4、audit_timing.py、audit_history.py、verify_delivery.py。
保留的check_*_variant.py和reference/probe_scan_store_*为中途候选历史，不是最终源码资格证明。
