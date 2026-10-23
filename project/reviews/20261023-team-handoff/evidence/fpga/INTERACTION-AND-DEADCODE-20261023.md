# 实体交互设计 + 死代码审计 · 2026-10-23

回答两件事：
① 最终用户怎么交互；为什么"音色 + 激发模式"这个两分法在交互上是对的，而四层框架该怎么落到实体机上；
② "死代码"到底有多少、分几类、怎么处置。

---

## 一、先回答一个关键区分：两分法和四层不是同一个轴

| 轴 | 分法 | 回答的问题 |
|---|---|---|
| **参数空间** | 频谱 / 时域 / 响应 / 演奏法（四层） | 硬件里这些数字**物理上**属于什么 |
| **交互频次** | 音色 / 激发模式（两分） | 用户**什么时候**去动它们 |

**这两个轴不冲突，而且你的分法在交互上更对。**

理由：四层里只有**演奏法**需要在演奏过程中实时切换，其余三层都是**编辑态的一次性设定**。

| 层 | 谁在什么时候调 | 需要演奏态控件吗 |
|---|---|---|
| 频谱 | 编辑态，用户慢慢捏 | ❌ |
| 时域 | 编辑态，用户慢慢捏 | ❌ |
| 响应（力度曲线） | 编辑态，一次设定（甚至只在出厂时设一次） | ❌ |
| **演奏法（激发）** | **演奏中，手指不能离开键盘** | ✅ **只有这一层需要** |

**⇒ "乐器 = 音色 + 激发模式"这个两分法，本质是按"什么时候调"分的：
音色 = 编辑态产物，激发模式 = 演奏态开关。**

这个分法是对的，因为它直接对应**两类完全不同的交互场景**。

---

## 二、两态交互模型

### 2.1 演奏态（手不离键）

| 控件 | 数量 | 作用 | 反馈 |
|---|---|---|---|
| 电容电极 | 7（物理可达） | 音高 + 力度 | 声音本身 |
| **槽选择键** | 1（循环 4 槽） | 选音色 | LED 显示槽号 |
| **激发切换键** | 1（循环 3 模式） | sustain / strike / hybrid | LED 显示模式 |
| LED | 6 | 曲谱指引 + 状态 | — |

**为什么是"循环"而不是"每槽一个键"**：见 §2.3 的引脚约束，独立键不够。

循环键的代价：**从槽 0 到槽 3 要按 3 下**。演奏中换音色会很别扭。
缓解：把最常用的两个槽放在循环的相邻位置（0↔1），或做"长按回 0"。

### 2.2 编辑态（进入方式：长按槽键 2 秒）

| 控件 | 作用 |
|---|---|
| 触控屏 | 显示当前槽的 16 根泛音柱、点选要编辑的泛音 |
| 右手推子 | 连续调该泛音的幅度（`rh_fader_*` 的设计意图） |
| 确认键 | 写入 `instrument_table` 并 commit |

**编辑态不做的事**：不构造泛音（用户原话："在编辑状态 应该没人会想要构造泛音"）。
所以编辑态只改**已有分量的幅度/时域**，不新增分量。

### 2.3 硬约束：引脚不够，这是必须知道的

板边 J5/J6 上全部可用的 FPGA 引脚（`nano-header-candidate.csv`，17 个）：

| FPGA 脚 | 排针 | 当前用途 | 带 LED 负载 |
|---|---|---|---|
| 27 | J6-8 | `pad[0]` | — |
| 28 | J6-9 | `pad[1]` | — |
| 29 | J6-12 | `pad[2]` | — |
| 30 | J6-13 | `pad[3]` | — |
| 31 | J6-14 | `pad[4]` | — |
| 41 | J5-6 | `pad[14]` | — |
| 42 | J5-5 | `pad[15]` | — |
| 15 | J6-6 | `led[0]` | ✅ 510Ω |
| 16 | J6-7 | `led[1]` | ✅ |
| 17 | J6-15 | `led[2]` | ✅ |
| 18 | J6-18 | `led[3]` | ✅ |
| 19 | J6-17 | `led[4]` | ✅ |
| 20 | J6-16 | `led[5]` | ✅ |
| **25** | J6-10 | **空闲**（I²C SDA 预留） | — |
| **26** | J6-11 | **空闲**（I²C SCL 预留） | — |
| **48** | J5-10 | **空闲** | — |
| **77** | J6-5 | **空闲**（TP_INT 预留） | — |

**纯空闲只有 4 个：25 / 26 / 48 / 77。**
而 25/26 要给 EEPROM + 触控（I²C 共用），77 要给触摸中断。

**⇒ 真正能自由支配的只有 48，最多再加 77（触控未定案前）。**

**5 个独立按键做不了。** 这是"2 键循环"方案的根本原因。

### 2.4 被忽略的方案：扫描总线

`nano-header-candidate.csv` 里还有一组信号，明显是为**按键/LED 扫描**设计的：

