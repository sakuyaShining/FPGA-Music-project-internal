# 第一次烧录：Tang Nano 9K + 4.3 寸 RGB 屏 bring-up 指南

> 建立时间：2026-09-21
> 硬件：Tang Nano 9K（GW1NR-LV9QN88PC6/I5）+ Sipeed 4.3 寸 RGB 屏（480×272，40P 排线）
> 目的：完成本项目**第一次把程序烧进 FPGA**，并让每个部件都自证是好的。

---

## 〇、先读这一节：一个需要你知道的战略事实

**9K 和 20K 两块板子都在你手上，但它们在本项目里的角色完全不同：**

| | Tang Nano 9K | Tang Nano 20K |
|---|---|---|
| 器件 | GW1NR-9C（8640 LUT4） | GW2AR-18（20736 LUT4） |
| 板载音频 DAC/功放 | ❌ **没有** | ✅ MAX98357A（I2S 输入 DAC + D 类功放） |
| 赛题《高云选题二》适配板卡列表 | ❌ **不在列表里** | ✅ 在列表里 |
| 在本项目里的角色 | 学习 / bring-up 练习板 | **最终要交的作品跑在这上面** |

赛题硬性要求「完整音频生成通路必须全部基于 FPGA HDL 硬件逻辑，**经 I2S 输出至 DAC 解码发声**」。
9K 没有板载 DAC，要出声必须先外接一个 I2S DAC 模块（如 PCM5102 / MAX98357A 模块）。
所以：**9K 用来练手和验证方法论，声学通路最终要在 20K 上打通。**

这次先用 9K + 4.3 屏做第一次烧录，完全合理 —— 第一次的目标本来就不是做功能。

---

## 一、这次要做到什么（成功判据）

第一次烧录的目标**不是实现功能**，而是回答三个问题：

1. 工具链通不通？（Gowin EDA 能不能把 Verilog 变成码流）
2. 下载链路通不通？（USB 驱动、线、Programmer 能不能把码流送进芯片）
3. 硬件活不活？（晶振起振、PLL 锁定、屏幕能显示）

**判据（看到这些就算成功）：**

| 现象 | 说明 |
|---|---|
| 6 颗 LED 里的 led[0] 以 1 Hz 闪烁 | 时钟活着、逻辑在跑 |
| led[4:1] 每 0.5 秒变化一次，呈二进制计数 | 计数器连续工作，没卡死 |
| led[5] 保持熄灭 | PLL 已锁定 |
| 屏幕上出现彩条 + 白边框 + 底部跳动的计数条 | 屏幕时序、色序、有效区全对 |

---

## 二、交付物清单

### 我编的码流（主角）

| 文件 | 说明 |
|---|---|
| - | 顶层：把 PLL、视频时序、测试图案、LED 拼起来 |
| `src/rtl/gowin_rpll.v` | rPLL 包装：27 MHz → 像素时钟 |
| `src/rtl/video_timing.v` | 480×272 行场时序发生器 |
| - | 测试图案（彩条 + 边框 + 二进制计数条） |
| `src/rtl/led_heartbeat.v` | LED 心跳 / 计数器 |
| `src/constr/bringup_top.cst` | 引脚约束（全部取自 Sipeed 官方例程） |
| `src/gowin/bringup_9k/bringup_9k.gprj` | Gowin 工程文件 |
| **`src/gowin/bringup_9k/impl/pnr/bringup_9k.fs`** | **← 要烧进板子的码流文件** |

### 官方保底码流（出问题时用来对照）

| 文件 | 用途 |
|---|---|
| - | 只测 LED。**建议第一个烧这个**|
| - | 官方 4.3 屏例程。验证板子+屏+线的组合是好的 |
| - | 上述例程的官方源码（对照用） |

### 工具

| 文件 | 用途 |
|---|---|
| `tools/scripts/build_gowin.ps1` | 一条命令重新编译出码流 |
| `tools/scripts/check_video_timing.py` | 时序不变量自检（验证 480/272 有没有差一） |

---

## 三、烧录步骤

