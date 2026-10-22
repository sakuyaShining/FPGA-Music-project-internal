# Gowin EDA 安装记录（已完成）

> 执行日期：2026-09-18
> 结论：**安装成功，全部在 D 盘，C 盘零占用**

---

## 一、回答：能装 D 盘吗？

**能，而且已经装好了，C 盘一点没占。**

| 盘 | 安装前可用 | 安装后可用 | 变化 |
|---|---|---|---|
| C: | 2.4 GB | **2.6 GB** | **+0.2 GB**（反而多了一点，是临时文件被清掉了） |
| D: | 56.3 GB | 53.6 GB | −2.7 GB |

关键做法（这是能装进 D 盘的原因）：
1. 安装包直接下到 `D:\FPGA-Project\downloads`，不经过 C 盘
2. 解压到 `D:\FPGA-Project\installer`
3. **把安装过程的 TEMP/TMP 环境变量指向 `D:\FPGA-Project\temp`**，避免安装器往 C 盘临时目录解压
4. 用 NSIS 的 `/D=` 参数指定安装目录

---

## 二、安装了什么，在哪

### 主程序

| 项 | 路径 |
|---|---|
| **Gowin EDA IDE** | `D:\FPGA-Project\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64\IDE\bin\gw_ide.exe` |
| **Gowin Programmer**（烧录） | `D:\FPGA-Project\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64\Programmer\bin\programmer.exe` |
| USB Cable 驱动 | `...\Programmer\driver\GowinUSBCableDriverV4_for_win7+.exe`（和 V5） |
| 卸载程序 | `...\Gowin_V1.9.11.03_Education_x64\uninst.exe` |

### 快捷方式（安装器自动创建，均已指向 D 盘）

- 桌面：`Gowin_V1.9.11.03 Education (64-bit)`
- 开始菜单：`Gowin\Gowin`、`Gowin\Gowin Programmer`

### 版本与许可

- 版本：**云源软件教育版 V1.9.11.03（64-bit）**
- **无需 License**，不绑定 MAC，无期限

---

## 三、验证结果（逐项实测通过）

| 验证项 | 结果 |
|---|---|
| 安装包 MD5 | ✅ 与官网公布值一致（`e5ed6222...`、`ae8db0e1...`） |
| 文件完整性 | ✅ 6088 个文件，1.85 GB |
| IDE 能否启动 | ✅ 已启动，窗口标题 `GOWIN FPGA Designer - [Start Page]` |
| **器件库是否含我们的芯片** | ✅ **`GW2AR-LV18QN88C8/I7` 在库**（见 `IDE\share\device\device_info.csv`） |
| 器件参数是否吻合 | ✅ 20736 LUT / 15552 FF / 828Kb BSRAM —— 与 Tang Nano 20K 规格完全一致 |
| 快捷方式指向 | ✅ 全部指向 D 盘 |

器件库原文（`device_info.csv`）：
```
gw2ar18c-000,GW2AR-LV18QN88C8/I7,GW2AR,GW2AR-18C,QFN88,LV,C8/I7,8,66,20736,15552,,40Kb,828Kb,,12,2,
```

> 注意：新建工程时，器件选型要选 **GW2AR-18C** 系列 → 封装 **QFN88** → 具体型号 **GW2AR-LV18QN88C8/I7**。

---

## 四、可回收的空间（可选）

安装完成后，以下目录可以删掉，共约 **930 MB**：

| 目录 | 大小 | 说明 |
|---|---|---|
| `D:\FPGA-Project\downloads` | 508 MB | 下载的 zip 压缩包 |
| `D:\FPGA-Project\installer` | 422 MB | 解压出的安装器 exe |

> 想重装时随时可以再下，不急的话先留着也行。

---

## 五、⚠️ 下一步：USB 下载驱动（需要管理员权限）

**这一步绕不开管理员权限**，而且必须在插板子之前做好，否则 Programmer 找不到设备。

驱动位置：
```
D:\FPGA-Project\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64\Programmer\driver\GowinUSBCableDriverV5_for_win7+.exe
```
（V4 是给 win7 更老环境的，一般用 V5）

**安装方式**：双击运行 → 会弹 UAC 提权窗口 → 点【是】→ 按提示装完。
> 我尝试过用命令行提权静默安装，UAC 被取消了。这一步需要你在屏幕上手动点一下【是】，我没法替你点。

**验证驱动是否装好**：插上 Tang Nano 20K（用 USB-C 插标着 **DEBUG-USB2** 的口）后：
- 设备管理器应出现 `Gowin USB Cable`
- 或者 Gowin Programmer 里能看到设备

---

## 六、⚠️ 另一个要提醒你的事：C 盘只剩 2.6 GB

C 盘 146.5 GB 用了 143.9 GB，**只剩 2.6 GB（1.7%）**。这不是小事——Windows 空间过少会导致：
- 系统更新失败
- 休眠/虚拟内存异常
- 程序崩溃、临时文件写不进去

**已发现的几个可回收点（未动，等你决定）**：

| 位置 | 大小 |
|---|---|
| `C:\Users\Sakuya\AppData\Local` | 25.6 GB ← 最大头，需细查 |
| `C:\Users\Sakuya\Downloads` | 705 MB |
| `C:\Users\Sakuya\AppData\Local\Temp` | 576 MB |

**建议**：等你把 IDE 跑通、项目上手之后，我们单独花 20 分钟做一次 C 盘清理。
清理涉及删文件，**我不会擅自动手**——到时候我会先列出清单让你确认。

---

## 七、本次安装的完整文件清单

```
D:\FPGA-Project\
├── downloads\                      (508 MB, 可删)
│   ├── gowin_eda_edu_win.zip
│   └── gowin_programmer_edu_win.zip
├── installer\                      (422 MB, 可删)
│   └── Gowin_V1.9.11.03_Education_x64_win.exe
├── temp\                           (安装临时目录，可清空)
└── Gowin\                          (1854 MB, 主程序)
    └── Gowin_V1.9.11.03_Education\
        └── Gowin_V1.9.11.03_Education_x64\
            ├── IDE\                ← IDE 主程序
            ├── Programmer\         ← 烧录器 + USB 驱动
            └── uninst.exe
```
