# 当前项目入口

**用户硬约束：触控、发声与独立实体可视化由Tang Nano20K FPGA承担，不使用其他MCU。2026-10-11用户明确允许连接电脑时由上位机计算音乐可视化，实体功能仍保留。** 计算资源逐项审计见[compute-resource-audit-20261010.md](compute-resource-audit-20261010.md)，电脑参考/FFT绘图与板载BL616单独列明；全FPGA触控和实体三视图尚未实现。

本次整理遵循：保留最新已验代码，向前接合；不通过回退旧版本制造“闭环”。

| 要确认的事实 | 唯一入口 |
|---|---|
| 最新设计、全部已有能力、未实现项与待决参数 | [design.md](design.md)，固定N-01～N-11，新增N-12音频可视化 |
| 产品候选及模块落点 | [state.json](state.json) 与 [catalog.json](catalog.json) |
| 来源工作树、保留方式、接合与风险 | [integration.md](integration.md) |
| 当前源码身份 | [integration-20261011-07.json](versions/integration-20261011-07.json)，241输入，松键连续性修复；512槽专项、新PnR、SRAM、30秒实时与6种释放板测通过；全量原57/58加环境身份补验通过，原退出1保留 |
| 本版实测及证据边界 | [validation.md](validation.md) |
| 松键尖峰修复 | [release-spike-20261011.md](release-spike-20261011.md)：07已下载SRAM并通过6种真实PCM释放验证，可见GUI已恢复COM6实时观察 |
| 全局演奏工作台方案 | [desktop-workbench-design-20261011.md](desktop-workbench-design-20261011.md)：常驻键盘/三视图、明确音色应用、参数与真实音频验证；方案已整理，尚未实施 |
| 触控前端决策与双形态比较 | [touch-decision-20261010.md](touch-decision-20261010.md)，用户确定全FPGA扫描/坐标/追踪，不用采集MCU，PSoC退出采购，原始测量前端待评估 |
| 当前采购与已在手设备 | [24号采购主清单](../docs/02-技术方案/24-采购清单.md)，2026-10-10按最新决策与用户库存同步；微信版同步 |
| 外部音频输出方案 | [audio-output-plan-20261010.md](audio-output-plan-20261010.md)，推荐3.5mm LINE OUT＋I²S线路DAC，内置喇叭可选；新增硬件尚未验 |
| 音乐可视化设计 | [audio-visualization-design-20261010.md](audio-visualization-design-20261010.md)，[gui-audio-20261011.md](gui-audio-20261011.md)，GUI真实波形页已接入/验证；FPGA轨迹与频谱尚未实现 |
| 三视图架构及性能指标 | [music-visualization-metrics-20261010.md](music-visualization-metrics-20261010.md)，21项指标、计算边界与候选比较；建议阈值未冻结，架构尚未证明最优 |
| 整机IO与PCB/底板分工 | [io-architecture-20261010.md](io-architecture-20261010.md)，Nano＋载板＋电极板为推荐分工，新前端/显示/引脚尚未冻结 |
| 原型、PCB、组装与提交排期 | [delivery-plan-20261010.md](delivery-plan-20261010.md)，官方11月4日18:00；内部10月31日提交目标，交期未确认 |
| 到货实验卡、接线检查和记录模板 | [prototype/README.md](prototype/README.md)，双形态实测准备完成，尚未执行 |
| 开发板/芯片要求与换板核对 | [board-requirements-20261010.md](board-requirements-20261010.md)，历史Primer20K比较保留；最新决定固定Nano20K，不以换板增加算力 |
| T60、旧LFO、时钟告警的具体含义 | [open-issues-explained-20261010.md](open-issues-explained-20261010.md) |
| 开发板诊断身份与结果 | [board-observation.json](board-observation.json)，与产品候选分开 |

整合开发分支为 **`codex/project-version-closure`**。底座为 `a61b/7ca52c9` 的四源队列与逐指接口，
接合 `6e70` 的GUI/配置、协议v1.1、I²C模块与判据，并接入诊断发现的活动声部复位修复。
原main/fe326ad是历史起点；未接合工作树是来源，不是另一个“当前正式实现”。

