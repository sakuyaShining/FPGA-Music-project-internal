> 当前版本见 [README-v2.md](README-v2.md) 与 [执行计划](执行计划-20261020.md)。下文保留 2026-10-19 v1 历史快照，不代表当前 230 件 PCB 的状态。

# 双屏整机图纸审查与采购制造准备 · 2026-10-19

**版本：dual-screen-carrier-review-v1；状态：原理图候选已实现、静态审查；整机尚未放行制造。**

用户目标按北京时间 **2026-10-21 00:00之前**安排。保留独立可视化屏和7英寸右手推子屏，演奏时两者同时可见；没有把推子区改为41/43mm，也没有增加应用MCU。

## 已形成的实际成果

- 嘉立创EDA原生工程：`C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019/FPGA-Music-Dualscreen-Review-20261019.eprj3`。
- D盘交付包：`D:/FPGA-Project/codex-deliverables/dual-screen-review-20261019/`，含12页PDF、逐页PNG、原生工程ZIP、网表、BOM与逐脚审查结果。
- 202个实物元件，964个引脚；827个连接、137个明确NC、243个网络。原生网表逐脚比对0差异，原生BOM覆盖202个位号，嘉立创EDA检查返回空错误列表。原四推子工程SHA核对未变。
- 27个唯一物料型号已有公开LCSC库存快照；电阻/电极接口缺货已更换，当前候选采购量均被该库存快照覆盖。**这不是国内商城报价，也不是嘉立创SMT库存保证。** 三种BOOMELE连接器在供应商中英文名称有差异，保留机械图复核提示。
- `procurement-native-candidate.csv`含实际用量、最低采购量、公开美元阶梯、库存和装配分工；`jlc-bom-DRAFT-NOT-FOR-ORDER.csv`只供后续贴片匹配。

## 页码与实际电路

| 页 | 内容 |
|---|---|
| 1 | Nano J5/J6两条1×20排针，17个面板GPIO及复用的I²S输出；未用板载接口NC |
| 2 | 六门LVC14、595、165、24LC256及两选一回读器 |
| 3 | 双屏自定义线束接口、I²C与片选上拉 |
| 4 | PCM5122、3.3V电荷泵/内部LDO去耦与AUX线路接口 |
| 5 | 独立DAC 3.3V稳压候选、供电分域及调试电源接口 |
| 6 | 四预设、编辑、带按压编码器及输入上拉 |
| 7–12 | 六路4067，每路14个电极接口、两组参考负载、1k串阻、TI保护器件 |

84个可用电极位支持80/83节点两种配置。`electrode-map-25-OPTION.csv`和`electrode-map-26-OPTION.csv`仅列映射选项，不替用户决定音位端点或电极几何。电极参考在地址14/15，未放未经证明的固定1nF公共计时电容。

## 本轮纠正的选型与接线

