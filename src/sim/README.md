# 仿真

Testbench 文件（`*_tb.v` / `tb_*.v`）。

**铁律：新模块先仿真再上板。**

---

## 一、工具

| 工具 | 位置 | 作用 |
|---|---|---|
| `iverilog` | `D:\iverilog\bin\iverilog.exe` | 编译 Verilog（仿真用，**不是**综合工具） |
| `vvp` | `D:\iverilog\bin\vvp.exe` | 运行仿真 |
| `GTKWave` | `D:\iverilog\bin\gtkwave.exe` | 看波形 |

版本：**Icarus Verilog 14.0**（2026-08-04 构建，官方安装包自带 GTKWave）。

> ⚠️ **它们不在 PATH 里**（安装时没勾"加入环境变量"）。
> `sim.cmd` 会**只在当前会话**临时把 `D:\iverilog\bin` 加进 PATH，
> **不改注册表**。这样既方便，又不动系统环境。

---

## 二、一条命令跑完编译 → 仿真 → 看波形

```cmd
tools\scripts\sim.cmd  src\sim\tb_你的模块.v  src\rtl\你的模块.v
```

它做三件事：

1. `iverilog -g2005 -Wall -o sim_build\sim.vvp <你的文件...>`
2. 在 `sim_build\` 里 `vvp sim.vvp` 跑仿真
3. 找 `sim_build\` 下最新的 `.vcd`，用 GTKWave 打开

**在纯脚本里调用时**（输出被管道/文件接住时），先设环境变量跳过 GTKWave，
否则图形进程会占住管道：

```cmd
set SIM_NOWAVE=1
tools\scripts\sim.cmd  src\sim\tb_hello_tick.v src\sim\hello_tick.v
```

---

## 三、本目录的文件

| 文件 | 用途 |
|---|---|
| `hello_tick.v` | **入门例子**：每 N 个时钟产生一个使能脉冲（= UART 波特率发生器 = I2S 位时钟内核） |
| `tb_hello_tick.v` | 上面那个的自检式 testbench，**照着它抄** |
| `tb_template.v` | Testbench 模板（复制改名，填空即可） |

先跑通例子，建立手感：

```cmd
tools\scripts\sim.cmd  src\sim\tb_hello_tick.v src\sim\hello_tick.v
```

---

## 四、写 Testbench 的三条要点

### 1. 三个必需部分

| 部分 | 少了会怎样 |
|---|---|
| **时钟** `always #(周期/2) clk = ~clk;` | 时序逻辑根本不动作 |
| **激励** `initial` 里给输入，结尾必须 `$finish` | 仿真跑到超时上限，卡住 |
| **录波形** `$dumpfile` + `$dumpvars` | GTKWave 打开是一片空白 |

### 2. 信号方向口诀

> 被测模块的 **input** → testbench 里用 **`reg`**（我要驱动它）
> 被测模块的 **output** → testbench 里用 **`wire`**（我要观察它）

### 3. ⚠️ 避开竞争（race）

被测模块在 `posedge clk` 更新，检查逻辑如果也在 `posedge clk` 读，
读到的是"更新前"还是"更新后"——**Verilog 标准不保证**，会出随机错误。

**本项目统一做法：检查逻辑走 `negedge clk`。** 上升沿更新、下降沿检查，
中间隔半个周期，值一定稳定。

---

## 五、两种仿真用法，第二种才是专业做法

| | 做什么 | 什么时候用 |
|---|---|---|
| ① **看波形** | 录 VCD，用眼睛在 GTKWave 里看 | 第一次接触、或者调试想不通的问题 |
| ② **自检** | 让仿真器打印 `PASS` / `FAIL` | **每次改代码都跑**，几百个用例眼睛看不过来 |

**`tb_hello_tick.v` 两种都做了**，照它抄。

### 给自己造一次"仿真抓 bug"的经历

改 `hello_tick.v` 里这一行：

```verilog
else if (cnt == DIV[15:0] - 16'd1) begin     // ← 把 16'd1 删掉试试
```

改成 `cnt == DIV[15:0]`，重跑仿真。自检会立刻报出间隔变成了 11 拍。

**这就是"仿真发现 bug"**——比烧到板子上、盯着一块不亮的屏猜，快一百倍。

---

## 六、目录约定

- 仿真产物全部落在项目根的 `sim_build\`（**已可安全删除**，随时重建）
- 设计文件在 `src/rtl/`，testbench 在本目录
- 编译时**两个都要给**：`sim.cmd <tb文件> <设计文件...>`
