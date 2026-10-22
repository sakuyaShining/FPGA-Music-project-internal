# INV2 原生连通修复 · 已保存重开验证，未投板放行

当前施工工程：`C:\Users\Sakuya\Documents\LCEDA-Pro\projects\FPGA-Music-Dualscreen-U8BusWork-20261022`。PCB SHA256 `6509803e7afca781b7f71ad69183cc10d8f6413312701eb16a2cdc46dfe83afd`。
相对上一已验证 59 项检查点，INV2（U7.6 → R13.1）完整闭合。严格原生 DRC 保存重开后为 **0 间距 / 0 物理 / 57 未连通，12 网**。未完成网络见 remaining-networks.csv；35 项仍属于 ADDR0–3/MUX_DISABLE，BUS_MOSI 仍未闭合。

为释放 U7 出口，局部抬升 3V3_PERIPH 顶层主干并保持 15.74 mil 宽；局部迁移 VIS_DC 换层孔并恢复原铜。VIS_DC 原有两焊盘岛仍为两岛，未冒称已闭合。INV2 使用 8 mil 线路、两个 24/12 mil 过孔，另增一个同规格 GND 缝合孔。R13 是 INV2 至 SENSE_2 的 220 Ω 串联电阻；本批未移动它，原 SENSE_2 铜保留。引脚角色此前依据 TI SN74LVC14A 数据表表 5-1 核对：https://www.ti.com/lit/ds/symlink/sn74lvc14a.pdf 。

## 核验结果

- 原生实际铜与声明变更逐网逐层几何对账，最大偏差 0.000001095 mm；558 孔逐个核对尺寸与位置，230 器件、1079 焊盘保持。
- 新 GND 孔在重建并重开后的实际地铜 15/2 均有有效铜环接触；INV2 顶层参考 15、内层 16 参考底层 2，排除各自换层孔周围 1 mm 后，线路中心线投影连续覆盖。排除范围、数值和铜环面积见 checkpoint-review.json。
- 原传感/音频及其他未受影响网络铜保持；115 个底层敏感/音频网络在同一排除掩模下比较实际内层16地铜投影，无覆盖退化。原有缺口不因本项比较而关闭。
- 两处 INV2 信号孔距合格参考地孔约 2.212 / 1.900 mm，未满足项目 1.5 mm 偏好，保留开放。几何覆盖与距离检查均不是 SI/EMC 或实物功能认证。
- 原63项施工源与稳定R15源文件哈希核对不变。本工程非PCB设计文件不变；描述文件仅更新PCB保存时间/版本元数据。

## 可恢复交付与下一入口

native-inv2-repair-WORK-IN-PROGRESS.zip 是同一施工工程完整原生包，ZIP CRC 和包内 PCB SHA 均验证。checkpoint-review.json、checkpoint-capture.json、checkpoint-drc.json 是同一57项源；probe-map-current-UNMEASURED.csv 复核21个测点但没有实物测量。

唯一当前施工入口为上级上级 REGIONAL-WORK-IN-PROGRESS.json。旧 8b9b68a5 源上的27个地址候选及旧DSN/SES不得直接导入，需对新57项源重检。固定布局地址出口、单邻线ripup和两根传感底层线局部重路由均未恢复全部所需网络；下一方法必须联合移动受影响布局/整束铜与去耦，或重新分配可恢复的出线通道，不重复相同局部搜索。

稳定 ACTIVE-ROUTING-CANDIDATE.json 仍为R15，本施工版没有制造放行。尚需闭合全部剩余网络、整板电气/参考地与DFM复核、屏幕/机械/装配同版资料核实和最终制造导出；上电、满载、屏幕/触摸、84路传感和音频均未实物验证。最终固件容量与集成由另一聊天独立推进，本批未修改RTL。
