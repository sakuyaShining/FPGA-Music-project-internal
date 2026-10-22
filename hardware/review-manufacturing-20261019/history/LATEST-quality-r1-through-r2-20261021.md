# 当前审查入口 · 2026-10-21

05:45接续新增：`connector-qualification-20261021-r2`已用原厂图纸核对7个连接器位号的针距/标称孔径，电源线端明确至SXH-001T-P0.6普通型。当前装配/调试入口为 **`装配与分阶段验收-r2.md`**；`bringup-acceptance-20261021-r2`有22阶段、32电压槽和165接口脚待测模板，静态核对通过，尚无实测。采购工作簿同步更新端子/线径/旋钮轴规格。

当前为 **quality-r1 走线整理版**：230 件器件、3244 段 API 铜线、529 个过孔、1079 个焊盘、2 层已重建地铜。保存、关闭并重新打开后的完整原生 DRC 为 **0 间距错误、0 物理错误、78 项未连通（17 网）**。

自主采购/制造收口长任务进行中，接续入口见 `AUTONOMOUS-CURRENT.md`。首轮核对确认86号冻结扫描与本板有两处接口冲突（屏幕复位高位、物理电极索引），`hardware-contract-20261021-r1` 保留原版本失败负对照和独立候选通过记录，未改板/冻结实验，也未签联合固件通过。`purchase-preparation-20261021-r1` 已形成36类板上物料、32项外部范围及4页采购工作簿；每板供料分工由旧212 SMT+5手焊按键调整为**217 SMT、13通孔补焊**。按钮C318884散买0，但国内页面有贴片库存，选择同料号工厂供料，最终平台匹配/费用待核。小屏八线错位接线表已明确；大屏、机械、电源、布线及报价仍未闭合，制造放行仍为false。

2026-10-21 最新进展：[实际 SPICE 电源与总线验证](../../notes/2026-10-21-SPICE电源与总线验证.md)。已运行 ngspice 的 16 个 I²C、32 个电源工况，并保留独立模型校准、动态校核、网表和波形。假设 1.2A 恒流需求下启动塌陷，低输入电压/线缆压降和 I²C 电容仍需实测收敛；不能冻结整机电源或采购装配。证据入口 `spice-validation-20261021/README.md`。未修改 PCB 或产品 RTL，未完成整板 SPICE/热角落或联合 PnR，制造放行仍为 false。

此前成果复查：[复查结果与仿真边界](../../notes/2026-10-21-成果复查与仿真验证边界.md)。该阶段重跑原生 DRC、基础时钟/I²S/16 路 pad 仿真，并完成 I²C/电源/RC 一阶参数扫描；其中“未执行 SPICE”是该阶段的历史范围，最新局部 SPICE 结果以上述新增记录为准。屏幕 SKU/线束、电极材料、完整固件和关键布局仍不能冻结。

本轮简化 RC_DRIVE、BUS_RETURN、EDIT、VIS_BL_EN、I2C_MOD_SCL、PRESET0、RC3 七个完整网络，共减少 **129.21 mm 铜线、10 个过孔、49 段线段**。没有新增过孔位置；器件身份/位置/方向、全部焊盘、规则及未选网络铜线与过孔均未变，原地网与 I²S 三线保留。

详细记录：[PCB 走线整理与快照归档](../../notes/2026-10-21-PCB走线整理与快照归档.md)。前后对照图见 `visual-quality-r1-20261021/quality-before-after.png`，最新分层图见该目录 `current-layers.png`。

## 当前可恢复原生包

`D:\FPGA-Project\codex-deliverables\dual-screen-review-20261020-v2\native-230-0clear-78open-quality-r1-20261021-CANDIDATE.zip`

包 SHA256：`d8340128342d5dbdcdddbc90fd540cf6a643590ab982c3af55aeecf58f61f88e`。

PCB SHA256：`be576cabac058fc0754fbc87a07565e69531e59c7d249a6f6d267c5f93c5fc3e`。

源文件清单：`route-checkpoint-0clear-78open-quality-r1-20261021.json`。交付目录 `CURRENT-CHECKPOINT.json` 已指向本版本。ZIP CRC、19 个归档工程文件及当前工程文件哈希均核验通过。

原生 DRC：`drc-stage-quality-core-r1-reopened.json`，同名 `.meta.json` 证明 DRC 前后源哈希一致。应用审计：`quality-core-r1-apply-audit.json`；质量度量与归档校验：`quality-r1-result.json`；当前原生捕获：`quality-r1-source-78.json`。

## 整理前独立快照

`D:\FPGA-Project\snapshots\before-routing-quality-refactor-78open-20261021-000126`

归档含原 78 项原生包、源清单、捕获、DRC、剩余网络清单、审查图与恢复说明。19 个原生文件哈希及归档材料 SHA256 清单已验证，后续工作不覆盖此目录。需要恢复时在新目录解包，再打开 `.eprj3`，不要覆盖正在使用的工程。

## 仍待处理

剩余 17 网及报错对象数见 `remaining-networks-78open.csv`，主要为地址/控制/显示总线及未闭合的 `5V_PERIPH`。七网整理未增加连接报错，原音频、GND、84 电极、六组 MUX/计时仍无未连通报错。

中部布局和 I²S 回流/换层风险尚未解决：I²S 三线仍有 9/8/10 个过孔。INV2、PRESET3、DISP_VIS_DC 的带预算试布在局部出线处受阻，未应用。后续应联合整理 U7/U8/U9/U15 附近出线和相邻网络，预留供电、I²S 与控制/显示主通道，再继续补线。不要冻结全部旧铜线后逐条找缝，也不要重放旧 102/88/原始 78 项规划。继续必须使用当前捕获并绑定当前 PCB 哈希。

采购与实物、机械、电源负载及整机 FPGA 联合布局布线等原待办保持。采购范围见 `整机采购范围与制造检查-v2.md`，装配/上电见 `装配与首次上电-v2.md`，其他待办见 `release-open-items.csv`。本轮没有 RTL/固件或码流更新，当前仍为 CANDIDATE，没有制造放行。

## 历史材料

不带 `quality-r1-20261021` 标签的 78 项包，以及 88/102/149 项包和旧 PDF 均为历史检查点。旧 `pcb-reviewed-pages-0clear-149open-CANDIDATE.pdf`、`pcb-pad-placement-review.pdf` 和 `visual-review-78open` 不代表本整理版。当前图片仅作布局审查，不能替代制造导出、电气完整性与实物验证。
