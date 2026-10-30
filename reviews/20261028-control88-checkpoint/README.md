本目录是独立审阅快照，不替换 `hardware/current/` 或已发布 main。

下载同目录 `Control88-review-source-20261028.tar.xz`，解压后以 `native/FPGA-Music-Control88-LAYOUT-CANDIDATE/FPGA-Music-Control88-LAYOUT-CANDIDATE.eprj3` 打开。压缩包内 `MANIFEST.json` 列出39个源与证据文件的 SHA-256；第三方规格书通过官方链接引用。本次未合并 main、未制造放行。

# 接续成果与当前采购入口（2026-10-28）

当前不能整套下单。此包是可恢复、可继续编辑的工程候选，未放行制造。

已完成：控制板加入原有 PCM5122/AUX 与 DAC 独立电源；88件/444焊盘/10页原理图，32个空脚有原始NC依据。最终原生原理图DRC为0致命/0错误/0警告，30组物料属性完全匹配。PCB已原生导入并完成第一轮布局；按Sipeed官方机械图修正两排排母至20.32mm，USB朝左时J5在上、J6在下，两排1脚均在左。四处输出滤波改为TI典型10kΩ线路负载方案：R41/R42为470Ω C23179，C27/C28为2.2nF C0G C33353，标称RC极点153.9kHz。没有新增FPGA GPIO。

PCM5122初始化候选通过7组成功/故障仿真，独立接收器确认旧输出是左对齐16位，8组数据在LTJ接收端正确、在I²S接收端均错误。初始化按软件I²C地址0x4c、BCK1.5MHz、Fs46875Hz、VREF模式配置，并核查PLL锁定、格式回读和DSP启动。未接整机共享I²C仲裁，也未做整机PnR/STA或实物音频测试。

PCB最新原生检查有412个连接性错误，属于尚未布线；当前为默认双层种子，四层叠层、完整布线、回流/电源/机械及制造复核均待完成。请不要把原理图DRC为0理解成PCB可以投板。J12仍是L/R/GND三针接线口；外接3.5mm立体声插座C19189087已查到商品，但固定方式及实物导通核验未完成。

采购表净用量为控制板88件+六块传感板168件=256件、37种料号；此前36种表在本次滤波修改后已被替代。数量未含备品和工厂损耗，整取量只是按商城最小量/销售增量计算，既不是人民币报价，也不是嘉立创SMT库存分配。部分库存沿用先前精确查询，后续批量刷新返回403；这表示本次刷新不可用，不表示库存为0。C205940、C50984、C962071属于先前观察的少量库存，应由实际配单再确认。

传感板C1591→C14663、C105579→C25819目前只在询价表中替换；附带传感板原生BOM仍保留原料号，不能直接将两者混用下单。用户只需焊线/排针，所有SMT器件必须由工厂贴装；尚未取得完整贴装、运费与交期报价。

仍须补齐：屏幕完整配置的可下单SKU/含运价/交期；5V电源与接头、TF卡、线束和电极材料的精确商品；全套700元预算；控制板制造资料与贴装核验；84路采集、J10触控、四槽演奏表情、应用/保存/取消、PCM录放及非易失存储的整机接合与验收。未下单、未付款、未烧录。用户已明确允许仅屏幕从厂家官方店选购，其他器件继续立创；本次授权不包含下单。

工程入口：`FPGA-Music-Control88-LAYOUT-CANDIDATE/FPGA-Music-Control88-LAYOUT-CANDIDATE.eprj3`。固定旧工程、传感板及已有main未被替换。原始基线与中间候选留在本地；本包优先保存最新可接续候选及证据。

## 立创商城直接链接（询价用）

