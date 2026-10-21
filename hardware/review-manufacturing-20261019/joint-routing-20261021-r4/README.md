# r4 原生布线比较候选 · 未放行制造

在独立工程 `C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-4L-Candidate-20261021-r4` 内完成 14 个网络重布，启用逻辑铜层 1 / 15 / 16 / 2，增加两个内层地铜。原双层 r3 的全部 19 个源文件保持原哈希；没有覆盖 CURRENT-STATE.json、采购工艺或既有快照。

保存、重建四层地铜、关闭并重新打开后，完整原生 DRC 为 **0 间距 / 0 物理 / 62 未连通对象（12 网）**。器件 230、焊盘 1079、API 铜线 3264 + 原生微短线 28（实际 3292）、过孔 519。对比双层 r3 的 74 对象 / 16 网 / 533 孔，闭合 I2C_SCL、DISP_RESET_N、DISP_VIS_DC、DISP_VIS_CS_N 四网；新闭合网增加 15 个过孔，已连通网络重布减少 29 孔和 181.608 mm 铜线，故整板净减少 14 孔。

原生完整铜形状已按 14 网 × 3 层与方案核对，5 nm 几何比较容差仅处理保存舍入；过孔保存到 4 位 mil 小数，最大舍入不超过约 1.3 nm。未放宽设计规则。全部器件、属性、焊盘、网络、规则以及未选择网络铜线不变；其他 17 个工程文件不变。ZIP 已核 CRC 及 19 个 SHA256。用的是默认原生脚本身份，没有更改外部交互权限或改用其他扩展身份。

## 当前源与恢复

- 工作分支唯一入口：上级 `ACTIVE-ROUTING-CANDIDATE.json`；原双层采购/制造基线仍由上级 `CURRENT-STATE.json` 指向 r3 / 74 项。
- 原生检查点：`native-candidate-checkpoint.json`；新会话 `native-session.json`；专用 API 包装 `candidate_native.py`。
- 原生捕获：`native-verified-capture.json`，必须把原生 28 段微短线一起纳入后续障碍物。
- 原生完整 DRC：`native-drc.json` / `native-drc-meta.json`；`native-geometry-reconciliation.json` 是完整铜核对。
- 原生包：`native-4L-230-0clear-62open-routing-r4-20261021-CANDIDATE.zip`（交付根目录）。
- PCB SHA256：`97a837d8411cef56633792edbb716451a4f6806a66dba659a91058e0c69c2515`。
- ZIP SHA256：`146bb3c14b1e12aaef0984c49805347b7c8bdce5d23f1f52bd18582bd1da6030`。
- 修改前候选快照：`D:/FPGA-Project/snapshots/before-four-layer-r4-copper-20261021-094047/native-four-layer-before-routing.zip`，SHA `974b1cde5a3770129ba00bc19721ad4ca6bb909d112468d90812290c8a557488`。

## 已发现的真实边界

1. **逻辑四铜层不等于物理叠层完整。** 原生 setTheNumberOfCopperLayers(4) 生效，四铜层走线/地铜均已保存并参与 DRC；但 LAYER_PHYS 仍只有原先两铜层和一个介质层的记录，内层 15/16 缺物理堆叠记录。命名叠层 API 当前返回 undefined / 空列表。详见 `physical-stack-audit.json`。CLI TLayerPhys 文档单位与继承记录外观又有差异，不能猜单位后直接写。须通过已知原生叠层样本或明确的 API 格式核实并补齐，再与嘉立创实际工艺对照。已查[嘉立创原厂叠层表](https://cart.jlcpcb.com/client/template/placeOrder/impedance.html)，但未选定/报价任何具体工艺。
2. **回流仍不完整。** 真实逻辑内层15地铜为单个约12329.68 mm²多边形；84 个接地过孔都接触两个新内层。内层16控制线与原底层 I²S 预留了0.6mm投影间隔，但其他过孔/通孔反焊盘仍造成空缺。排除三个 I²S 网所有信号过孔周围1mm及信号通孔焊盘外扩0.5mm区域后，底层中心线投影落在内层16地铜上的比例仅约97.6% / 92.8% / 91.7%，**不是完整回流或 SI 合格证**。I²S 仍为9/8/10孔，见 `visual-native/plane-and-return-geometry.json` 和空缺定位CSV。
3. 新内层地铜可能增加高阻传感线的寄生电容；这是工程推断，未做实物/完整场求解验证，不能把双层校准或此前假设 SPICE 结果沿用为四层传感验收。84 电极容量和网络完全保留。
4. 芯片供电/去耦布局仍需复查，尤其 C35 到 U15.20 的位置与实际供电回路；本轮未移动任何器件，也没有把几何连通当作供电瞬态合格。
5. 12 个未闭合网仍在：BUS_SCK、BUS_MOSI、HARM_CS_N、ADDR0–3、MUX_DISABLE、PRESET3、INV2、DISP_SCK、DISP_MOSI。仍需联合出线/局部布局处理，不能仅增加孤立过孔后声称闭合。

## 未应用的失败候选

`u15-all` 恢复原铜后相交；`connected-first` 最后只留下与原铜相同的 TP_RESET_N。`local-v1/v2/v3` 的局部 IO/GND/电源交换或因间距失败，或局部通过但整网时钟仍封闭，未写入任何原生工程。`four-layer-offline` 是单内层试布，仅7条初步路径，未应用。实际应用的是 `four-layer-mixed/plan.json` 中经独立连续几何及四层真实焊盘连通检查的14网：`four-layer-mixed/independent-geometry.json`。

## 下一步

优先补齐并核验物理叠层，定位并修复 I²S 回流空缺/过多换层，复查 C35/U15 去耦和12网出线。继续以四层候选作隔离的工程比较，保留 r3 可恢复基线。后续过孔规划必须检查所有四个铜层；不能直接用只看顶/底层的旧布线函数。原生调用用本目录 candidate_native.py；不要误用 native_review.py 中指向原双层工程的会话与路径。当前所有制造放行字段均为 false，未下单、付款、联系供应商、烧写固件或修改额度权益。
