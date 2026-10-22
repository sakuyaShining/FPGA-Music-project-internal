# 板级音频实测交付

仅用于Nano20K/GW2AR-LV18QN88C8/I7，profile72/ABI1音频诊断，不是完整产品固件。

**复位按键为S2（87脚），按下高有效**。旧准备说明“S1/87”有编号错误；本轮未改码流的实际引脚。

只采用Gowin操作2 SRAM Program临时配置。该音频镜像本轮已下载并完成限定板上检查，Flash未读写。静音回退镜像本轮未下载。当前硬件测试结束后已停止/静音，断电结束临时配置。

同一台设备本轮UART为COM6、FTDI序列号2025030317B，重新连接须以实际枚举为准。先读身份，再指定测试；脚本不会下载FPGA。

```powershell
python notes/board-audio-hardware-20261017/package/board_check.py --port COM6
python notes/board-audio-hardware-20261017/package/board_check.py --port COM6 --case 1 --output board-results/retest1
```

本轮六项回读、短音补测、实体S2复位及恢复演奏通过，用户能听到且暂未发现异常；不等于完整整机、模拟音质、外部I²S边沿、屏幕/传感或持久录音已验。请看73号报告与父目录CURRENT/delivery。
