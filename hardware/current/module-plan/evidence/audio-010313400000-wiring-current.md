# 55元音频候选：逐针连接与17项基线核对

状态：电气接线与逐项核对已有证据，仍不是采购或通电指令。SKU **010313400000 / RPI-PCM5122-Audio-HIFI-HAT-A**，厂家页面本次仍列55元、在售；库存数量、预焊交付清单和清远发货日期未确认。不能套用59元SKU010314600000的资料。

## 原理图确认

对应厂家原理图中，MODE1/ADR2接地，MODE2由R21拉高，ADR1由R14拉高：PCM5122的7位地址是 **0x4D**，线上写/读地址0x9A/0x9B。耳放TPA6130A2另占 **0x60**，线上0xC0/0xC1。低分辨率图中曾将GPIO6的NC误读为MODE2未接，已经由原始PDF放大图纠正；不保留这项假故障。

P1.1/17的3V3标签与板内U6输出VCC不是图中同名电源，不能据此把板内稳压输出当成排针供电。此接线草案不连接P1.1/17；此前“防止并联稳压输出”的具体理由没有证据，已经更正。板内U6只覆盖DAC供电，不覆盖屏幕、触摸和外设的3V3_PERIPH。

## 连接契约

P1均指音频板40针接口的**物理针号**；J5/J6均指Nano20K官方原理图排针号，不凭照片猜方向。最少7个逻辑导体，实际配线还需要紧邻音频时钟的回流地与可靠分配连接，尚未冻结完整线材SKU。

| 信号 | Nano/系统端 | 音频P1端 |
|---|---|---|
| 受保护5V | 外设保险、反接与限流之后的5V_PERIPH | 2 |
| 公共地 | 电源及信号回流地 | 6；BCK/LRCK/DIN旁可用14/34/39 |
| BCK | Nano J5.7 / FPGA56 | 12 / BCM18 |
| DIN | Nano J5.8 / FPGA54 | 40 / BCM21 |
| LRCK | Nano J5.11 / FPGA55 | 35 / BCM19 |
| SDA | Nano J6.10 / FPGA25，**经过断电安全I2C隔离** | 3 / SDA1 |
| SCL | Nano J6.11 / FPGA26，经过同一隔离 | 5 / SCL1 |

不能将原TCA9517及外设3.3V上拉需求省略为两根直接连线。P1.31/BCM6经R4接耳放SD，板上R3已拉高；使用I2C耳放控制时可先不接，不默认新增GPIO。其余未用排针不连，也不能把整排树莓派接口直插Nano。

厂家教程明确：**RCA白左红右是AUX OUT；3.5mm是耳机功放输出，不当作已合格AUX OUT，更没有AUX IN。** 双RCA转接线、实际立体声播放负载及其供电仍需采购，不能假定用户已有音箱。

## 软件与上电验收契约

登记producer当前实际DIV_BCK=16、BCK_PER_LRCK=32；按27MHz推导BCK=1.6875MHz，LRCK=52,734.375Hz，16bit两个声道槽。目前两个槽填相同样本，不能称已验证独立立体声。这里只读源码、记录SHA，没有修改、构建或烧录，也不声称其他工作区没有新实现。

PCM5122当前处于软件控制模式，SCK经R8接地。必须明确配置BCK参考PLL和内部时钟分频，不能把树莓派48kHz驱动配置或硬件模式自动锁定说明直接套用。芯片默认I2S24bit；源码中WS/MSB关系还需与最终采样波形核对。只有证明为LTJ16bit时，Page0/Reg40=0x30才是相应格式设置；这一个寄存器不是完整初始化表。

TPA6130A2的条件启动步骤已经定位：0x60的Reg4低4位版本应为2；Reg2高两位置1先静音；Reg1=0xC0使能两个通道且保持立体声、退出软件关断；Reg3=0x00是正常输出阻抗。确认DAC时钟、读回与静音状态后，才低音量逐步解除静音。不写保留测试寄存器。上述为驱动契约，未对实物执行。

## 原17件的去重边界

详见同目录`audio-010313400000-original17-map-current.json`，每件均关联原网络、候选覆盖或仍需解决的条件。11项已有芯片/供电/泵电容/去耦/静音拓扑对应证据；**6项尚不能去重**：R41/R42、C27/C28的实际RCA输出滤波保护，J12的物理转接，以及R72的DAC3.3V放电负载。模块明确标NC的电容不能当作已焊元件，正常工作电流也不能冒充断电放电保护。

这不是取消旧227件BOM：全部原功能保留。仍待实际装配路径、软件初始化、断电隔离、外设供电、全部附件及700元总价/清远交期闭合后，才形成最终购买清单。实物保持UNMEASURED。

## 来源

- [同SKU商品页](https://spotpear.cn/shop/Raspberry-Pi-5-I2S-PCM5122-DAC-Audio-Card-3.5mm-Earphone-Jack-HAT-A.html)
- [对应厂家教程](https://spotpear.cn/wiki/Raspberry-Pi-5-I2S-PCM5122-DAC-Audio-Card-3.5mm-Earphone-Jack-HAT-A.html)
- 本目录`Spotpear-010313400000-schematic.pdf`，SHA3908e6255a977ca61ef69ab051c34eadaaaf53a2b27b987724adec5006252cbb；`Spotpear-PCM5122-mode-straps-detail-current.png`为放大核对图。
- [TI PCM5122资料](https://www.ti.com/lit/ds/symlink/pcm5122.pdf)，模式/地址、软件三线PLL和Page0Reg40。
- [TI TPA6130A2资料](https://www.ti.com/lit/ds/symlink/tpa6130a2.pdf)，地址和控制/静音/版本寄存器。
