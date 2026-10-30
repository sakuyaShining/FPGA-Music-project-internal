# 电源保护温度约束，负载预算尚未完成

冻结R2输入身份与10个电源相关器件引脚已只读核对。F1实际为MF-MSMF110/16-2，厂家非X型号行的Ihold在23/40/50/60/70/85°C分别为1.10/0.95/0.87/0.80/0.71/0.60A。已保存[Bourns官方数据表](https://www.bourns.com/docs/product-datasheets/mf-msmf.pdf)，第9页渲染核对，不能混用/16X行。PDF SHA见POWER-CONSTRAINTS.json。

原R2压降检查中的J13 0.5A是声明式估计输入。在此条件下60°C与PTC hold的算术余量为0.30A；23°C R1max0.21Ω对应0.105V条件压降。它们不构成实物电流、全温压降或温升保证。原TPS2553 23.7kΩ±1%限流约1.002–1.184A保持不变；外部适配器3A铭牌不意味着板内通道可供3A。

Nano USB-C与C88 J13为两条5V供电支路，J5.1为空；3V3_IO由Nano头提供，U17 EN在该网。J10及两颗LDO位于保护后的5V_PERIPH。JSON内逐件rail incidence仅表示真实源网络连接，不是功耗测量。仍缺Nano动态负载、实际屏/触控稳态与启动电流、线束压降、外壳温升与LDO热条件。精确国内电源SKU、完整分支线束及含运价格仍未确认，700元全预算未签收。

可在仓库运行python -B hardware/sourcing-closure-20261030/power-envelope-20261030/extract_power_constraints.py。只读冻结源与保存的PDF，输出同目录条件报告；无CAD更改、换料或制造放行。并非完整供电选型完成。
