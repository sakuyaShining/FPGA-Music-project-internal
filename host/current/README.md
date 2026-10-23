# 上位机开发候选：ca03 / 11版

本目录保存ca03的`host-workbench-20261015-11`源码、字体、测试及协议辅助脚本，文件身份见`../../project/versions/engineering-sources-20261023.json`。原`tools/host/README.md`含10版历史描述，11版身份以随源`host_version.json`及本目录为准。

```powershell
python tools/scripts/engineering.py test --area host --output D:/FPGA-Project/review/my-host-run
```

依赖Python、PyQt5、pyserial、numpy。统一入口在新的导出目录执行离线Qt/模拟协议测试，设置offscreen并补齐PYTHONPATH。GUI启动使用导出目录中的`tools/host/dsp_gui.py`；连接实体串口需要明确硬件操作授权。

原作者会话为`01a130bf-52f5-7311-b486-1270b5a0e3d4`，当前暂停，新的维护者需认领任务。此版本不自动代表与`fpga/current`协议已接合；旧09固件兼容记录不适用于新FPGA源。6e70等其他候选保留在历史清单中，未批量合并。
