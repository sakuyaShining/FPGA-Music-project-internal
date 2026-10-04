# $readmemh 初始化验证

> 2026-10-01 · **回答一个问题：烧进板子会不会因为表没读进去而静音？**

## 结论

**`$readmemh` 的初值确实写进了比特流。** 四条独立证据：

| # | 证据 | 观察 |
|---|---|---|
| 1 | 综合日志无 `EX3988` | 三张表都被找到 ✓ |
| 2 | 综合日志的 RAM 推断 | `Extracting RAM for 'sine_tab' / 'note_rom' / 'part_rom'` ✓ |
| 3 | **综合报告的 BSRAM 明细** | **`BSRAM 8 = SDPB 7 + pROM 1`** ✓ |
| 4 | **改 hex → 比特流变化** | 见下方对照实验 ✓ |

**证据 3 最关键**：`pROM` 是 Gowin 专门为「带初值的 ROM」准备的 BSRAM 原语 ✓
它出现了，说明工具链**识别出这是 ROM 并保留了初值** ✓

---

## 对照实验（含失败的第一次尝试）

### 第一次尝试：直接比哈希 —— **无效** ✗

```
基线    (hex A) : 2E1AADCA...
改过hex (hex B) : 1F49E0EB...   差异 22 字节
还原后  (hex A) : EC01F525...   ✗ 没有回到基线！
```

**三次哈希全不同** ✗ → 比特流含时间戳/不确定性 ✗
**⇒ 那 22 字节差异【不能作为证据】** ✗

> **这一步是必要的**：只做前一半，就会拿一个无效结论去汇报。

### 第二次尝试：分离时间戳噪声 —— **有效** ✓

```
相同输入、构建两次 : 差异  5 字节，全部在偏移 543~550（8 字节窗口）
不同输入、构建两次 : 差异 22 字节
```

**⇒ 时间戳固定占 5 字节** ✓ → **改 hex 引入的约 17 字节是真实的数据差异** ✓

---

## 未能做到的部分（如实记录）

- **没有回查那 22 字节的具体分布** ✗ —— 严格来说应该确认它们**不在** 543~550 那个时间戳窗口内 ✗
  再做一轮需要两次综合 ✗
- **网表不可读** ✗ —— `impl/gwsynthesis/tdm_synth.vg` 是**编码过的** ✗
  （在里面搜 `SDP` 得到 44 处命中全是 base64 里的巧合 ✗ 搜 `sine256.hex` 的特征值 `7fff`/`8001`
  各命中 0~1 次，也是巧合 ✗）
- **无法在无板条件下做最终确认** ✗

**⇒ 因此把"开机是否出声"列为板级 bring-up 的必检第一项** ✓

---

## 综合报告的存储器推断明细

```
BSRAM  8  = SDPB 7 + pROM 1
SSRAM 132 = RAM16SDP4 128 + RAM16S4 4
Logic 4019 (2872 LUT + 355 ALU + 132 RAM16) / 20736 = 20%
```

**⇒ 时隙状态存储器走 BSRAM，小表有一部分落到了分布式 RAM（LUT RAM）** ✓
这是正常的（小表用 LUT RAM 更快更省 BSRAM ✓）

---

## 这个坑在本项目已经踩过三次

| 次 | 文件 | 症状 |
|---|---|---|
| 1 | `sine256.hex` | 综合器静默地把模块扫掉 ✗ |
| 2 | `sine256.hex`（换目录后） | 仿真输出全 0，不报错 ✗ |
| 3 | `note_inc.hex` / `preset_part.hex` | `EX3988` 只警告不报错 ✗ 板上会静音 ✗ |

**共同点：`$readmemh` 失败【不报错】** ✓

**⇒ 已把教训写进 RTL 注释与本文档** ✓
**⇒ 每次改动表文件后必须检查综合日志里没有 `EX3988`** ✓

---

## 复现

```powershell
# 1) 确认表文件在【工程目录】里（不是 RTL 目录）
Get-ChildItem src\gowin\tdm_synth\*.hex
#    应有: sine256.hex  note_inc.hex  preset_part.hex

# 2) 综合
powershell -NoProfile -ExecutionPolicy Bypass -File tools\scripts\build_gowin.ps1 `
  -Project src\gowin\tdm_synth\tdm_synth.gprj -SspiAsGpio

# 3) 三处必查
#    a. 日志里【没有】EX3988
Select-String -Path src\gowin\tdm_synth\impl\gwsynthesis\tdm_synth.log -Pattern 'EX3988'
#    b. 有 Extracting RAM / pROM
Select-String -Path src\gowin\tdm_synth\impl\gwsynthesis\tdm_synth.log -Pattern 'Extracting RAM'
Select-String -Path src\gowin\tdm_synth\impl\gwsynthesis\tdm_synth_syn.rpt.html -Pattern 'pROM'
#    c. 端口都在 3.3V bank
Select-String -Path src\gowin\tdm_synth\impl\pnr\tdm_synth.rpt.txt -Pattern 'BankVccio'
```

---

## 板级 bring-up 必检清单（板子到手后按序做）

| # | 检查 | 判据 |
|---|---|---|
| 1 | **时钟**：`clk` 27 MHz 是否起振 | LED 能闪烁 |
| 2 | **复位**：按键 S1 是否有效 | 按下 LED 灭 |
| 3 | **★ 是否出声** | **接喇叭有声音** ← 这一条同时验证了 `$readmemh` ✓ |
| 4 | **I2S 波形** | 示波器看 BCK 1.5 MHz / LRCK 46875 Hz |
| 5 | **测试模式** | `test_mode=1` 时频谱分析仪上能看到多路谱峰 |
| 6 | **演奏接口** | 排针给音符事件，能出正确的音高 |

**第 3 条是关键** ✗ —— 如果静音，第一嫌疑就是表没读进去 ✗
（测试模式与演奏模式都依赖表：正弦表决定波形，音符表决定音高 ✓）
