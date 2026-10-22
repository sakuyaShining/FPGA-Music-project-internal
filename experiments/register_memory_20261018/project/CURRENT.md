# 当前源码入口 · 参数回读RAM78

版本register-memory-20261018-v0，整机部分实现。报告：../../../docs/02-技术方案/78-参数回读RAM与逻辑余量恢复-2026-10-18.md

- 完整联合综合19765Logic/10844寄存器/29BSRAM，余971Logic/17BSRAM；比77减少870Logic，新增1BSRAM。
- 15万拍参数旧参考、5万拍回读时序/反例，core/serial、板级包装两模式及诊断内部PnR通过；新RAM实体路径已实现待验证。
- 当前板上仍76号，未开COM/下载/访问存储介质或Flash；设备GUI使用../envelope_resources_20261017/launch_gui.cmd。
- 新候选build_board_register/impl/pnr/board_config.fs未部署；包装C2仍76，必须按哈希区分。package/仅继承76旧包。
- 新身份入口verify_stage78.py。旧verifier/报告只用于历史，不以当前更新文档重写旧快照。
- 下一步存储控制与缓冲的模型/资源验证，然后非易失、TF与伴奏录放；这些功能仍待实现，音乐规则不变。
