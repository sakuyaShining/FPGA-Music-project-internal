# 2026-10-27 统一接续入口

本次统一已发布阶段成果及其恢复资料。实际远程 main 是唯一发布入口；源码、候选方案、制造核验和实体功能验收分别判断。本次未修改产品 RTL、CAD 几何或引脚分配，也未进行烧录、下单或制造放行。

**接续候选**：本次合并后的硬件资料、同源BOM/放置草稿、J6.15/17文档纠正、叠层缺口及屏幕选型核验见`hardware/current/module-plan/manufacturing/README.md`，位于任务分支`codex/hardware-delivery-20261027`。传感板原生制造导出、完整报价/交期、700元总成本与实体整机仍未完成；不得将本轮资料核验等同制造放行。

## 当前工作与边界

| 工作 | 当前入口 | 真实状态 |
|---|---|---|
| 实体模块／简单小板方案 | `hardware/current/module-plan/模块方案-当前工作单.md` | 仅确认持有Nano20K；清远收货，含全部附件／代焊／运费700元硬上限，11月4日前实体与视频目标；采购、报价及整机接合未闭合 |
| 原整合载板 | `hardware/current/CURRENT-HARDWARE.json`、`hardware/current/native/` | 保存原生951ce88a，227件、649孔、42项未连通／12网；离线62线24孔、MUX四岛保留，未导入 |
| 14路传感小板候选 | `hardware/current/module-plan/evidence/sensor-fourlayer-native-current.epcb2`及同名`.esch2` | 与原227件载板是不同工程；`sensor14bank/`保留早期83b238df快照。最新保存候选617f550e，302线51孔；作者记录重开后原生DRC及未连通为0，35段参考口径已限定批准；制造文件与工厂装配仍待核验 |
| 三独立操作键 | `hardware/current/module-plan/evidence/edit-control-interface-current.md` | 应用／保存／取消逐针及16位读回合同候选，65536种位序核对；完整固件动作与实物未验收 |
| FPGA与演奏表情 | `project/PRODUCT-SPEC.md`、`project/WORK-PLAN.md` | 保留main的帧／contact与四槽音频增量；全层finger消费者、真实84节点／J10、编辑保存与录放尚未完成；PnR／STA及实体边界不变 |
| 固定恢复检查点 | `hardware/checkpoints/pcb-951ce88a-20261025/manifest.json` | 73项固定身份，60项树内，13项Release外置；恢复资料不等于制造合格 |

## 已确认决定

- J10保留、J11取消；84电极、32×16、四槽、逐音滑条、独立八度、录放与非易失等功能不削减。
- 2026-10-27 17:58 CST，用户接受指定35段本网通孔过渡区按真实反焊盘边界及已核回流地孔验收。只改变该限定口径，其他门限不变。证据：`reviews/20261027-hardware-consolidation/sensor35-approval.json`。
- 接下来继续制造文件核验；不得把批准口径写成已完成制造核验或投板授权。

## 接续顺序

1. 先读本页，再读PRODUCT-SPEC、模块当前工作单与未完成门禁；不要从旧六角色整板施工计划直接重开复杂PCB。
2. 对固定小板源继续核验同源制造文件／BOM／CPL／工厂预焊与交期；收取屏幕完整配置报价，闭合全部附件与700元总预算。
3. 继续完整手指表情／真实音频与实体控制接合，最终完成整机功能、时序与原规格实测。当前方案不是可直接照单购买的完整成品清单。
4. 原整合载板的完整四层布线与制造交付继续独立验收，实体视频不替代PCB完成。

## 合并范围与历史

- 当前main基点：b732de68bb84408ace7d4a995352de9bc5f5c8a6。
- PCB恢复检查点／门禁：7d5056ad37dfd73577809f765f09b48f27f3d380（原PR5）。
- 最新模块方案与三键／TF证据：5354b46d83e0a0c2495469a627e40ce60fdbe12a。
- 两条来源均以merge保留祖先关系；main的FPGA增量、168h观察／审阅窗口、每日CI与历史恢复输入保留。旧review和交付记录不改写，当前新审阅另存于reviews/20261027-hardware-consolidation/。
- 只在远程main合并及检查确认后清理已完整覆盖的开发ref；恢复tag、Release、原owner工作区和未纳入的其他分支不删除。
