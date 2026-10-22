# 资源优化与逐拍回归 · 2026-10-16

整机仍**部分实现**。本轮仅改变内部存储/查询组织；最新状态见[project/CURRENT.md](project/CURRENT.md)，设计与完整验证边界见主目录71号报告。原70号、原引擎和GUI均保留。

默认构建选择`all`：

- `selected/finger_pitch.v`：同一手指的锚点共享，逐组所有权、偏移和松手尾音保持。依据是一个已绑定手指的所有组具有相同锚点；单绑定、多绑定和非2幂触点数分别对照。
- `selected/note_map_owned.v`：提前一拍读取实例身份，利用原有分配阶段，不增加事件接受/完成或装载周期。复位清有效/所有权标志，未使用的存储内容不再逐项复位。
- `selected/left_contact_bridge.v`：将世代、音符、位置和坏帧计数合成一条触点记录，IDLE/NEXT预取，复位有效位屏蔽旧内容；同地址写转发保留SCAN到MOVE等相邻更新。

原文件分别位于`engine/`、`optimization/`、`rtl/`，不会被默认构建重复编译；`reference/`只重命名模块用于双实例比较。`fault_injection/`只含故意破坏的测试副本，不进入产品或资源探针。

```powershell
python experiments/resource_safety_20261016/check_derivations.py
python experiments/resource_safety_20261016/run_units.py
python experiments/resource_safety_20261016/run_bridge_equiv.py
python experiments/resource_safety_20261016/check_fault_detection.py
python experiments/resource_safety_20261016/run_music_equiv.py
python experiments/resource_safety_20261016/run_synthesis.py all
python experiments/resource_safety_20261016/run_synthesis.py reference
python notes/resource-safety-20261016/finalize.py
```

本机Icarus/Gowin路径沿用70号。`run_music_equiv.py`分别运行参考/选定实现，逐字节比较每拍记录：PCM有效样本、每个I²S拍、分配/音符反馈及逐组表情输出，含启动未知值；`evidence/*.tsv`不是只比较摘要。不要并行启动两份该脚本，它们使用相同参考轨迹文件。

保留参数分支`both`供本轮两项优化的中间资源对比，最终选定为`all`。历史较早的`music-equivalence.json`为中间记录，其运行脚本后来扩展，不作为最终来源门禁；最终门禁明确使用`music-equivalence-all.json`与本轮三个单元/故障记录。所有当前门禁逐项验证输入SHA256。

最终`all`的综合输出目录为`synthesis_all_clean/`；先前`synthesis_all/`保留地址截断告警修正前的中间源副本。修正后重新回归，旧报告不冒充当前源码报告。

综合只执行`run syn`，逻辑顶层仍`instrument_layer_probe`，没有真实IO约束/SDC/PnR、下载或采购。完整配置/非易失保存/录放/7英寸界面继续待接，不能把优化后的余量称为全产品容量保证。
