**2026-10-29 基线复核更正：传感板暂停投产。** 实际S1 Gerber底层地铜到22个非地排针焊盘最小间距约0.162858mm，低于保留门限0.1651mm；此前原生DRC0、5μm图形比对与较低通用门限未覆盖该严格条件。可继续询价，先不按本版传感板付款生产。旧冻结包字节保留用于追溯，不能据其中的PASS或READY文字忽略本更正。详见基线`evidence/retained-clearance-gate-audit.json`。

# 2026-10-29 硬件交付基线：Control88 R2 + Sensor14Bank S1

这是一份可恢复的工程制造资料基线，可交厂家DFM/SMT审单、预览和报价。不是已下单、已实测或完整产品验收。

## 使用入口

- `factory-handoff-20261029.zip`：给厂家审单的总包。解压后按01/02目录分别上传Gerber、BOM、SMT坐标；总包不要直接作为某块PCB的Gerber上传。
- `control88-frozen-r2-20261029.zip`、`sensor14-frozen-s1-20261029.zip`：独立原生源、制造文件及证据。解压后可分别执行`python verify_package.py`核对。
- `WHOLE-MACHINE-PURCHASE-AND-ASSEMBLY.md`：采购、供电、接线、单板扩至六板、装机与验收顺序。
- `JLC-FIRST-ORDER-TUTORIAL.md`：初次审单和PCB/SMT建单步骤及官方教程链接。
- `Q4-FIRMWARE-SOURCE-RECOVERY-NOT-QUALIFIED.zip`：协作者固件与显式GPRJ依赖/数据表的只读恢复副本；不是可烧录正式固件。原相对路径保留，构建脚本可能引用旧工作区，恢复后需审阅适配，不直接运行。

## 固定口径

1块Control88 R2 + 6块Sensor14Bank S1 = 7块装配成品，38种C料号、256净件、232 SMT + 24插件。单板BOM不预乘六。旧32/232、37/256及旧载板227件表不用于本基线下单。

Control PCB SHA256 `733e1d9c33d11ef946863dca0bc9f36ae2916b9965d038b147aafea416194eb8`。

Sensor PCB SHA256 `2184d027643f52ff50a7bca4bf9c717ae805a099043d300855f3348be5b5b7e3`，原理图 `7710964c5831a580909709aab0ddb271cef88779a11f585de45149c6046e12eb`。

两板原生保存关闭重开DRC0，详见子包证据。84外接电极=75音位电极+5八度+4备用，另12个板上参考通道。J2仅3.3V；六路SENSE独立。RC_DRIVE低放电、高充电，测反相SENSE高到低。

## 尚未闭合

厂家DFM/SMT贴装预览、物料供给/替代审核、报价与交期；屏幕完整配置报价；J10端到端转接线；电源、电极、线束、结构、音频插座和TF卡的精确配单；全套含运700元预算；RC扫描、J10驱动、EEPROM/TF、四槽表情与录放整机接合，以及全部样机实测。

Nano20K通过USB-C供电，J13为独立外设5V输入，当前控制板J5.1未接Nano5V。不能只接J13期待整机启动；电脑下载时避免给Nano USB叠加两个5V来源。控制板已集成PCM5122，不重复购买旧独立音频HAT；J11已取消。

本基线只在任务分支提交备份，main发布状态以实际Git提交和PR合入为准。子包内“尚未推送”等文字是冻结时刻记录，后续发布以仓库交付收据为准，不修改已冻结包字节。