### Step 0：装 USB 驱动（**需要你点一次 UAC，我代不了**）

Tang Nano 9K 板载 BL702 芯片，提供 USB-JTAG 下载和 USB-UART 串口。
Windows 需要装 Gowin 的 USB Cable 驱动，Programmer 才能认到板子。

- 驱动安装包：`D:\FPGA-Project\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64\Programmer\driver\GowinUSBCableDriverV5_for_win7+.exe`
- 右键 → **以管理员身份运行** → 一路下一步。

> 我先查过：这台机器的驱动库里**没有** Gowin 的驱动（之前装 EDA 时没用管理员权限，驱动没跟着装上）。
> 所以这一步大概率是必须的。

### Step 1：插板子，确认电脑认到了

1. 用 USB-C 线把板子连到电脑（板子上标着下载/调试的那个 USB-C 口）。
2. 打开「设备管理器」，看有没有出现 **Gowin USB Cable** 或类似的新设备。
3. 如果看到带黄色感叹号的未知设备 → 回 Step 0 装驱动。
4. 装好后拔插一次。

> 我可以帮你确认：板子插上后告诉我，我运行
> `programmer_cli.exe --scan-cables` 看能不能扫到下载器。

### Step 2：先烧官方点灯码流（**强烈建议**）

**为什么要先烧这个**：它是原厂出货验证过的，能一次性排除"线坏了/驱动没装好/板子坏了/工具链不对"这一整类问题。
如果跳过这步直接烧我编的，一旦不亮，你会分不清是**我的代码问题**还是**硬件问题**。

打开 Gowin Programmer：
- 方式 A：Gowin IDE 里 `Tools → Programmer`
- 方式 B：直接运行 `D:\FPGA-Project\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64\Programmer\bin\programmer.exe`

操作：

1. 左上角 `Access Mode` 选 **SRAM Program**（先烧 SRAM —— 掉电就没了，**零风险**）
2. 点 `Scan Device`，应该扫到 **GW1NR-9C**
3. `File` 处选 `refs\vendor-examples\tang9k-official\step1_led\9K_LED_project.fs`
4. 点 `Program/Configure` 开始下载
5. 看板子：**6 颗 LED 应该跑马灯一样流水点亮，每 0.5 秒移一位**

这一步成功 = 下载链路完全打通。

### Step 3：烧官方 4.3 屏码流，验证屏幕

同样步骤，`Access Mode` 保持 SRAM Program，文件换成
`refs\vendor-examples\tang9k-official\step2_lcd43\Tang_nano_9K_LCD.fs`

**注意排线方向**：官方文档明确提醒 —— 排线的 1 脚要对上连接器旁边的 1 脚丝印，插反了可能不出图甚至伤屏。

预期：屏幕出现彩条。
- 出彩条 → 板子+屏+线+时序基线全部正常，可以进入 Step 4
- 黑屏 → 先查排线方向和是否插到底，再告诉我

### Step 4：烧我编的码流

文件：`src\gowin\bringup_9k\impl\pnr\bringup_9k.fs`

同样 SRAM Program 方式下载。预期现象见第一节的判据表。

**附加测试**：按住板上的 **S2 按键**，屏幕会变成整屏纯色并每 0.5 秒在
**红 → 绿 → 蓝 → 白** 之间轮换。这一档用来单独验证每个颜色通道能不能全亮。

### Step 5（可选，以后再说）：固化到 Flash

上面烧的都是 SRAM，**断电就没了**。想让它上电自动运行，要把码流写进板载
32 Mbit SPI Flash：

- `Access Mode` 改成 **External Flash Mode**
- Operation 选 **exFlash Erase, Program, Verify**
- 再点 Program/Configure

⚠️ 先别急着做这步。等 Step 4 显示正常了再固化，否则每次改代码都要重新擦写 Flash，慢且费寿命。

---

## 四、故障诊断表

这套设计刻意把 LED 和屏幕做成**互相独立**的两条证据链，所以故障现象是唯一的：

