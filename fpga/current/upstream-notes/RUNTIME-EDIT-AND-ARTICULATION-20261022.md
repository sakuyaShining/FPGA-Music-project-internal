# 运行时表 / 现有编辑界面 / EEPROM / 激发模式规则 · 2026-10-22

四个问题：① 为什么搬到 `instrument_table`　② 原有编辑界面长什么样　③ 接 EEPROM 是什么　④ 激发模式规则怎么定。

---

## 0. 先更正我上一轮的两个错误

| 我上次说 | 实际 | 依据 |
|---|---|---|
| `s_lvl` 满量程 65535，30000 = 45.8% | **满量程 32768，30000 = 91.6%** | `osc_env.v:42`「电平 Q1.15 无符号：0 = 静音，**32768 = 满幅（1.0）**」、`:80` `FULL = 32768` |
| 「2 bank = 激发模式」 | **bank 是双缓冲的前台/后台，与激发模式无关** | `instrument_table.v` 全文：写 `!banks[slot]`、读 `banks[slot]`、commit 翻转 |

两处已在 `ADDITIVE-SYNTH-DIAGNOSIS` 与 `NSLOT-AND-RUNTIME-EDIT` 两份文档里改过来了。
第二处更正对第 ④ 问很关键——**激发模式不是靠 bank 实现的**。

---

## 一、为什么要把参数搬到 `instrument_table`

三个理由，第三个才是根本。

### 1.1 让参数可改（ROM → RAM）

| | `preset_part.hex` | `instrument_table` |
|---|---|---|
| 类型 | ROM，上电 `$readmemh` 加载 | RAM，运行时写 |
| 改一次要做什么 | 改文件 → **重新综合 + PnR + 生成码流**（400–900 秒） | 发串口命令，**几毫秒** |
| 谁能改 | 只有开发者 | **演奏者自己** |

### 1.2 拿到预设表没有的字段

预设表每项 48 位，**没有包络字段**（只有 `epar` 的 3 个参数）。
运行时表每项 88 位，多出 **40 位自定义包络**（`a_inc` 起音增量、释放倍率、释放移位）。

所以"起音快慢"这件事，在预设表里只能靠 `d_m/d_k` 间接凑，在运行时表里可以直接给。

### 1.3 根本理由：最终音色是用户调出来的

出厂 4 个预设只是"能出声的起点"。产品的差异点是**演奏者能自己捏音色**。
所以数据必须活在 RAM 里，ROM 只是上电时的兜底。

### 1.4 顺带拿到原子切换

双缓冲已经实现好了：

```verilog
words[{slot, !banks[slot], part}] <= word;   // 写非活动 bank
// 16 个泛音全写完（&written[slot]）才允许 commit，commit 时 banks[slot] 翻转
```

**演奏中换音色不炸音**，因为旧音色在活动 bank 里一直有效，直到新音色 16 个泛音全部就绪。

---

## 二、原有编辑界面：已经有一套，约 7000 行

位置：`C:/Users/Sakuya/FPGA-Music-project/experiments/config_transport_20261017/`

### 2.1 结构

| 文件 | 行数 | 作用 |
|---|---:|---|
| `gui/workbench.py` | 904 | 主工作台 |
| `gui/config_editor.py` | — | 音色编辑 |
| `gui/instrument_config.py` | — | 界面侧配置模型 |
| `gui/piano_keyboard.py` | — | 钢琴键盘 |
| `gui/live_visualizer.py` | — | 实时可视化 |
| `gui/score_control.py` | — | 曲谱 |
| `gui/tone_panel.py` | 126 | 音色面板 |
| `gui/advanced_tools.py`、`audio_observer.py`、`serial_link.py`、`dsp_gui.py` | — | 高级工具 / 音频观察 / 串口 / DSP 视图 |
| `host/instrument_config.py` | 202 | **配置模型 + 校验（核心）** |
| `host/config_transport_client.py` | 88 | 传输客户端 |
| `host/config_adapter.py` | 86 | 适配层 |
| 测试 | — | `test_workbench.py` 493 行等，**104 项离线回归通过** |

### 2.2 配置数据模型（`host/instrument_config.py`）

```python
MODES = ("sustain", "strike", "hybrid")

{
  "schema_version": 1,
  "name": "strike",
  "preset": 0,
  "spectrum_mode": "replace",           # replace / 叠加
  "spectrum": [16 × 0..255],            # 每泛音幅度
  "articulation": {
    "mode": "sustain" | "strike" | "hybrid",
    "attack_ms": 0..60000,
    "decay_ms": 0..60000,
    "sustain_level": 0..255,
    "release_ms": 0..60000,
    "hybrid_parts": [16 × "sustain"|"strike"]
  },
  "vibrato": {"enabled", "rate_millihz", "depth_cents"},
  "effects": {
    "dry_enabled",
    "delay":  {"enabled", "time_ms", "feedback_q8"},
    "chorus": {"enabled", "rate_millihz", "depth_ms"},
    "reverb": {"enabled", "feedback_q8", "damping"}
  }
}
```

