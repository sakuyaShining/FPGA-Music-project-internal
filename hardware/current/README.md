# 当前硬件保存工程

`native/`包含当前保存的U9ControlWork原生工程，包括工程描述、PCB、全部原理图及面板；逐文件身份见`../../project/versions/engineering-sources-20261023.json`。PCB身份`e098c5db…`，作者施工记录47项未连通、13网、227件、616孔。保留37项旧检查点仍可从历史档案恢复。

`context/`保存当前施工、DRC/参考检查与采购上下文；`interface-references/`保存引脚参考。上下文中的绝对路径和session只是原工作区出处，不可复用会话或重放事务。采购文件包含历史表及草稿，按`context/purchase-preparation-20261021-r1/current-board-procurement.json`解释；旧CPL未随全部改位重导出，不能直接下单。

```powershell
python tools/scripts/engineering.py export --area hardware --output D:/FPGA-Project/review/my-hardware
```

校验通过后在自己的副本中打开`native/`原生工程，创建该副本的新会话并核对实际工程身份。主机原D盘/06df目录不属于新协作者可写路径。当前施工owner为会话`01a15ee5-fa24-7501-8475-ad28a0f08939`；本次发布只核对保存文件和恢复字节，没有重新执行CAD DRC。

保留J10，取消J11；接口改动需双方确认。仍有未连通及参考/装配/屏幕线束资格缺口，实物未测，制造未放行。导出不启动CAD、不应用施工脚本。
