# 现有Nano的TF接口与录放采购边界

2026-10-27。拥有的Tang Nano20K自带J7 TF卡座，Nano3921官方原理图第5页已核。连接为DAT2→FPGA80、DAT3/SPI_CS→81、CMD/SPI_MOSI→82、CLK→83（22Ω串联）、DAT0/SPI_MISO→84、DAT1→85，供电3.3V；5条数据/命令线上有10k上拉，去耦4.7μF。证据图Nano20K-TF-proof-current.png与源PDF SHA见JSON。

由具体原理图证明：采用现有板载卡座时，不再采购一块外部FPGA侧TF读卡模块。TF卡仍需购买；EEPROM用于乐器定义保存，不能因此删除。Nano的码流Flash也不能当作空闲录音空间。

实际PCM录放、块读写/缓存、写忙间隙、文件格式与现场/曲谱混音未签收；不能以“有卡座”关闭录放功能或10ms目标。SPI模式与SDIO模式由最终产品驱动/CST确定，当前仅列已存在电气连接，不在本聊天修改RTL、格式化卡或烧录。

电脑准备/导出卡文件的USB读卡器候选：[川宇C289，DFRobot SKU FIT0548](https://www.dfrobot.com.cn/goods-1605.html)，网页价8元，数量1。实际库存数量、清远运费/发货未确认。它用于准备/导出，不是核心运行依赖；若用户实际已有可用读卡设备可据实去重，当前不暗算已拥有。

存储卡检索的两条原厂商城结果已明确下架：[FIT0570/32GB](https://www.dfrobot.com.cn/goods-1708.html)、[FIT0394/16GB](https://www.dfrobot.com.cn/goods-1037.html)，均不列可购买项，不以旧介绍/关联推荐冒充现货。卡的准确可买SKU、人民币价和交期仍需继续核对。

来源：[Sipeed原厂Nano20K](https://wiki.sipeed.com/hardware/en/tang/tang-nano-20k/nano-20k.html)及本地官方3921原理图。没有借板载单声道功放替代PCM5122/AUX。