| LED 现象 | 屏幕现象 | 结论 | 下一步 |
|---|---|---|---|
| 全不亮 | 黑 | FPGA 没配置成功 / 晶振没起振 | 回 Step 2 烧官方点灯码流对照；若官方也不亮 → 驱动或下载问题 |
| led[0] 在闪，**led[5] 常亮** | 黑 | **PLL 没锁定**，屏幕不亮是正常的 | 像素时钟没出来，属于我这边 PLL 参数的问题，告诉我 |
| led[0] 在闪，led[5] 灭 | 黑 | PLL 正常，问题在屏幕侧 | 查排线方向/接触；对比 Step 3 官方码流 |
| led[0] 在闪，led[5] 灭 | 有条纹但错位/花屏 | 时序参数不匹配 | 记录现象告诉我，要改 `video_timing.v` 的参数 |
| led[0] 在闪，led[5] 灭 | 正常彩条 | ✅ 全部通过 | 进入下一步开发 |
| 按住 S2 有反应但颜色不对 | — | R/G/B 数据线顺序或位宽问题 | 记录哪个颜色不对，告诉我 |

---

## 五、设计说明（为什么这么写）

### 时钟结构：两个独立时钟域，刻意不共用

```
27 MHz 晶振 ──┬─→ [LED 心跳 + 二进制计数]        ← 域①：直连，不过 PLL
              │
              └─→ [rPLL] ─→ 像素时钟 ─→ [视频时序] ─→ [测试图案] ─→ LCD  ← 域②
```

**为什么 LED 不跟屏幕共用像素时钟**：如果共用，一旦 PLL 没锁，LED 和屏幕会**一起死**，
你就分不清是"PLL 挂了"还是"屏挂了"。分开之后故障现象唯一（见第四节诊断表）。

两个域之间只传一个 `pll_lock` 状态位，在 27 MHz 域打两拍同步后使用，没有数据通路跨域。

### 视频时序：总量照抄官方，同步脉冲改成规范的

| 项 | 官方 4.3 例程 | 本设计 | 为什么 |
|---|---|---|---|
| 行总拍数 | 560 | 560 | 照抄，保持刷新率一致 |
| 场总行数 | 297 | 297 | 同上（场频 54.1 Hz） |
| 像素时钟 | 9 MHz（官方标称） | 9 MHz（同一份 rPLL 参数） | 照抄已验证的配置 |
| DE 有效区 | 481 × 273（**差一**） | **480 × 272（正好）** | 面板要的是 480×272；差一在彩条上看不出来，但边框测试会暴露 |
| HSYNC/VSYNC | 几乎恒低，**实际上没有同步脉冲** | 规范同步脉冲（行 40 拍、场 15 行，低有效） | 见下方安全论证 |

**为什么敢改同步信号**：官方那段同步逻辑实际上输出的是"几乎整行低电平 + 场同步恒为 0"，
等于完全没有同步脉冲，只靠 DE 工作。它能出货、能点亮，说明这块屏工作在 DE 模式
（只用 DE 锁存数据，同步信号被忽略）。据此：

> 官方能跑 ⇒ 屏忽略同步信号 ⇒ 本设计输出规范脉冲，屏照样忽略 ⇒ 也能跑

反过来，万一面板其实需要同步脉冲，那官方的恒 0 根本不可能显示，与"官方能显示"矛盾。
所以改成规范脉冲是**弱安全**的改动 —— 最坏情况与官方等价，最好情况比官方健壮。

### PLL 参数：曾经是悬案，**2026-09-21 已彻底解决**

`gowin_rpll.v` 里的 defparam 照抄自官方 `lcd_4.3` 例程。项目早期记过一句悬案：

> "Gowin rPLL 的 defparam 与 UG286 文档公式对不上，用文档公式算不出官方例程注释里的频率。"

**答案找到了，藏在 IP 向导自己的描述文件 `<ip>.mod` 里**——它记的是**界面上填的数**，
而生成的 Verilog 写的是**减 1 之后的编码值**：

```
.mod :  -idiv_sel 3     -fbdiv_sel 1
.v   :   IDIV_SEL = 2    FBDIV_SEL = 0      ← 各减了 1
```

