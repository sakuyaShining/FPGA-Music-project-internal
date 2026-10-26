# 14路传感前端小板当前候选

这是原227件功能基线中一组前端的拆分候选。计划6组覆盖84电极，不是完整购物清单、现货模块或投产板。

- 28件/150引脚，127有连接、23有意NC。原生原理图严格DRC与全部150PAD网名独立核验通过。
- 当前55×45mm初步布局，91段Top铜/36个地孔。14个内部串阻—MUX模拟网全部闭合；仍21个信号网56连接项开放。实际重铺、保存关闭重开后，其他原生DRC错误0。
- 原生PCB2 SHA：83b238dfec46b08fd8f0825804fd37d57b1d44181c30f0f27e93c53e7ddcbab3。43段新增信号铜实际物理及全宽Bottom地参考通过。C3一个地孔/引线有意调整，其他源铜/孔及规则/PAD映射保持。全板参考/细颈/机械装配未验收。
- `Sensor14_frontend.esch2`、`PCB2.epcb2`是实际新子板快照；`working-project-metadata.eprj3`是同一U9ControlWork整个工作工程元数据，仅作恢复上下文，不能冒充独立完整工程包。原951主板及14页在当前交付native目录保持。勿覆盖活工程或建立重复工程。
- 每组26贴片/2直插，六组156贴片/12排针。用户不能焊贴片，必须核实工厂贴片/排针预焊、全部费用和清远交期；当前未报价。
- 六板J2.15 SENSE_OUT必须接六个独立Nano采样输入，严禁并接。共享控制扇出、电源、线缆及真实感应校准仍需验证。
- 先读相邻evidence目录sensor-front-native-progress-current.json、sensor-front-14nets-actual-Cu-audit-current.json和sensor-front-electrode-whole-channel-order-current.json。左8电极端点序相反，直接单调横向路由有28对交叉次序，只是当前通道问题，不是全局无解证明。
- 不重放原理图构建/导入、left8/right4/right2已落线脚本或终态Top35自动作业。仅接续同一PCB2实际文件。当前实物UNMEASURED，六板和全部模块附件700元总价仍未闭合，不可下单。
