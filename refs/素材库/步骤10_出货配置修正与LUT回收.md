# 出货配置修正 + LUT 回收（2026-10-02 第二轮）

> 本轮做了两件事，都属于"**把设计从'验证过的样子'拉回'真的要出货的样子'**"：
> ① 修掉出货时钟配置下的一个**隐藏相位/累加 bug**；
> ② 把滑音从指数衰减改成**线性速率**，回收 **5591 LUT**（72% → 45%）。
> 测试台：`tb_pitch_mod` / `tb_pitch_mod512` / `tb_reg_ctl` / `tb_tdm_top` / `tb_latency`
> 本轮最后一节记录了**三次"陈旧构建"事故**换来的 `build_sims.ps1`。

---

## 一、★ 隐藏 bug：周期（576）> 时隙数（512）时，前 64 个时隙每样本推进两次

### 症状
把测试台的样本周期从"= 时隙数"改成"时隙数 + 64"（当时是为了给滑音衰减腾出空闲窗口），
128 档立刻报：

```
G2 比例 d15/d0：最小 16.00000 最大 32.00735（应为 16）
```

比值变成 **32** —— 说明 slot 15 每样本推进了 **两次**。

### 根因
`tdm_engine` 的时隙计数器 `sc` 是 `$clog2(NSLOT)` 位，**在 NSLOT 处自然回卷**：

```
采样周期 = 576 拍（27 MHz ÷ 18 × 32），NSLOT = 512
sc: 0,1,...,511, 0,1,...,63        ← 后 64 拍回卷
slot_addr = sc + LAT  →  4,...,67   ← 于是 slot 4..67 被【第二次访问】
```

后果有两处（都在出货配置下成立）：
1. **slot 4..67 每样本相位推进两次** → 那 64 个振荡器频率翻倍；
2. **累加窗口与输出锁存也在一个样本周期内触发两次**：
   `sc == LAT`（清零）与 `sc == LAT-1`（锁存）在回卷后又各出现一次，
   第二次锁存的是**只累了一半的残窗** → I2S 取到的可能是垃圾值。

### 为什么之前的验证没抓到
| 测试 | 周期 | 能否发现 |
|---|---|---|
| `tb_tdm_equiv`（R0 逐位一致） | 32 = NSLOT | ❌ 周期 = 时隙数 |
| `tb_pitch_mod`（128 档） | 128 = NSLOT | ❌ 同上 |
| `tb_pitch_mod512`（512 档） | 512 = NSLOT | ❌ 同上 |
| `tb_note_music` / `tb_tdm_demo`（音频示范） | 128 = NSLOT | ❌ 同上 |
| **`tb_tdm_top`（唯一用真实时钟的）** | **576 > NSLOT** | ❌ **只校验 I2S 闭环一致性——对"值对不对"是盲的** |

**教训**：`tb_tdm_top` 的判据是"串行流解码 == 引擎输出"，
它只能证明**链路一致**，不能证明**合成正确**。而合成正确性全部是在
"周期 = 时隙数"这个**与出货配置不同**的条件下验证的 —— 这正是"验证了错的配置"。

### 修法：让出货周期就等于时隙数
```
DIV_BCK: 18 → 16
BCK = 27 MHz / 16     = 1.6875 MHz   （整数分频，无抖动）
fs  = 1.6875 MHz / 32 = 52734.375 Hz （MAX98357A 支持 8k~96k ✓）
每样本拍数 = 16 × 32 = 512 = NSLOT  ✓
```
- `sc` 不再回卷 → 每个时隙每样本**恰好访问一次**，累加/锁存**恰好一次** ✓
- 顺带把 `audio_clk_en.v` 里硬写的 `bck_cnt >= 9` 改成参数化的 50% 占空比
  （原来只对 DIV_BCK=18 成立）
- 表按新采样率重新生成（`note_map_gen.py --fs 52734.375`）
- **出货配置从此与全部功能验证的配置完全一致** —— 证据直接适用
- 测试模式的频率栅格随之整体上移 12.5%（inc 常量没动）：225 Hz + slot×27.7 Hz

---

## 二、滑音：指数衰减 → 线性速率（回收 5591 LUT）

### 为什么改
把 `glide_k` 做成运行时端口后，每音符衰减回路里的 `mmul >> glide_k`
从**常量移位（免费连线）**变成 **19 位变量移位器**，32 份实例实测：

| | Logic | LUT |
|---|---|---|
| 常量移位（对照实验） | 9497（46%） | 6997 |
| **变量移位** | **14766（72%）** | **12267** |

试过两种省法：
- **分时复用**（样本末尾 64 拍空闲里每拍算一个 entry）→ 需要 `period ≥ NSLOT + NG`，
  而修法①之后周期**正好等于** NSLOT，**没有空闲窗口** ✗（而且正是它引出了上面的 bug）；
- **线性速率** → 每份只要"比较 + 加减 + 选择"（≈35 LUT），不需要移位器 ✓ 选它。

### 新语义（更好讲，也更像乐器）
```
gq 每样本朝 0 走 glide_step（Q16）：
    gq > 0 : gq <= (gq >  step) ? gq - step : 0
    gq < 0 : gq <= (gq < -step) ? gq + step : 0
时长 = |gq0| / glide_step  个样本 —— 一个【可算的确定值】
```
寄存器：`0x35-0x36 = GLIDE_STEP`（小端 16 位）。默认 10 → 12 个半音约 62 ms。

---