```
BUS_SCK      = 27    ← 但现在是 pad[0]
BUS_MOSI     = 15    ← 但现在是 led[0]
SCAN_LATCH   = 16    ← 但现在是 led[1]
INPUT_LOAD_N = 17    ← 但现在是 led[2]
INPUT_DATA   = 28    ← 但现在是 pad[1]
```

`engine/src/scan_shift595.v` 就是这套的驱动，**但它不在产品顶层**（见 §3）。

**问题：这 5 个脚和现在的电极/LED 完全冲突。**
要用扫描，必须先把电极从 16 路降到 7 路，把 27/28 让出来 —— 但那样电极就只剩 5 路（29/30/31/41/42），更不够。

**⇒ 扫描总线与"7 路电极"是互斥的两个方案，必须二选一。**

| 方案 | 电极数 | 按键数 | 代价 |
|---|---|---|---|
| A · 电极优先 | 7 | 2（48/77） | 循环键，换音色要按多下 |
| B · 扫描优先 | 5 | 16+ | 电极更少，且要新写扫描驱动 |
| C · I²C 扩展 | 7 | 8（PCF8574 挂在 25/26） | 与 EEPROM/触控共用总线，需仲裁 |
| D · 触控屏 | 7 | 全部（虚拟按键） | 屏未定案 |

**我的建议：A 起步（今天就能做），C 作为 v2。** D 依赖硬件到货，B 会牺牲电极。

---

## 三、死代码审计

### 3.1 一级：78 个模块文件，只有 27 个进网表

从 `build_decay2_v1/board.gprj` 的 FileList 出发做可达性分析：

```
模块文件总数        78
文本可达            28
真正进网表          27   （uart_cfg_transport 被 generate if(CONFIG_SERIAL) 排除）
不进网表            51
```

### 3.2 二级：可达 ≠ 在网表里 —— `instrument_table` 已被完全优化掉

```
grep -c "instrument_table" impl/pnr/board.rpt.txt   →   0
```

**整个运行时音色表在 PnR 报告里出现 0 次。** 原因：`cfg_valid` 恒 0 ⇒ `words` 永远不写；
`custom_hold` 恒 0 ⇒ `custom_entry` 永远不用。综合器做了跨模块常量传播，把它整块删了。

**⇒ 代码"可达"不代表它活着。这类比孤立文件更隐蔽。**

### 3.3 三级：9 个功能开关，7 个是关的

`tdm_ship_owned.v` 的 6 个参数 + `tdm_top_owned.v` 的 3 个参数：

| 开关 | 产品值 | 关掉了什么 | 代码位置 |
|---|---|---|---|
| `CONFIG_SERIAL` | **0** | 串口配置上传 + 自定义音色生效 | `tdm_top_owned.v:190` |
| `INSTRUMENT_ENV` | **0** | 40 位自定义包络（起音/释放/抽稀） | `tdm_engine_rh.v:392` |
| `OWNED_EVENTS` | **0** | 多实例所有权（`owned_hold` 恒 0） | `note_map_owned.v` 全文 |
| `FINGER_EXPR` | **0** | 逐指音高表达（`finger_use` 恒 0） | `tdm_engine_rh.v:709` |
| `RIGHT_TIMBRE` | **0** | 右手音色注入（`right_timbre` 块不生成） | `tdm_engine_rh.v:497` |
| `MULTI_BIND` | **0** | 一指绑多组（四层分层需要） | `layer_dispatch.v` |
| `BEACON` | **0** | 串口心跳 | `tdm_ship_owned.v:81` |
| `LEGACY_PAD` | 1 | ✅ 开着（16 路电极直连） | `tdm_top_owned.v:686` |
| `BOARD_DIAG` | 0 | 板级诊断寄存器 | `tdm_top_owned.v` |

**7 个关闭里，有 5 个是产品核心功能**：自定义音色、起音可调、逐指表达、右手音色、四层分层。

**这不是"死代码"，是"写好了但没通电"。**

### 3.4 51 个不进网表的模块，分五类

#### B1 · 放弃的功能（10 个）—— 可以归档

`RA8875` 可视化链 + 旧显示驱动：

```
image_rom  image_view  music_visualizer  mv_fft1024  mv_panel_driver
mv_renderer  mv_spi_byte  mv_wave_capture  lcd_480x272  video_timing
```

**处置：** 用户已决定放弃可视化 ⇒ 这 10 个可以移到 `archive/`。它们占了 78 个文件里的 13%。

#### B2 · 旧顶层与旧引擎（10 个）—— 可以归档

```
tdm_top  tdm_top_rh  tdm_ship  tdm_ship_beacon  tdm_engine
osc_additive  osc_additive_top  osc_core  synth_top  bringup_top
```

**风险**：`tdm_engine.v` / `osc_additive.v` 里还引用了 `osc_env`（双段衰减的端口我在那里固定成 0）。
如果归档，`tb_strike` 之类可能引用不到。**归档前要跑一次全量回归。**

#### B3 · 同名旧版本（3 个）—— 危险，容易读错

```
note_map.v      vs  note_map_owned.v      ← 产品用 _owned
reg_bank.v      vs  reg_bank_compact.v    ← 产品用 _compact
test_mode.v / test_pattern.v              ← 旧测试图样
```

