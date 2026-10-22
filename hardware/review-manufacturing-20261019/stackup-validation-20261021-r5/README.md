# r5 四铜层物理叠层核验 · 未放行制造

当前工作源见上级 ACTIVE-ROUTING-CANDIDATE.json；新工程 FPGA-Music-Dualscreen-4L-Stackup-20261021-r5，新会话09c0fd69-4ee1-4b67-83cc-779e92716d04，仅用本目录 native_project.py 操作。r3双层与r4逻辑四铜层的19个源文件分别保持原哈希。

已补齐原生物理顺序 **1 / 361 / 15 / 362 / 16 / 363 / 2**：四铜层与三个介质层。依据[嘉立创公布的1.6mm JLC7628叠层表](https://cart.jlcpcb.com/client/template/placeOrder/impedance.html)，名义结构为0.035 / 0.2104 / 0.0152 / 1.065 / 0.0152 / 0.2104 / 0.035 mm。原厂网页原文、选中表格与SHA保存在本目录。名义铜+介质1.5862mm，原生3位mil量化后为1.5861538mm，加继承阻焊模型约1.606169mm；这是设计模型，不是实际成品测厚或工厂放行。

核实当前安装包pro-api的 getCurrent/overwrite/savePhysicalStackingConfiguration 是空实现/直接返回false；原型源码已保存。安装包PCB解码器将原生thickness除以10，界面再mil2mm(model×10)，写入方向为mm2mil(mm)/10再编码×10。因此该版本**原生盘值实际使用mil**，CLI TLayerPhys“0.1mm”文档注释与已安装实现不同；不是靠数值外观猜单位。只读源码证据含文件SHA与偏移，没有修改安装包、外部权限或扩展身份。

新副本通过普通项目文件修改LAYER_PHYS和两个新介质LAYER记录，打开编辑器前先解析/逐类比较。第一次写入被EOF缺换行的解析检查拦下，未打开编辑器；已保存失败边界并只重建本轮尚未打开的副本。修复后才正常原生打开、保存、关闭、重开。所有铜线/过孔/焊盘/器件/网络/规则/地铜原始记录及API捕获与r4相同，其他17文件相同。

完整原生DRC仍为 **0间距 / 0物理 / 62未连通（12网）**。230件、1079焊盘、3264 API线+28原生微短线、519孔。物理结构完整性已关闭；实际工厂工艺、材料损耗、触摸寄生和I²S回流仍未关闭。损耗切线没有原厂所选材料的依据，保持null/未验证，不得将编辑器可能显示的零默认值当作无损介质或跑出SI签核结论。

源PCB SHA：d21fb5545e51bb27ff5a2e86405c7ea50c80e5664c186543843ede1704eb3fcb。
原生ZIP：native-4L-230-0clear-62open-stackup-r5-20261021-CANDIDATE.zip，SHA e9659c25786d6b5133ffb7b84adbabdee87962e0112ca31d948b5f21556f835b，已核CRC和19文件SHA。

继续以本版做回流和12网布线，勿重放prepare/finalize。r4平面铜和地铜图仍准确，因为本轮逐类证明平面记录完全未变；物理顺序以本版为准。r6音频试布为离线工作，不能因为候选有路径就应用；需真实地铜复核及完整原生DRC。采购/制造基线 CURRENT-STATE.json 仍为保留的r3/74项，没有自动改成已下单的四层工艺。