1. **RA8875保留MISO读回**。U11的S接HARM_CS_N，I0=RA_MISO、I1=KEY_QH，Y到Nano28。按厂家引脚表，I1=1、I0=3；不直接并联两路推挽输出。协议与实际采样时序仍待实现/实测。
2. RA8875以SPI控制字区分命令/数据；VIS_DC只给ILI9341。忙状态分别按绘图寄存器/相应功能读取，不能将所有忙条件等同。120字节线上传输时间不能用作真实帧率。
3. 原C2841426是**TECH PUBLIC TPD4E02B04DQAR-TP**，不能套用TI手册。本候选改用**TI TPD4E02B04DQAR / C106794**，24片、覆盖84个电极；NC脚6/7/9/10明确NC，不把这些脚当作内部直通通道。成本须重新报价。
4. 缺货候选C21190→**C22548**（1k/0603/1%）；C107696→**C22962**（220Ω/0603/1%）；电极接口C66987→**C22465876**（1×16公排针）。后者需要母头线束，机械封装已随型号更换，不能当原母座直接替料。
5. **更正旋钮判断**：[ALPS原厂EC11E15244B2页面](https://tech.alpsalpine.com/e/products/detail/EC11E15244B2/)明确带按压、30定位/15脉冲、行程1.5mm。旧“C470754无按压”结论撤销。本候选恢复C470754。C370986附件实际指向EC11E15244G1，不能证明EC11E183440C的精确机械规格。
6. PCM5122采用I²C 0x4C，BCK/LRCK均输入；LDOO只接100nF到地，不能接3.3V；VCOM按默认VREF模式接地。52.734375kHz手动PLL字段只通过算术检查，完整静音、启动、锁定和错误处理未实测。
7. 两屏VCC候选均走5V_SYS，**要求模组自带适用稳压、所有数字IO为3.3V**。Nano 3V3_IO仅供扫描/控制；DAC_3V3独立，不能并接。Nano J5.1保持NC，未把USB与外部5V直接并联。
8. AUX为线路输出，外置TRS的Tip=L、Ring=R、Sleeve=GND；不是耳机/无源喇叭接口。板载MAX98357为桥接喇叭输出，两端均不接AUX或地。

## 审查和报价文件怎么使用

- 先看`connectivity-audit.json`、`pin-net-audit.csv`及12页PDF。规则检查和连线一致性不证明电源、触摸、音频或整机功能已通过。
- 对照`harness-contract.csv`做线束表。**J10/J11编号是本项目自定义接口，不是商家屏幕原生排针编号。** 供方针脚栏仍为NOT_ASSIGNED，禁止照编号直接插屏。
- `release-open-items.csv`记录所有未闭环项和所需证据。`采购与制造询价稿.md`可供用户发给供应商；本轮没有发送询价、购买或下单。
- 原生PCB仍为空，没有真实布局、布线、Gerber、钻孔、CPL和布局DRC。不能用原理图坐标生成假的贴片坐标，也不能将BOM草案作为制造放行。
- 首版v0的原生工程ZIP/PDF保留在D盘，最终默认文件为v1。大图和数据手册放D盘，避免继续占用紧张的C盘空间。

## 20日收敛顺序与21日前交付边界

| 顺序 | 20日目标 | 完成判据 |
|---|---|---|
| 1 | 确认两屏具体可售配置/针脚和到手价 | 型号、触摸、接口、电源、连接图与报价能一一对应 |
| 2 | 关闭供电/接口/封装审查问题 | 电源树、USB隔离、模块上拉/电平、实际Nano版本、机械图逐项签注 |
| 3 | 冻结首轮板型、摆件/布线与装配分工 | 真实PCB及DRC，评估电极/模拟/数字/电荷泵回流；独立审图 |
| 4 | 形成可下单材料或明确暂缓表 | Gerber/钻孔/真实CPL/采购BOM及平台匹配核对；未通过项明确暂缓 |

当前已完成的是**审查候选与准备材料的第一轮**，不是整机图纸最终审签。模块供应信息、PCB布局、实体标定与FPGA联合路由不能由静态审查代替；若21日前不能关闭，保留明确暂缓项，不将其写为已完成。现有可继续推进的资料和脚本均在本目录，不能把本聊天旧源码当作最新产品RTL。

## 来源与复现

- 原始四推子工程保留不变；输入逐文件SHA见`evidence/original-manifest.json`。
- 设计依据：主仓库38/39/60/86号及WorkBuddy 88号作为可纠错输入。86号完整联合路由仍失败；没有新整机码流或本轮板验。
- [Nano3921 rev1.30原理图](https://dl.sipeed.com/fileList/TANG/Nano_20K/2_Schematic/Tang_Nano_20K_3921_Schematics.pdf)、[Nexperia4067](https://assets.nexperia.com/documents/data-sheet/74HC_HCT4067.pdf)、[Nexperia1G157](https://assets.nexperia.com/documents/data-sheet/74LVC1G157.pdf)、[TI PCM5122](https://www.ti.com/lit/ds/symlink/pcm5122.pdf)、[TI TPD4E02B04](https://www.ti.com/lit/ds/symlink/tpd4e02b04.pdf)、[DIODES AP2112](https://www.diodes.com/datasheet/download/AP2112.pdf)、[RAIO RA8875手册镜像](https://cdn-shop.adafruit.com/datasheets/RA8875_DS_V12_Eng.pdf)。
- 器件查询原始JSON与UTC时间见`evidence/catalog/`；数据手册下载状态/SHA见`evidence/datasheet-manifest.json`，下载失败不标作已取得。
- `build_review.py`/`rebuild_candidate.py`是**隔离工程修改脚本**，后者会重建指定候选图页，不能对原型或已审签版本盲目运行。`verify_review.py`为只读审查；`prepare_procurement.py`更新采购候选表；`package_review.py`复制交付材料到D盘。
