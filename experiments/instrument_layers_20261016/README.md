# 运行时音色槽与双层音频原型 · 2026-10-16

当前状态：**部分实现**。最新入口见 [project/CURRENT.md](project/CURRENT.md)，详细边界与资源见主目录70号报告。此目录不会替换旧产品或GUI，不含可下载的整机码流。

沿69号的真实扫描/音乐链，增加四槽16分量运行时表、完整暂存提交、每次起音的独立预设、最多双层的实例展开，以及一指多声部滑音。配置已装入声部后由引擎独立保存，后续槽发布不会修改该声部；这只是“新音使用新配置”的可替换原型策略。

低层槽格式是 `slot_format.py` 定义的 v0：频率比Q8、幅度、延音Q15、指数衰减m/k。**不等于完整GUI配置格式**：起音/释音、颤音和效果器尚共用，未接非易失存储或串口新协议；sustain/strike样例只是验证数字链路，不是最终钢琴/小提琴音色。

```powershell
python experiments/instrument_layers_20261016/check_derivations.py
python experiments/instrument_layers_20261016/run_validation.py
python experiments/instrument_layers_20261016/check_memory_opt.py
python experiments/instrument_layers_20261016/run_synthesis.py synthesis_selected
python notes/instrument-layers-20261016/finalize.py
```

Icarus与Gowin路径沿用本机配置。仿真在`engine/`读取原查表和根目录样例。综合仅运行`run syn`，无CST/SDC/PnR/下载。

构建选择：原引擎目录中的`pitch_mod.v`不用，改选`optimization/pitch_mod.v`；分配器使用`optimization/note_map_owned.v`；多绑定修改明确放在本目录的`engine/finger_pitch.v`。`reference/layer_dispatch.v`保留未优化版本。历史失败综合均保留各自源副本与输入指纹，不能拿旧源的资源数字冒充当前版本。

运行时表逻辑接口：`cfg_valid/ready`握手；`cfg_commit=0`向槽的非活动银行写一分量；`cfg_commit=1`在16分量全部写过后发布并发出`cfg_applied`，不完整提交或保留位非法发出`cfg_error`。提交和音符接受串行，不会读到半份配置。失败提交保留暂存内容。没有读取、取消草稿、传输校验或设备断电保留的成品协议。

`layer_selection`是四槽位掩码，目前只接受一或两位；其他掩码显式失败，不静默丢层。桥保留父实例直到真实松手，每层使用`{父实例,槽号}`作为15位子身份。松手依据起音时保存的掩码；抢占的子声部不接受旧移动或旧OFF，另一个子声部仍可滑音。选择变更、原子抢占整键、在奏编辑和声音平衡的最终音乐规则继续讨论，不由这个原型裁定。
