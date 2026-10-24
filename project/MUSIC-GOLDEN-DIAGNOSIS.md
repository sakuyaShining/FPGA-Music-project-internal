# 音乐黄金差异诊断

## 后续：明确配置的回归入口

`python tools/scripts/music_profiles.py --profile all --fault-checks --output <不存在的新目录>`已经在全新导出attempt03执行：历史profile的compat/layers/sensor全轨迹匹配旧黄金；当前profile保持0x6E=0x80/vscale=256，三组功能探针通过，其中分层的7次快照/112个分量幅度由独立Python整数参考核验。旧默认测试及旧黄金不覆盖、不改写。

篡改参考值、测试台关闭力度、负向副本把力度ROM槽号地址绑0，均在指定幅度判据触发失败，反例检出成功。最后一项只修改隔离负向导出的vel_shape地址，变异前后哈希明确登记；仓库产品源不改。

attempt01声明顺序elaboration失败、attempt02端口force先触发无关包络断言均保留，不计为幅度反例检出。最终证据由governance当前review指向。上述通过不等于四层并奏、共享尾音优先分配、独立完整PCM参考、实体编辑/录放或产品听感已验收；当前仅是现有最多两层探针的明确profile验证。

输入为341项工程检查点中的FPGA候选，源提交374a84d；本轮不改产品RTL、参数表、原黄金或原owner工作区。所有编译/仿真在新导出目录执行。

## 实验与实际结果

| 测试 | 当前默认配置，原测试台 | 仅在测试台切为历史vscale=0的对照 |
|---|---|---|
| compat | 第6662拍PCM从黄金0009e0变为000890；56495行不同 | 完整逐字节匹配黄金 |
| layers | 原测试台在独立自定义频谱幅度断言失败，轨迹未完成 | 完整逐字节匹配黄金，原断言通过 |
| sensor | 第58885拍PCM从001280变为001020；22714行不同 | 完整逐字节匹配黄金 |

对照在首个音符之前的第4000个下降沿先报告寄存器/派生值，再force测试台中的vel_vscale为0；报告显示原r_vel_sens=0x80、原vscale=256。仅生成的三个测试台有差异，产品RTL和数据表不变。对照不是通过UART测试正式接口，也不是关闭产品功能的补丁。

## 结论与限制

1. 在这些完整轨迹覆盖范围内，历史黄金差异可由力度灵敏度配置变化解释：当前默认0x6E=0x80使vscale=256，历史等价配置是vscale=0。三组匹配均检查原黄金哈希，不重新生成或替换黄金。
2. 这不是证明当前默认的音乐行为错误；也不是证明任何新默认已被用户接受。旧测试的固定幅度断言依赖旧配置，不能把它直接当作新默认的产品验收判据。
3. 当前默认测试的差异/失败继续保留。后续应把“旧行为兼容”和“新默认独立参考/产品要求”分成两个明确profile，各自绑定配置、源和结果；不能用force-off对照给新默认签绿。
4. 尚未对新默认建立完整独立参考、功能故障反例、PnR/STA或实体听感签收；四层/曲谱并奏/FIFO抢占/实体编辑等完整产品功能也未因本实验完成。

## 证据与复现

审阅与脚本/日志/来源清单见`reviews/20261024-music-golden-diagnosis/`。在仓库根执行，输出须为两个不存在的新目录：

```powershell
python tools/scripts/engineering.py export --area fpga --output <native新目录>
python project/reviews/20261024-music-golden-diagnosis/scripts/diagnose_music_golden.py --root <native新目录>
python tools/scripts/engineering.py export --area fpga --output <control新目录>
python project/reviews/20261024-music-golden-diagnosis/scripts/diagnose_velocity_profile.py --root <control新目录>
```

脚本会保留逐项比较/错误后继续下一项，results.json是权威结果；脚本成功结束只表示诊断流程完成，不等于所有测试通过。本地完整轨迹另保存在D盘review的music-golden-20261024-01和music-golden-20261024-legacy-vscale-01；公开交接保留其哈希、输入及复现脚本，不把未上传的轨迹声称为仓库文件。