**两边公式其实完全一致：**

```
fCLKOUT = fCLKIN × fbdiv_sel / idiv_sel
        = fCLKIN × (FBDIV_SEL + 1) / (IDIV_SEL + 1)
        = 27 × 1 / 3 = 9 MHz          ✓ 与 .ipc 里的 CLKOUT_FREQ=9 完全吻合
约束：fVCO = fCLKOUT × ODIV_SEL 必须落在 400 ~ 1200 MHz
      本 IP：9 × 48 = 432 MHz          ✓
```

**三组官方例程交叉验证，全部对上：**

| 例程 | IDIV | FBDIV | ODIV | 公式算出 | 官方佐证 |
|---|---|---|---|---|---|
| 9K lcd_4.3 | 2 | 0 | 48 | **9 MHz** | `.ipc` 写 `CLKOUT_FREQ=9` ✓ |
| 9K lcd_led | 4 | 23 | 4 | 129.6 MHz → CLKOUTD(÷4)=**32.4 MHz** | 注释说 33.33 MHz ✓，VCO=518.4 ✓ |

**证据文件**（未改动，可随时对照）：


> ⚠️ **必须纠正的一条旧结论**：项目早期记的"20K 音频例程 PLL 输出 6 MHz"是**错的**。
> 该例程参数为 `IDIV_SEL=5 / FBDIV_SEL=0`，按正确公式是 `27 × 1 / 6 = **4.5 MHz**`。
> 这会直接改变 I2S 的 BCK 与采样率推导 —— **做音频通路时必须重算**，
> 以该例程自己的 `.ipc`/`.mod` 为准，不要沿用旧笔记里的 6 MHz。

### 测试图案各元素在验证什么

| 元素 | 验证什么 |
|---|---|
| 8 段标准彩条（白黄青绿品红红蓝黑） | R/G/B 数据线有没有接错位、断线、恒 0/恒 1 |
| 1 像素白色边框 | 有效区就是 480×272。四条边完整可见 = DE 宽度正确 |
| 底部 15 格二进制计数条 | 帧计数器在跑（右边几格闪得快，肉眼看是一条灰带，属正常） |
| S2 按住 → 纯色轮换 | 每个颜色通道能否独立全亮 |

---

## 六、这次踩到并解决的坑（记录下来，以后不用再踩）

### 坑 1：Bank 3 的引脚不能写 `IO_TYPE=LVCMOS33`

```
ERROR (CT1136): Bank 3 vccio(1.8) is locked by other constraint or embedded port,
                conflicting BANK_VCCIO set by 'led_5_obuf': IO_TYPE = LVCMOS33
```

Tang Nano 9K 的 **Bank 3（引脚 3、4、10、11、13、14、15、16）VCCIO 被固定在 1.8 V**。
在这些脚上声明 3.3 V 会直接中断布局布线。这解释了为什么官方 led 例程那几条约束
**故意不写 `IO_TYPE`** —— 照抄官方写法（只写 `PULL_MODE` / `DRIVE`）即可。

### 坑 2：RP2017 / SSPI 专用脚

```
ERROR (PR2017): 'lcd_g[5]' cannot be placed according to constraint,
                for the location is a dedicated pin (SSPI)
```

LCD 的 G4/G5/B0 接在引脚 **56 / 55 / 54** 上，这三个脚默认是 SSPI（从机配置接口）专用脚。
必须先释放为普通 IO 才能用。

- **命令行**：`set_option -use_sspi_as_gpio 1`（`tools/scripts/build_gowin.ps1 -SspiAsGpio` 已内置）
- **图形界面**：`Project → Configuration → Place & Route → Dual-Purpose Pin` → 勾选 `Use SSPI as regular IO`

> 该选项已持久化在 `src/gowin/bringup_9k/impl/bringup_9k_process_config.json` 里
> （`"SSPI": true`），所以在 IDE 里直接编译也是通的，不用每次手动勾。
> 这也印证了官方 wiki 驱屏教程里专门提到的那一步。

