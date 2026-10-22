# 乐器配置与独立包络 · 2026-10-17

当前为隔离接合原型，**部分实现**；配置编译、独立包络和记录的配置到PCM数字链在限定范围**已验证**，无新板验/串口应用。当前仅有Nano20K与喇叭，不依赖屏幕或实体触控。原引擎/GUI/71/72/73交付与历史快照保留。

在72号副本中扩展每槽16分量为88位，增加逐分量独立起音、释音和A/D/R时间分频。包络元数据随泛音参数一起进入待生效/当前存储，旧音/尾音保留自己的参数；四槽提交及最多双层原型沿用旧行为。旧音保持、逐层抢占等仍是可替换原型，未冻结最终音乐规则。

`host/instrument_config.py`是ca03现有schema1文件模型的只读来源副本；`host/config_adapter.py`可将已有草稿编译为硬件词，支持频谱add/replace、沿预设频率比、持续/击发/混合与ADSR。开启独立颤音/效果器或关闭干声会明确拒绝；未开启字段不冒充已应用。该CLI**只写本地文件，不打开串口、不保存到设备**；现有GUI及73号板级镜像未获得此能力。

```powershell
python experiments/instrument_config_20261017/host/config_adapter.py experiments/instrument_config_20261017/config-fast.json compiled.hex --report compiled-report.json

python experiments/instrument_config_20261017/check_host.py
python experiments/instrument_config_20261017/check_envelope.py
python experiments/instrument_config_20261017/check_phase_wrap.py
python experiments/instrument_config_20261017/check_music.py
python experiments/instrument_config_20261017/check_engine_compat.py
python experiments/instrument_config_20261017/check_enabled_compat.py
python experiments/instrument_config_20261017/check_faults.py
python experiments/instrument_config_20261017/run_synthesis.py
python notes/instrument-config-20261017/finalize.py
```

新样例统一为`config-*.json/hex`，历史兼容样例`sustain.hex/strike.hex`保留48位。原始同名碰撞与旧内部位宽比较的失败日志保留；不要用新88位样例覆盖旧48位数据。`faults/`是故意错误副本，普通sources()不会编入。

完整组合以`instrument_layer_probe`为综合入口，默认启用`INSTRUMENT_ENV=1`：20277Logic、11189寄存器、45BSRAM，余459Logic/1BSRAM。只有综合，没有真实引脚/PnR/时序或新硬件音频结果；不能外推整机容量。`tdm_top_owned`和`left_layer_music_probe`默认仍关闭新包络选项，显式启用后v0零扩展数据保持旧声音。

离散物理时间、固定释放阈值、相位分频精度及格式见[FORMAT.md](FORMAT.md)。长时包络通过分频延长，时间会量化，分频有相位等待；报告给出名义时间与抖动上界。释放时间按满幅到阈值估算，较低起始电平会提前结束，固定状态转移有额外采样开销；0ms也是最小采样级转换，不是严格零时延。

下一步是带能力识别/完整确认的主机传输和GUI应用，再做对应板级包装/PnR及实际试听。独立颤音/效果器、四层同时、设备断电保存、伴奏录放/曲谱和7英寸界面仍待接；完整配置不能标作全部完成，也不改写原GUI显示已应用。
