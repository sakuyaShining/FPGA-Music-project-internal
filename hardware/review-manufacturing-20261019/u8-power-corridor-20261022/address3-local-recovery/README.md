# ADDR3 原生施工检查点：参考地待修复，禁止投板

此包是可恢复施工资料，不是制造放行包。实物上电、双屏/触摸、84 路传感与音频均为 **UNMEASURED**。

## 已形成的原生结果

- 独立工程 `FPGA-Music-Dualscreen-Addr3Work-20261022` 已保存重开；严格 DRC：0 间距错误、0 物理错误、50 项未连通，剩余 11 网。
- ADDR3 七节点完整连通，消除原来的 7 项连接错误。未修改 RTL、BOM、元件/焊盘位置、板框或层数。
- L2_M04、L2_M14 保留源铜；L2_M02、L2_M03 已恢复连通，保持 8 mil、Top1/Bottom2。未缩减传感能力。
- 清理 2 个没有实际换层作用的 ADDR3 冗余孔；现为 594 个过孔，其中新增 17 个 GND 缝合孔。17 孔均在实际 15/2 层地铜上有不少于 0.15 mm² 的环接触。
- 实际铜与声明计划最大 Hausdorff 差 0.00000835 mm；非铜设计数据逐项与源核对一致。原 57 项源工程全部文件哈希保持不变。

## 尚未通过的参考地审查

本候选未提升为已验证施工源。`REGIONAL-WORK-IN-PROGRESS.json` 的 `project/pcb_sha256` 仍指向原 57 项源；`pending_trial` 指向本候选。

- ADDR3：Inner16 对真实 GND2 的中心线投影检查通过（扣除自身换层孔 1 mm 区域）；Top1 对 GND15 仍有合计 9.3661 mm 投影缺口。
- L2_M02：Top1 对 GND15 仍有 0.6219 mm 投影缺口；Bottom2 对 GND16 未见缺口。
- L2_M03：Bottom2 对 GND16 仍有 2.4489 mm 投影缺口；Top1 对 GND15 未见缺口。
- 301 个未改动敏感/音频“网络—走线层”组已做前后比较。Bottom2 的 114 组未退化；Top1 的 6 组出现约 0.294–0.624 mm 的覆盖损失：L0_E08、L0_M07、L2_E05、L2_M00、L2_M01、RC4。缺口与新过孔避空位置的关系见 `reference-loss-localization.json`。
- U2 一处回流孔距离仍为约 2.7 mm，未达到项目 1.5 mm 设计偏好；这不是通用制造限值，也不是 SI 签署。所有回流/阻抗、SNR 与实际边沿仍需验证。
- ADDR3 实际线长约 380.73 mm、16 个信号过孔。M02 线长 20.48→35.10 mm、过孔 0→2；M03 线长 18.94→50.23 mm、过孔 2→3。寄生、噪声及标定影响未测，不用 DRC 或连通性替代功能证据。

## 唯一接续入口

先读根目录 `REGIONAL-WORK-IN-PROGRESS.json` 的 `pending_trial`，再读本目录 `native-state.json`、`checkpoint-review.json`、`native-stage-review.json` 和 `reference-loss-localization.json`。所有路由及复核进程已终止；CAD 会话仍开放。不要重跑 `native-trial.py` 或重放原始导入。

1. 核对候选 PCB 哈希、当前 Windows 账户及 CAD 项目身份。另一账户必须自行打开保存的工程，不能借用 Sakuya 的 sessionId。
2. 优先局部调整造成 Top1 敏感走线参考损失的新过孔及相邻短线，使用实际 Ground15 避空轮廓作为约束。不能只按信号铜线间距判断参考地安全。先做离线真实四层铜、孔/焊盘、敏感区与连通复核，再原生修改。
3. 原生 ID 映射：`native-apply.json.createdV[i]` 对应 `grounded-plan.json.vias[i]`，`createdL[i]` 对应 `lines[i]`。任何后续修改先绑定当前候选哈希，保留本恢复包；原始计划 SHA650… 不可再次导入候选。
4. 同时处理 ADDR3 Top1、M02 Top1、M03 Bottom2 的上述实际投影缺口，保持四条受影响传感线完整连通及原宽度，保留原 M04/M14 铜。完成后四层原生重铺铜、严格 DRC、保存重开、重新核对 301 组参考、生成新恢复包；通过后才提升候选。
5. 继续 ADDR0/1/2、MUX_DISABLE、BUS_MOSI 与其余显示/复位网。保持双屏、84 路、Nano20K、140×100、四层及既定 BOM，不触碰另一个聊天的 FPGA 容量评估。

剩余网：TP_RESET_MOD_N(2)、VIS_DC(2)、DISP_RESET_N(2)、DISP_VIS_DC(2)、HARM_CS_N(3)、BUS_MOSI(7)、ADDR1(7)、ADDR2(7)、MUX_DISABLE(7)、ADDR0(7)、PRESET3(4)。数字为原生 Connection Error 对象数，不是引脚数或飞线数。

## 恢复与交付

- `native-addr3-50-REFERENCE-REPAIR-PENDING.zip`：原生工程恢复包，CRC 与内部 PCB SHA256 已复核。
- `checkpoint-review.json`：保存重开、严格 DRC、包哈希及未完成项。
- `native-stage-review.json`：实铜对账、实际地铜/回流、敏感走线前后比较、线长/孔数。
- `full-preflight.json` / `ground-preflight.json`：独立四层几何及接地孔检查。

之前的 U8/C8/R63 移位未恢复供电/控制网，已拒绝；显示复位候选存在参考地缺口，已拒绝；不重复这些终态作业。ADDR3 本轮的有效方法是识别 U5 内层孤立区、改用可到达主干的出线、按实际地覆盖连接分支，并优先恢复原 M04/M14 铜。

制造资料与最终装配/上电测试尚未放行。器件/显示模块版本、机械配合、供电负载、最终固件整合及实测开放项继续以根目录 release-open-items.csv 为准。
