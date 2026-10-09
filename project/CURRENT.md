# 当前项目入口

本次整理遵循：保留最新已验代码，向前接合；不通过回退旧版本制造“闭环”。

| 要确认的事实 | 唯一入口 |
|---|---|
| 最新设计、全部已有能力、未实现项与待决参数 | [design.md](design.md)，2026-10-10总册，固定 N-01～N-11 |
| 产品候选及模块落点 | [state.json](state.json) 与 [catalog.json](catalog.json) |
| 来源工作树、保留方式、接合与风险 | [integration.md](integration.md) |
| 当前源码身份 | [integration-20261010-04.json](versions/integration-20261010-04.json)，主机串口配置顺序与失败清理修复，正在验证 |
| 本版实测及证据边界 | [validation.md](validation.md) |
| 开发板诊断身份与结果 | [board-observation.json](board-observation.json)，与产品候选分开 |

整合开发分支为 **`codex/project-version-closure`**。底座为 `a61b/7ca52c9` 的四源队列与逐指接口，
接合 `6e70` 的GUI/配置、协议v1.1、I²C模块与判据，并接入诊断发现的活动声部复位修复。
原main/fe326ad是历史起点；未接合工作树是来源，不是另一个“当前正式实现”。

本版是可继续开发的产品候选，真实触控、完整右手行为、三种发声方式和模拟音频板验仍有缺口。
版本归一不等于产品功能全部完成。

```powershell
python tools/scripts/project_version.py check project/versions/integration-20261010-04.json
python tools/scripts/closure_check.py
python tools/scripts/regress_all.py --full
```

闭环路径：设计ID → 实现提交/完整源清单 → 本版判据 → 构建配置/码流指纹 → 板级输入与结果 → 状态更新。
每步只确认它实际覆盖的行为。没有证据的阶段保留“待验证”，已有成果继续向前使用。

旧34/35号规格、记忆和架构图用于追溯。发生冲突先看本入口和可追溯用户决定，再核对实际源码。

主目录接合按用户选择暂缓。2026-10-10用户已授权本分支上板测试与模拟多指：先验证，不打断其他活跃板测。
20261009-06已验底座保留；01/02板测失败保留。当前04完整源226输入，全回归56/56、新PnR、SRAM下载、内部数字板测15/15均退出0，传输逐字节稳定性追加验证中。实体触控/DAC与最新未实现音乐语义仍挂账。03中止快照保留。状态以state为准。
本轮测试见[board-test-20261010.md](board-test-20261010.md)，旧55/55与产品PnR不直接签收新增配置。