|料号|精确型号|净用量|商城整取数量|商品页|
|---|---|---:|---:|---|
|C106794|TPD4E02B04DQAR|24|25|[立创商品](https://item.szlcsc.com/108010.html)|
|C110499|DMP2035U-7|1|5|[立创商品](https://item.szlcsc.com/111722.html)|
|C133541|SN74LVC14ADR|6|10|[立创商品](https://item.szlcsc.com/144847.html)|
|C14663|CC0603KRX7R9BB104|25|50|[立创商品](https://item.szlcsc.com/15331.html)|
|C14858|CL10C101JB8NNNC|6|50|[立创商品](https://item.szlcsc.com/15530.html)|
|C158012|B2B-XH-A(LF)(SN)|1|20|[立创商品](https://item.szlcsc.com/169360.html)|
|C1592|CL10A105KO8NNNC|1|50|[立创商品](https://item.szlcsc.com/1944.html)|
|C1607|CL10A225KP8NNNC|8|20|[立创商品](https://item.szlcsc.com/1959.html)|
|C1634|CL10C100JB8NNNC|6|100|[立创商品](https://item.szlcsc.com/1986.html)|
|C179326|74HC4067PW,118|6|6|[立创商品](https://item.szlcsc.com/190720.html)|
|C205940|SN74LV595ADR|1|1|[立创商品](https://item.szlcsc.com/206938.html)|
|C210834|MF-MSMF110/16-2|1|10|[立创商品](https://item.szlcsc.com/211712.html)|
|C22465876|PZ254V-11-16P|18|20|[立创商品](https://item.szlcsc.com/24163068.html)|
|C22548|RC0603FR-071KL|86|100|[立创商品](https://item.szlcsc.com/23274.html)|
|C22912|0603WAF2372T5E|1|100|[立创商品](https://item.szlcsc.com/23639.html)|
|C22962|0603WAF2200T5E|6|100|[立创商品](https://item.szlcsc.com/23689.html)|
|C23162|0603WAF4701T5E|5|100|[立创商品](https://item.szlcsc.com/23889.html)|
|C23179|0603WAF4700T5E|2|100|[立创商品](https://item.szlcsc.com/23906.html)|
|C247920|2.54-1*12P|1|10|[立创商品](https://item.szlcsc.com/244949.html)|
|C25803|0603WAF1003T5E|5|100|[立创商品](https://item.szlcsc.com/26546.html)|
|C25819|0603WAF4702T5E|6|100|[立创商品](https://item.szlcsc.com/26562.html)|
|C273656|SN74LV165ADR|2|5|[立创商品](https://item.szlcsc.com/262001.html)|
|C318884|TS-1187A-B-A-B|8|20|[立创商品](https://item.szlcsc.com/299976.html)|
|C33353|CL10C222JB8NNNC|2|20|[立创商品](https://item.szlcsc.com/34318.html)|
|C411625|24LC256-I/SN|1|1|[立创商品](https://item.szlcsc.com/403162.html)|
|C4190|0603WAF2201T5E|2|100|[立创商品](https://item.szlcsc.com/4597.html)|
|C470754|EC11E15244B2|1|1|[立创商品](https://item.szlcsc.com/476834.html)|
|C49257|2.54-1*3P|1|20|[立创商品](https://item.szlcsc.com/50265.html)|
|C503437|74LVC1G157GV,125|1|5|[立创商品](https://item.szlcsc.com/516133.html)|
|C50984|2.54-1*20P|2|5|[立创商品](https://item.szlcsc.com/51996.html)|
|C51118|AP2112K-3.3TRG1|2|5|[立创商品](https://item.szlcsc.com/52131.html)|
|C544515|TCA9517DGKR|1|1|[立创商品](https://item.szlcsc.com/565166.html)|
|C55266|TPS2553DBVR|1|1|[立创商品](https://item.szlcsc.com/56292.html)|
|C7668|SN74LVC244APWR|1|5|[立创商品](https://item.szlcsc.com/8145.html)|
|C7836|SN74LVC1G17DBVR|1|5|[立创商品](https://item.szlcsc.com/8313.html)|
|C962071|PCM5122PWR|1|1|[立创商品](https://item.szlcsc.com/1043162.html)|
|C98220|RC0603FR-0710KL|13|100|[立创商品](https://item.szlcsc.com/99429.html)|

外接立体声插座候选：[C19189087 / HX PJ-320A-3P DIP](https://item.szlcsc.com/20414042.html)，单机净需1只，前次观察最小整取10只；未计入上面的256件SMT/板上物料。该件是直插插座，须安排可靠固定，不能把它当已带接线的成品模块。

依据：[TI PCM5122 SLAS763C](https://www.ti.com/lit/ds/symlink/pcm5122.pdf)第42、47–49、72–85、97页；[Sipeed v3921机械图](https://dl.sipeed.com/fileList/TANG/Nano_20K/4_Dimensional_drawing/v3921/Tang_Nano_20K_3921_Demension.pdf)。