默认值（`default_config`）：`spectrum=[255,0×15]`、`mode=sustain`、
`attack_ms=5`、`decay_ms=300`、`sustain_level=192`、`release_ms=200`、
**`hybrid_parts = ["sustain"]×8 + ["strike"]×8`**。

> 注意这个默认：**低 8 个泛音持续、高 8 个泛音打击**——正是"余音变暖"的行为。
> 说明设计意图早就想清楚了，只是没在硬件上验证。

### 2.3 传输协议（doc 75）

```
E0=A5 开始 → E1 槽号、E2/E3 事务号(小端) → 176×E4 数据 → E5/E6 CRC-16/CCITT-FALSE → E7=5A 结束
每个 88 位词 = 11 字节小端；共 183 个寄存器对 / 366 UART 字节
115200 下纯线时约 31.8 ms（不含回读/USB/主机调度）
接收阶段 100 ms 超时；进入上传即 sandbox，普通参数与音符写入被隔离
```

### 2.4 状态：部分实现，未上板

doc 75 原文：**「限定串口/音频数字链与离线界面已验证；完整联合综合未通过，没有本版本板级部署、试听或生产包」**，
GUI 是「源代码入口，**未发布替换 exe**」。

**所以：界面代码在、数据模型在、协议在、离线测试过；缺的是"接到真实硬件上跑一遍"。**

---

## 三、接 EEPROM 是什么

### 3.1 器件

`24LC256-I/SN`，Microchip，SOIC-8，**32 KiB（256 Kbit）**，I²C 接口。
BOM 里 ¥4.50，状态是「立创估算（批量 ¥2.64），待精确 1+ 价」。

### 3.2 为什么需要

`instrument_table` 第一行注释就写着 **`volatile slots`**——**掉电全丢**。

用户花半小时调好的音色，一拔电就没了。这是产品级不可接受的。EEPROM 就是干这个的。

### 3.3 容量核算

```
4 槽 × 2 bank × 16 泛音 × 11 字节 = 1408 字节（一套完整音色组）
32 KiB / 1408 ≈ 23 套
```

**32 KiB 远远够用**，可以存 20 套以上音色，或者存 4 套音色 × 多版本。

### 3.4 现状：零实现

```
grep -rl "24LC|eeprom|EEPROM" candidate_source/engine/src candidate_source/rtl  → 无结果
i2c_master.v 只存在于 sim_build/board_diag_20261009/ 的旧诊断工程，不在产品源
```

**一行 EEPROM 相关 RTL 都没有。** 24LC256 目前只活在 BOM 里。

### 3.5 要做的四件事

| # | 工作 | 说明 |
|---|---|---|
| **P1** | I²C 主机 | 可从旧诊断工程移植，但要重验 |
| **P2** | 24LC256 时序层 | 2 字节地址、**页写 64 字节边界**、**写周期 5 ms 需轮询 ACK**、上电 5 ms 稳定 |
| **P3** | 上电加载 | 复位后读 → 校验 CRC → 灌进 `instrument_table`（走正常 `cfg_*` 写口） |
| **P4** | 保存 | 用户点"保存"→ 从 RAM 读回 → 写 EEPROM → 回读校验 |

### 3.6 一个必须先核的风险

屏的触摸 IC（FT5316 / GT911）**也用 I²C**。EEPROM 大概率要跟它共用总线。

- 若共用：需要总线仲裁或严格分时（触摸是高频轮询，EEPROM 是低频突发，冲突概率不低）
- 若不共用：需要单独两组 I²C 引脚，而 Tang Nano 20K 的可用引脚要重新核

**这条要在画板/接线之前核清楚**，否则 EEPROM 和触摸会互相踩。

---

## 四、激发模式规则（这是现在要定的）

### 4.1 现有模型

```python
MODES = ("sustain", "strike", "hybrid")
```

| 模式 | 含义 | 硬件怎么实现 |
|---|---|---|
| `sustain` | 所有泛音衰减后保持 | 16 个泛音全给 `s_lvl = sustain_level×128` |
| `strike` | 所有泛音衰减到 0 | 16 个泛音全给 `s_lvl = 0` |
| `hybrid` | 每泛音单独选 | `hybrid_parts[i]` 决定第 i 个泛音走上面哪一套 |

**硬件机制只有一套：每泛音的 `s_lvl` + `d_m` + `d_k`。三种模式都是它的组合。**

`strike.hex` / `sustain.hex` 就是"全 strike"和"全 sustain"编译出来的两张表（各 16 行），
在 `tb_layers.v` 里作测试用例。**它们不是硬件 bank。**

### 4.2 现有模型有三个缺陷

#### 缺陷 A：`hybrid_parts` 是二值，浪费了硬件

硬件每泛音有独立的 `s_lvl`（16 位）+ `d_k`（5 位）+ `d_m`（2 位），是连续可调的。
但配置模型只让选 `"sustain"` 或 `"strike"` 两个词。

**结果**：想做"泛音 1 衰减 3 秒、泛音 2 衰减 1.5 秒、泛音 3 衰减 0.8 秒"这种真实乐器行为，
模型表达不了。

#### 缺陷 B：`hybrid` 模式下 `decay_ms` 用哪个