**`note_map.v` 和 `note_map_owned.v` 有 90% 相同代码，但只差几处**。改错文件不会有任何报错，只是"改了没用"。
**处置：重命名成 `note_map_legacy.v` 并加顶部注释，或直接归档。**

#### B4 · 探针（7 个）—— 可以归档

```
instrument_joint_probe  instrument_layer_probe  instrument_owned_probe
instrument_sensor_probe  compat_music_probe  left_music_probe
left_layer_music_probe  rh_music_probe
```

#### B5 · 待接线（4 个）—— 必须留

```
layer_dispatch.v      ← 刀4 四层派发要用
rc_mux_scan.v         ← B5 电极多路复用要用
i2c_master.v          ← EEPROM / 触控要用
uart_cfg_transport.v  ← CONFIG_SERIAL=1 要用
```

**这 4 个不是死代码，是"备件"。** 但它们没被例化，所以从网表看跟 B1 一样"不存在"——
**必须用注释或目录结构把它们区分出来，否则下次审计会误判。**

#### B6 · 实体交互层（10 个）—— **这是最大的发现**

```
rc_mux_scan  rc_delta_store  rc_strip_positions      左手滑条扫描
rh_fader_bank  rh_fader_gain_map  rh_fader_panel     右手推子
rh_performance_control  rh_timbre_slew               演奏控制 / 音色平滑
left_contact_bridge  perf_ctrl  scan_shift595        接触桥 / 性能控制 / 595 扫描
mixer  led_blink  led_heartbeat                      混音 / LED
```

**这 10 个模块合起来就是"实体交互层"，而它们一个都没接进产品顶层。**

产品顶层现在只有：`pad[15:0]`（16 路电极直连）+ `btn_rst`（复位）+ `led[5:0]`。

**⇒ 你问"最终用户怎么交互"，现状的准确回答是：现在只有 16 个电极触点，没有槽选择、没有激发切换、没有编辑入口。**

---

## 四、处置建议

### 4.1 立即可做（不动风险）

| 动作 | 收益 |
|---|---|
| 把 B1（可视化 10 个）+ B2（旧顶层 10 个）+ B4（探针 7 个）移到 `archive/` | 78 → 51 个文件，读代码时不会被误导 |
| 把 B3 的 `note_map.v` / `reg_bank.v` 重命名加 `_legacy` 后缀 | 消除"改错文件"的隐患 |
| 给 B5 的 4 个文件加顶部注释 `// 备件：未接入产品顶层，用途见 XXX` | 下次审计不误判 |

### 4.2 需要决策

| 决策 | 选项 |
|---|---|
| 实体按键方案 | A 电极优先（2 键循环）/ C I²C 扩展（8 键）/ D 触控屏 |
| B6 的 10 个交互模块 | 全部接？只接 `rc_mux_scan` + `rh_fader_*`？ |
| 7 个关闭的开关 | 先开哪两个（建议 `CONFIG_SERIAL` + `INSTRUMENT_ENV`） |

### 4.3 一个必须提醒的风险

**开关关闭 ≠ 免费。** `INSTRUMENT_ENV=0` 省了 1.1 块 BSRAM，但代价是：
- 界面 6 个旋钮是空的（用户调了没反应）
- 钢琴低音做不到 10 秒衰减
- "激发模式"只改衰减不改起音

**这些代价不会出现在资源报告里，只会在用户试用时出现。**

---

## 五、复现命令

```bash
P=D:/FPGA-Project/codex-builds/fpga-m1-agent-work/build_decay2_v1

# 模块可达性
python - <<'EOF'
import re,glob,os
os.chdir(r"D:/FPGA-Project/codex-builds/fpga-m1-agent-work/build_decay2_v1")
mods={}
for f in glob.glob('*.v'):
    s=open(f,encoding='utf-8',errors='ignore').read()
    for m in re.finditer(r'^\s*module\s+(\w+)',s,re.M): mods[m.group(1)]=f
seen=set();stack=['tdm_ship_owned']
while stack:
    cur=stack.pop()
    if cur in seen: continue
    seen.add(cur)
    f=mods.get(cur)
    if not f: continue
    s=open(f,encoding='utf-8',errors='ignore').read()
    for m in mods:
        if m!=cur and re.search(r'(?<!module\s)\b'+re.escape(m)+r'\b\s*(#\s*\(|[a-zA-Z_])',s):
            if m not in seen: stack.append(m)
print('可达',len(seen),'/ 总',len(mods))
EOF

# instrument_table 是否在网表
grep -c "instrument_table" $P/impl/pnr/board.rpt.txt

# 7 个关闭的开关
grep -n "CONFIG_SERIAL=0\|INSTRUMENT_ENV=0" $P/tdm_top_owned.v
grep -n "FINGER_EXPR = 0\|RIGHT_TIMBRE = 0\|OWNED_EVENTS = 0" $P/tdm_ship_owned.v

# 引脚冲突
cat "C:/Users/Sakuya/FPGA-Music-project/hardware/system-candidate-20261015/nano-header-candidate.csv"
```