## 三、验收（每一条都是本轮重新跑出来的）

| 判据 | 结果 |
|---|---|
| **R0** TDM ≡ 全并行 | 延迟 5，**不符 0 / 2495** ✓ |
| **128 档**（周期 = 时隙 = 128） | G1 **0/39598**、终点误差 **+0.000 音分**、G2 **16.00000~16.00013**、V1/V2/C1 全过 ✓ |
| **512 档**（周期 = 时隙 = 512，**与出货一致**） | **E1a 32/32 路基频逐个精确**、G1 **0/6048**、G2 **16.00000~16.00021**、V1/V2 ✓ |
| **E2/E3 运行时参数** | 音色 4 预设 **16/16**；颤音深度 **0.00 / 26.31 / 52.64 音分**；滑音线性递推 **0 不符**、相位增量 vs gq **0/2998**、时长 **2761 / 346**（理论 2761/345）、比值 **7.98** ✓ |
| **顶层端到端** | I2S 闭环 **0 / 227** ✓ |
| **E5 延迟**（新时钟链） | t_pin 最大 **2807 拍 = 0.104 ms**，对 5 ms **48×** 余量；同相位两遍逐拍一致 ✓ |
| **综合** | **只有既有的 PR1014 告警** ✓ |

### 资源（GW2AR-LV18QN88C8/I7，NSLOT=512，周期 512）

| 项 | 本轮前 | **本轮后** |
|---|---|---|
| **Logic** | 14766 / 20736（**72%**） | **9175 / 20736（45%）** |
| — LUT | 12267 | **6070** |
| — ALU | 1707 | 2313 |
| Register | 1454（10%） | 1463（10%） |
| BSRAM | 9 / 46（20%） | 9 / 46（20%） |
| DSP | 6.75 / 24（29%） | 6.75 / 24（29%） |
| SETUP slack | +11.838 | **+14.195**（arrival 28.136 ns） |
| HOLD slack | +0.205 | **+0.205** |

**净回收 5591 LUT（−27 个百分点）**，为 E4 效果器腾出了预算。

---

## 四、三次"陈旧构建"事故 → `build_sims.ps1`

本轮（以及上一轮）一共被同一件事咬了三次：
1. 改了 RTL，只重编了部分测试台 → 拿旧 `vvp` 的数据下结论；
2. PowerShell 里用函数 + 数组展开调 `iverilog` → 打印成功但**根本没重建**；
3. 加了 `sample_en` 门控后只重编两个调制测试台 → `rc.vvp` 还是旧版
   （衰减每时钟一次 = 快 512 倍，实测滑音速率 14046/样本）。

于是固化成一条命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\scripts\build_sims.ps1
```

它 **重编全部 9 个测试台**，然后**逐个比对 `.vvp` 与最新 `.v` 的时间戳**，
过期的直接标 `STALE`。**以后每轮改完 RTL 先跑它，再谈数据。**

（另外：这个 `.ps1` 必须是**纯 ASCII** —— Windows PowerShell 5.1 会把无 BOM 的
UTF-8 脚本按 ANSI 读，中文注释会直接把脚本解析坏。）

---

## 五、复现

```powershell
# 1) 重建（含时间戳核对）
powershell -NoProfile -ExecutionPolicy Bypass -File tools\scripts\build_sims.ps1

# 2) 四套功能判据
cd sim_build\_recheck ; vvp tdm.vvp ; cd ..\..
python tools\scripts\tdm_compare.py --simdir sim_build\_recheck --mask 0xFFFFFFFF

cd sim_build\pitchmod    ; vvp pm.vvp    ; cd ..\..
python tools\scripts\pitch_mod_check.py    --simdir sim_build\pitchmod

cd sim_build\pitchmod512 ; vvp pm512.vvp ; cd ..\..
python tools\scripts\pitch_mod512_check.py --simdir sim_build\pitchmod512 --fs 48828.125

cd sim_build\latency
vvp rc.vvp +test=0 ; vvp rc.vvp +test=1 ; vvp rc.vvp +test=2 ; vvp rc.vvp +test=3
cd ..\..
python tools\scripts\reg_ctl_check.py --simdir sim_build\latency

# 3) 顶层端到端 / 延迟
cd sim_build\_recheck ; vvp top3.vvp ; cd ..\..
cd sim_build\latency  ; vvp lat.vvp +phase=0 ; cd ..\..
python tools\scripts\latency_check.py --file refs\素材库\步骤8_延迟证据\原始测量.txt

# 4) 综合
powershell -NoProfile -ExecutionPolicy Bypass -File tools\scripts\build_gowin.ps1 `
  -Project src\gowin\tdm_synth\tdm_synth.gprj
```

---

## 六、仍要注意

| 项 | 说明 |
|---|---|
| 采样率变了 | 46875 → **52734.375 Hz**。报告/视频里的频率数字、MAX98357A 的配置说明都要跟着改 |
| 测试模式栅格 | inc 常量没动 → 峰位整体上移 12.5%（225 Hz 起，间隔 27.7 Hz）。要恢复原频率就把 inc 按 8/9 缩放 |
| HOLD slack 仍只有 +0.205 ns | 上板前值得再看一眼；加 E4 逻辑后必须重测 |
| 纸上"周期 = 时隙数"现在是不变量 | `tdm_engine` 依赖它（sc 不回卷）。若将来改时钟链，必须同时满足 `DIV_BCK × 32 = NSLOT`，或在引擎里处理回卷 |