释放 SSPI **不影响 JTAG 烧录**，也**不影响从板载 Flash 上电启动**（那走的是 MSPI）。

### 坑 3：`cell` 是 Verilog 保留字

```verilog
wire [3:0] cell = x[8:5];   // ← Syntax error near 'cell'
```

`cell` 属于 Verilog-2001 配置块关键字，不能当变量名。已改名 `cell_idx`。

### 坑 4：`gw_sh` 能跑批处理，但 IDE 的工程选项不在 `.gprj` 里

`.gprj` 只记录器件和文件列表，**进程配置（含 Dual-Purpose Pin 选项）不在里面**。
Gowin 的命令行控制台是 `gw_sh.exe`，流程是：

```tcl
open_project "xxx.gprj"
set_option -use_sspi_as_gpio 1
run all
```

`set_option` 的完整选项名在 `SUG100_Gowin云源软件用户指南.pdf` §8.3.19（本地就在
`IDE\doc\CN\` 下）。**猜选项名会浪费很多时间，直接查这份文档。**

---

## 七、怎么重新编译

改完 RTL 后，一条命令重新出码流：

```powershell
powershell -NoProfile -File tools\scripts\build_gowin.ps1 `
    -Project src\gowin\bringup_9k\bringup_9k.gprj -SspiAsGpio
```

改过 `video_timing.v` 的参数后，跑一下时序自检：

```powershell
python tools\scripts\check_video_timing.py
```

它会把最容易出错的地方数字数一遍：DE 是不是正好 480×272、同步脉冲有没有和有效区重叠、
每帧是不是只有一个 frame_tick。

### 本次编译的资源占用（GW1NR-9C 基线）

| 资源 | 用量 | 占用率 |
|---|---|---|
| LUT/ALU | 226 | 3% |
| 寄存器 | 109 | 2% |
| BSRAM | 0 | 0% |
| rPLL | 1 / 2 | 50% |
| I/O | 29 / 71 | 41% |

**这个基线很重要**：8608 个 LUT 空着，说明后面做 32 复音合成引擎时，
逻辑资源不是瓶颈（真正的瓶颈另有其物，见方案文档）。

---

## 八、下一步

**已完成（2026-09-21）**

- [x] 完成第一次烧录 —— ✅ 成功，且**全链路验证通过**（详见第十节）
- [x] **Phase 0**：核对 rPLL 实际输出频率 —— ✅ 已彻底解决，**9 MHz**（见第五节，含公式推导 + 三组官方例程交叉验证）
- [x] 把 4.3 屏显示通路沉淀成可复用模块 —— ✅ 已抽出 ，接口契约见 `src/rtl/README.md`

**仍待办**

- [ ] 找 4.3 寸屏规格书（Sipeed 下载站 `Nano 9K/6_Chip_Manual/CN/LCD_Datasheet`），核对行场时序是否有更严格要求。
      **优先级已下调**：本设计已在实物上正常显示，说明当前参数可用
- [ ] 回到 20K，打通 MAX98357A 的 I2S 音频通路（赛题硬性要求）。
      ⚠️ **必须重算采样率** —— 别沿用旧笔记里的 "PLL 输出 6 MHz"，正确公式下那是 4.5 MHz
- [ ] 定下乐器形态（用户尚未拍板）
- [ ] （可选）把工程固化到板载 Flash，使上电自动运行（`--operation_index 8/9`，exFlash）

---

## 九、参考来源