本版是可继续开发的产品候选，真实触控、完整右手行为、三种发声方式和模拟音频板验仍有缺口。
版本归一不等于产品功能全部完成。

```powershell
python tools/scripts/project_version.py check project/versions/integration-20261011-07.json
python tools/scripts/closure_check.py
python tools/scripts/regress_all.py --full
```

闭环路径：设计ID → 实现提交/完整源清单 → 本版判据 → 构建配置/码流指纹 → 板级输入与结果 → 状态更新。
每步只确认它实际覆盖的行为。没有证据的阶段保留“待验证”，已有成果继续向前使用。

旧34/35号规格、记忆和架构图用于追溯。发生冲突先看本入口和可追溯用户决定，再核对实际源码。

主目录接合按用户选择暂缓。2026-10-10用户已授权本分支上板测试与模拟多指：先验证，不打断其他活跃板测。
20261009-06已验底座保留；01/02板测失败和03中止快照保留。当前04完整源226输入，全回归56/56、新PnR、SRAM下载、内部数字板测15/15、100/100完整流逐字节一致均退出0；实际主机capture与2048样本RAM索引读一致，无重试。板上构建[board-build-20261010-04.json](versions/board-build-20261010-04.json)，最终交付记录[evidence/full32-hostfix04-20261010/delivery.json](evidence/full32-hostfix04-20261010/delivery.json)。实体触控/DAC/10ms与未实现音乐语义仍挂账。
本轮测试见[board-test-20261010.md](board-test-20261010.md)，旧55/55与产品PnR不直接签收新增配置。

2026-10-11上位机波形更新：本版228输入，37主机测试/GUI自测/真实COM6后台采样通过。RTL及构建脚本与04相同；未重新PnR/下载，旧04码流和全量证据不升级为新GUI版全量签收。电脑FFT调试模式尚未批准。

2026-10-11演奏工作区：见[performance-workspace-20261011.md](performance-workspace-20261011.md)。39主机测试和真实COM6双音演奏/采样期间释放通过；无新RTL/PnR/下载，FPGA轨迹/频谱仍未实现。

2026-10-11连接问题：实窗原为模拟后端，虽端口下拉已改COM6；现已切换真实COM6并连续采集。03修复连接时锁定端口，40主机测试通过，保护在下次GUI启动生效；保留当前已连的02窗口供用户演奏。

2026-10-11用户重新上电并报告波形仍不可见：当前板上配置未知，之前连接成功不视为本次问题闭环。原04码流/日志指纹复核一致；本轮未下载。见[重新下载流程与键盘演奏方案](reload-and-keyboard-plan-20261011.md)，键盘新增设计为建议，尚未实施。

2026-10-11重新上电恢复实测：完整04源隔离副本check-build通过，当前GUI03源228检查通过；原04码流SRAM重载exit0，COM6身份D3/rev2/proto11/scope32。A4产生2048非零样本、释放后active0；用户实际GUI采样并显示波形成功，显示倍率4，测试音已释放，保留最近快照。证据[evidence/reload-test-20261011/record.json](evidence/reload-test-20261011/record.json)。本轮未改产品源码；短音漏过周期采样/实体DAC仍未闭环。

2026-10-11 N-12实现审查：用户要求实时演奏中观察三视图。当前只有1Hz、约39ms的有限快照，轨迹与FPGA频谱未实现，不能按采样成功签收实时可视化。详见[代码与算法审查](visualization-implementation-audit-20261011.md)。本轮未改实现或占用串口。

2026-10-11 N-12新决定：电脑连接模式可用PC对真实FPGA音频计算波形/频谱并处理轨迹；不取消实体FPGA实现。见[电脑实时可视化架构](desktop-live-visualization-20261011.md)。此前PC FFT未批准的条目为历史状态，现被本次明确授权覆盖。持续数据通路尚未实现，现有快照不签收新目标。

2026-10-11实时三视图实现：连续原采样率PCM16、FPGA接受事件、PC FFT及固定演奏区已接入候选，详见[实现与验收](desktop-live-implementation-20261011.md)。尚未签收新码流与板级结果，不能将界面已写当完成。