配置里 `decay_ms` 是**全局一个值**。`hybrid` 模式下：

- 标为 `"sustain"` 的泛音用它 → 合理
- 标为 `"strike"` 的泛音**也用它** → 那"打击"就跟"持续"一样慢，失去意义

**这是真实的模型冲突，必须解决。**

#### 缺陷 C：ms → `d_k` 的换算没定义

界面用毫秒，硬件用 `d_m`/`d_k`。现在没有任何换算规则，HEX 里是手调的原始值。

### 4.3 提案：五条规则，请逐条拍板

#### R-1　三种模式保留，但内部统一

`sustain` 和 `strike` 都是 `hybrid` 的特例（全 sustain / 全 strike）。
界面保留三档只为了快选，硬件只走"每泛音 epar"一条路。

**要你确认**：这样理解对不对？还是三档在语义上另有区别（比如 `strike` 要禁止 release）？

#### R-2　`hybrid_parts` 从二值改成每泛音两个连续量

```json
"hybrid_parts": [16 × "sustain"|"strike"]        ← 现在
"part_decay_ms": [16 × 1..5000],                 ← 改成这个
"part_sustain":  [16 × 0..255]
```

兼容映射：
- `"sustain"` = `part_decay_ms = decay_ms`，`part_sustain = sustain_level`
- `"strike"` = `part_decay_ms = 最快档`，`part_sustain = 0`

**要你确认**：这个改法接受吗？改了之后老配置文件需要迁移。

#### R-3　时间换算规则

衰减是指数式：`lvl ← lvl − ((lvl × m) >> k)`，时间常数 `τ = 2^k / (m × fs)`，`fs = 52734.375`。

**定义**：`decay_ms` = 从满幅衰减到 `sustain_level` 所需时间。

换算：`k = round( log2( decay_ms/1000 × fs × m / ln(1/s) ) )`，其中 `s = sustain_level/255`。

对照表（`m = 3`，即现在所有预设用的档）：

| `d_k` | τ | `decay_ms` @ s=75% | @ s=50% | @ s=1% |
|---:|---:|---:|---:|---:|
| 8 | 1.62 ms | 0.47 | 1.1 | 7.5 |
| 10 | 6.47 ms | 1.9 | 4.5 | 30 |
| 12 | 25.9 ms | 7.5 | 18 | 119 |
| 14 | 104 ms | 30 | 72 | 477 |
| 16 | 414 ms | 119 | 287 | 1.9 s |
| 18 | 1.66 s | 477 | 1.15 s | 7.6 s |
| 20 | 6.63 s | 1.9 s | 4.6 s | 30.5 s |
| 22 | 26.5 s | 7.6 s | 18.4 s | 122 s |

**要你确认**：`decay_ms` 定义成"到 sustain 的时间"对不对？还是你想要"时间常数"？

#### R-4　`s_lvl` 映射

```
s_lvl = sustain_level × 128          (0..255 → 0..32640，满量程 32768)
```

验证：默认 `sustain_level = 192` → 24576，与 `sustain.hex` 的 24584 一致。

**要你确认**：`sustain_level = 255` 对应 100% 满幅，也就是"不衰减"。这个语义对吗？

#### R-5　生效时机：每个音符锁存

现有实现就是这个语义：

```verilog
custom_hold <= cfg_enabled[event_preset];
bank_hold   <= cfg_banks[event_preset];      // 在 note-on 时锁存
```

即**演奏中改参数，下一个音符生效，当前音符不受影响**。这与 doc 75 的
「下一次起音使用、仅本次通电有效」一致。

**要你确认**：这条直接写成规则，不再改？

### 4.4 还需要你定的两条产品级规则

| # | 问题 | 为什么必须现在定 |
|---|---|---|
| **Q-A** | `strike` 模式下按住不放，声音自己消失——这是**正确行为**还是**要避免的意外**？ | 决定界面要不要提示、要不要禁止长按 |
| **Q-B** | 激发模式**跟音符绑定还是跟音色绑定**？<br>（同一音色，轻按=strike、重按=sustain？还是整个音色固定一种？） | 决定 `hybrid` 是不是要跟力度联动。若联动，`hybrid_parts` 还要加力度维度 |

**Q-B 是最关键的一条**：如果激发模式要跟力度联动（轻按拨弦、重按拉弦），
现在的模型（音色级固定）就不够，得改数据结构。**这个决定越早，返工越少。**

---

## 五、复现命令

```bash
# 包络满量程（我上一轮算错的地方）
sed -n '42p;80p' candidate_source/engine/src/osc_env.v

# 运行时表全文（bank 是双缓冲，不是激发模式）
cat candidate_source/engine/src/instrument_table.v

# 配置模型与三种模式
sed -n '15,48p;96,106p' experiments/config_transport_20261017/host/instrument_config.py

# 界面文件清单
ls experiments/config_transport_20261017/gui/ experiments/config_transport_20261017/host/

# 示例配置
cat experiments/config_transport_20261017/config-hybrid.json

# EEPROM 是否已实现（应为空）
grep -rl "24LC\|eeprom" candidate_source/engine/src candidate_source/rtl
```