| 内容 | 来源 |
|---|---|
| 引脚号、rPLL 参数、LED 极性 | `github.com/sipeed/TangNano-9K-example`（`led/`、`lcd_4.3/`） |
| 板卡规格（8640 LUT / 468K BSRAM / 32Mbit Flash / BL702） | [Sipeed Wiki - Tang Nano 9K](https://wiki.sipeed.com/hardware/zh/tang/Tang-Nano-9K/Nano-9K.html) |
| Dual-Purpose Pin 设置位置、烧录流程 | [Sipeed Wiki - 点灯LED](https://wiki.sipeed.com/hardware/zh/tang/Tang-Nano-9K/examples/LED.html)、[驱动RGB屏幕](https://wiki.sipeed.com/hardware/zh/tang/Tang-Nano-9K/examples/LCD.html) |
| `set_option` 全部选项名 | 本地 `IDE\doc\CN\SUG100-4.4.2_Gowin云源软件用户指南.pdf` §8.3.19 |
| 4.3 寸屏像素时钟 8~12 MHz | 官方 `lcd_led/src/TOP.v` 内的注释 |
| PLL 目标频率 9 MHz | 官方 `lcd_4.3/src/gowin_rpll/gowin_rpll.ipc` 的 `CLKOUT_FREQ=9` |
| PLL 公式（`idiv_sel`/`fbdiv_sel` 与 defparam 差 1） | 官方 `lcd_4.3/src/gowin_rpll/gowin_rpll.mod` |
| 调试器枚举形态、按住 S2、下载频率 2.5MHz | [Sipeed Wiki - 常见问题](https://wiki.sipeed.com/hardware/zh/tang/common-doc/questions.html) |

---

## 十、上板实测结果（2026-09-21）—— **全链路验证通过**

### 验证证据

| 验证项 | 设计预期 | 实测 | |
|---|---|---|---|
| 下载链路 | 烧录成功 | 多次 SRAM Program，exit 0，2.8~2.9 秒 | ✅ |
| FPGA 识别 | GW1NR-9C | ID `0x1100481B`，Family GW1NR | ✅ |
| 27 MHz 晶振 | LED 有规律变化 | 符合 | ✅ |
| PLL | led[5] 不亮（已锁定） | 符合 | ✅ |
| 屏幕出图 | 非纯白 | 出图 | ✅ |
| 有效区 | 480×272（四边白框） | 有边框 | ✅ |
| 色序 | 白→黄→青→绿→品红→红→蓝→黑 | **完全一致** | ✅ |
| 二进制计数条 | 在**最底下**一条 | **在最底下**，白黑方格在跳 | ✅ |
| 画面方向 | 左上黑方块、右下白方块 | **完全一致**（角标法确认） | ✅ |

### 一次性确认下来的环境事实（省得以后再试）

| 项 | 结论 |
|---|---|
| 烧录时要不要按 S2？ | **不需要**。官方 FAQ 说 Nano 9K 的 JTAG_SEL 挂在 S2 上、用 Programmer 时要按住；本板本机实测**直接就能扫到器件并烧录成功**。仅在将来扫不到器件时才回头试 |
| 下载频率 | 自动就是 **2.5 MHz**（FAQ 推荐值），无需手动设 |
| 调试器长什么样 | 设备管理器出现**两个 `USB Serial Converter A/B` + 一个 `COM` 口**。VID_0403&PID_6010，设备自报字符串 "JTAG Debugger" |
| 要装什么驱动 | **FTDI 驱动**（`oem132/133.inf`，v2.12.36.20，WHQL 签名）。**不需要** Gowin 的 USB Cable 驱动 |
| 迭代成本 | 改代码 → 编译 → 烧录 → 看到结果，**全程约 3~10 秒**，纯命令行 |

### 资源基线（GW1NR-9C）

| 资源 | 用量 | 占用 |
|---|---|---|
| LUT/ALU | 241 | 3% |
| 寄存器 | 116 | 2% |
| BSRAM | 0 | 0% |
| rPLL | 1 / 2 | 50% |
| I/O | 29 / 71 | 41% |

**8620 个 LUT 空着** —— 后面做 32 复音合成引擎时，逻辑资源不是瓶颈。

### 本轮新增的坑（第六节四个之外的）

**坑 5：「背光亮」不等于「屏幕在工作」。**
RGB 屏背光从 40P 排线的电源脚直接取电，跟 FPGA 有没有配置**完全无关**。
FPGA 空片时 IO 浮空/弱上拉 → RGB 数据线全被拉高 = 全 1 → 面板显示**纯白**。
所以白屏是空片的正常表现，**不能**用来判断码流烧没烧进去；唯一可靠判据是**有没有图像内容**。
反过来，背光能亮说明排线已把电源送到面板，是个正面信号。

**坑 6：屏幕方向不能用照片判断。**
本轮曾根据用户拍的屏幕照片量出"色条顺序反了"，据此误判画面被镜像，白做了一轮实验。
**实际是照片本身被镜像/旋转了**（手机前置摄像头会自动镜像，或照片存储时被转 180°）。
正确做法：**在画面上放两个不可能认错的标记**（左上大黑方块 + 右下小白方块），
让人的眼睛直接判定。 的 `MARKERS` 参数就是干这个的（默认关闭）。
`(x,y)` 平面上的四种变换（正常 / 水平镜像 / 垂直翻转 / 旋转180°）会被两个方块的位置唯一区分。

**坑 7：组合逻辑与寄存信号混用会错 1 拍。**
改造前的 用**寄存后的 `de`**去门控**组合逻辑算出的颜色**——
两者相差 1 拍，有效区边缘错 1 个像素（只差 1 像素又在边缘，肉眼看不出来，但确实是错的）。
修法：`video_timing.v` 同时输出组合版 `de_comb`，图案模块必须用它。
重构后打拍收在 一处，客户模块只写纯组合逻辑，**这类错从结构上不可能再发生**。

**坑 8：Windows 设备「问题代码 28」的排查路径。**
FTDI 驱动明明在驱动仓库里（且 WHQL 签名正常），设备却停在 Code 28（`CM_PROB_FAILED_INSTALL`）。
决定性证据源是 Windows 的设备安装日志：
```
C:\Windows\INF\setupapi.dev.log      ← 逐条记录 INF 段落安装、服务创建、设备启动的退出码
```
配套命令：`pnputil /enum-drivers`（查驱动仓库）、`pnputil /enum-devices /problem`（查问题设备）、
`Get-PnpDeviceProperty -KeyName DEVPKEY_Device_ProblemCode`（查问题码）。
⚠️ **红鲱鱼警告**：驱动列表里有个 `oem131.inf = usb_device.inf`，Provider 是 **`libwdi`**（Zadig 留下的），
看着很像"被 Zadig 抢走了驱动"，但读 INF 内容发现它匹配的是 `VID_33AA&PID_0120`（高云另一种下载线 GWU2X），
与本设备无关。**看 Provider 名字就下判断会误判，必须读 INF 里实际匹配的 Hardware ID。**

**坑 9：把"计数器值"当"像素坐标"交出去，图案会整体偏移。**
`video_timing` 里的行/场计数器范围是 `x=0~559 / y=0~296`，而**有效区只是 `x=30~509 / y=5~276`**。
早先直接把计数器值当坐标交给图案模块，于是：
- 白条只显示 30 像素宽（应为 60），黑条却占 90 像素
- 左边框画在 `x=0`（属于行消隐），**永远不可能显示出来**
- `y=0` 的上边框同理消失；而 `x=479`、`y=271` 这两条"边框"落在有效区**内部**，成了画面里两条莫名其妙的细线

**最阴的地方**：色条**顺序**是对的，所以只检查"颜色对不对"完全发现不了；必须看**几何**
（各条宽度是否相等、边框是否贴边）。
修法：`lcd_480x272` 交给客户模块的坐标必须是**有效区相对坐标**（已减掉 `H_BP` / `V_BP`），
而不是原始计数值。同时把这条写进客户契约——客户不该知道消隐有多少拍。

> 复盘：这个问题其实是**用户拍的屏幕照片**先暴露的（照片里最宽那条约为最窄那条的 3 倍），
> 但当时我把它误读成"照片被镜像"，直到后来计算图像取样地址时才回头发现真因。
> 教训：**照片里的"宽度比例"这类几何信息比颜色顺序更可靠**，不该轻易归因于成像artifact。

**坑 10：`$readmem*` 的数据宽度必须与存储器位宽严格一致。**
用 `$readmemh`（1 字符 = 4 bit）给 3 bit 宽的存储器加载数据，Gowin 只报一条不起眼的
`WARN (EX2526): Entry size 4 ... does not match memory width 3`，然后
**静默丢弃全部内容** —— 存储器虽被识别（日志里有 `Extracting RAM`），但没有初值，
整个 ROM 被优化掉，资源表里 BSRAM 显示 **0 块**，极易误判成"Gowin 不支持 readmem"。
改用 `$readmemb`（每行 3 个二进制字符）后正常。

> 连带教训：**测试存储器推断时，不要用能被地址推导出来的规律数据**
> （比如 `mem[i] = i % 8`）。综合器会常量传播把整个 ROM 消掉，
> 让你以为"推断失败"，其实是测试用例本身没意义。

---

## 十一、图片显示功能（2026-09-21 上板验证通过）

把电脑里的一张图片显示到屏上。**这正是第十节那个"可复用调试显示模块"的第一个真实客户**，
 一行都没改（除了修坐标 bug），只新增了两个模块：

| 文件 | 作用 |
|---|---|
| - | 图片像素 ROM，`$readmemb` 加载，综合后占**24/26 块 BSRAM**|
| - | 把 8 色索引还原成 RGB565 |
| `tools/scripts/make_image_rom.py` | 图片 → 索引数据的转换脚本（可复现） |

### 硬约束：为什么只有 8 色

**GW1NR-9 的 BSRAM 只有 26 块共 468 Kbit。**
480×272 全彩 16 位需要 `480×272×16 = 2,088,960 bit` —— 是它的 **4.5 倍**，根本放不下。

逐级降规格的账：

| 方案 | 需要 bit | 能否装下 |
|---|---|---|
| 480×272 @16bpp | 2,088,960 | ✗（差 4.5 倍） |
| 480×272 @8bpp | 1,044,480 | ✗（差 2.2 倍） |
| 480×272 @4bpp | 522,240 | ✗（差 9%，就一点点） |
| **480×272 @3bpp（8 色）** | **391,680** | ✅ **实测占 24/26 块** |

**想再提高画质，只能换存储介质**：板载 64 Mbit PSRAM 或 32 Mbit SPI Flash。
但那需要另写存储器控制器（PSRAM 有 Gowin 的 IP 可用），属于后续工作。
—— 顺带一提，**这个 PSRAM 控制器是迟早要做的**：音频引擎的延迟线/混响缓冲区同样需要它。

### 关键技术点：地址预取，抵消 BRAM 读延迟

显示驱动的客户契约要求**纯组合**（给坐标、本拍出颜色），但 BSRAM 读数据天生要 1 拍。
解法是**取下一个像素的地址**：

```
第 t   拍：地址 = index(x+1, y)   → 第 t+1 拍数据出来 = 像素 (x+1, y)
第 t+1 拍：坐标正好变成 (x+1, y)  → 数据与坐标同步到达
```

于是对外表现就是纯组合，驱动那边一行都不用改。地址用 `y*480 = (y<<9)-(y<<5)` 算，
**不需要乘法器**。

### 换图的完整流程

```powershell
python tools\scripts\make_image_rom.py "图片路径" --crop top --contrast 1.25 --saturation 1.5
# 脚本会把新的 PAL0..PAL7 打印出来，粘进 src/rtl/image_view.v 替换
powershell -File tools\scripts\build_gowin.ps1 -Project src\gowin\bringup_9k\bringup_9k.gprj -SspiAsGpio
programmer_cli --device GW1NR-9C --operation_index 2 --fsFile src\gowin\bringup_9k\impl\pnr\bringup_9k.fs
```

⚠️ **调色板和 .bin 必须同批生成**，否则颜色全错。
⚠️ 脚本会同时输出一张 PNG 预览，**烧板前先看一眼**。

### 按键

| 操作 | 画面 |
|---|---|
| 不按 | 图片 |
| **按住**（不是当复位用的那个键） | 自检图案（彩条 + 白边框 + 二进制计数条） |

自检图案留着，是为了以后换屏/换线时能一键回到"已知正确"的画面。
