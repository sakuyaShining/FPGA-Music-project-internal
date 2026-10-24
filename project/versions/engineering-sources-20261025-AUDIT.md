# `engineering-sources-20261025.json` 审计报告

> 由 `project/versions/engineering-sources-20261023.json` 重发而来。
> 重发原因：20261023 之后有 G1/G4 修复、25 音位落地、八度档电极与采样率定稿，
> 共 **17 个文件内容变了、17 个文件新增**，旧 manifest 早已对不上 ——
> `engineering.py check` 会在第一个变动文件上抛 `Stored identity changed`。

## 1. 规模

| area | 20261023 | 20261025 | 新增 | 内容变 | 删除 |
|---|---:|---:|---:|---:|---:|
| `fpga` | 253 | 269 | 16 | 17 | 0 |
| `hardware` | 50 | 51 | 1 | 0 | 0 |
| `host` | 38 | 38 | 0 | 0 | 0 |
| **合计** | **341** | **358** | **17** | **17** | **0** |

`captured_at` = `2026-10-24T19:33:27.613782+00:00`
`source_branch` = `codex/91-spec-intake-20261024`

## 2. 新增的文件（逐条说明为什么该进 manifest）

**`fpga`（16 个）**

- `FS-AUDIT-20261024.md` — 文件系统审计（此前未纳入）
- `PITCH-MAP-DEFINITION-20261024.md` — 音高映射定稿文档（此前未纳入）
- `SCAN-CHAIN-DELIVERY-20261024.md` — 扫描链交付说明（此前未纳入）
- `TEST-REGISTRY.md` — 测试台登记表（本轮新建）
- `constraints/tdm_ship_board.cst` — 载板约束（此前未纳入）
- `engine/src/scan_bus_arbiter.v` — 扫描总线仲裁器（此前未纳入）
- `engine/src/scan_shift165.v` — 165 读回移位（此前未纳入）
- `engine/src/sensor_frontend_board.v` — 传感器前端整链（此前未纳入）
- `project/scan-map.json` — `check_joint.py` 的输入。一直没提交，所以 check_joint 在干净 clone 上从来没跑起来过
- `sim/tb_audio_clk_en.v` — **采样率判据**（本轮新建，此前 audio_clk_en.v 注释引用了一个不存在的同名文件）
- `sim/tb_octave.v` — **八度档 5 格判据**（本轮新建）
- `sim/tb_pad_velmap.v` — G4 力度别名判据（此前未纳入）
- `tb/tb_area.v` — G1 接触面积判据（此前未纳入）
- `tb/tb_board_scan.v` — 载板扫描前端判据（此前未纳入，且无驱动）
- `tools/check_audio_rate.py` — 采样率静态守门（本轮新建）
- `tools/run_all_checks.py` — 统一测试入口（本轮新建）

**`hardware`（1 个）**

- `context/pin-map-audit-20261024.md` — 引脚映射核对（hardware）

## 3. 内容变了的文件

每一行都能对上本轮或近几轮的一个提交，没有"来源不明"的改动。

**`fpga`（17 个）**

- `check_engine_compat.py` — 参考轨迹改为「没有 .tsv 就从 .tsv.gz 解压」（原写法在干净 clone 上必然 FileNotFoundError）
- `check_sensor.py` — 随 25 音位与 area 输出同步
- `engine/src/audio_clk_en.v` — 头部注释：18 分频/46875 Hz → 产品是 16 分频/52734.375 Hz
- `engine/src/instrument_sensor_probe.v` — 透出 single_touch
- `engine/src/layer_dispatch.v` — 25 音位落地
- `engine/src/left_contact_bridge.v` — 25 音位落地（NF 26→25）
- `engine/src/left_layer_music_probe.v` — 25 音位落地
- `engine/src/left_music_probe.v` — 25 音位落地
- `engine/src/pad_pitch.v` — G4：vel_bus 扩到 25 路，索引用完整 sc
- `engine/src/rc_strip_positions.v` — 八度档 5 格单电极直读（NSINGLE/SINGLE_BASE/single_touch）
- `engine/src/tdm_top.v` — 头部采样率注释 + `.vel_bus({25{4'd12}})`
- `engine/src/tdm_top_owned.v` — 同上 + pp_vel_bus 补零
- `engine/src/tdm_top_rh.v` — 同上
- `handoff_support/system_integration_20261016/tb_sensor.v` — 随 25 音位同步
- `sim/tb_pad_chain.v` — 新增判据 [5]~[8]：换八度不打断在奏音
- `tb/tb_sensor.v` — 随 25 音位同步
- `tools/run_sims.py` — 注册 tb_audio_clk_en / tb_octave / tb_board_scan；判据识别加 "ALL PASS" 风格

## 4. 三条"看不出变化"的变化：黄金轨迹的 `stored` 路径

三条黄金轨迹的 `name` 没变、解压后的 `sha256` 也没变，所以既不算"新增"也不算"内容变" ——
但它们的 `stored`（仓库里真正存的文件）从 `.tsv` 变成了 `.tsv.gz`：

| `name`（逻辑路径，export 写这里） | `stored`（仓库实际存的文件） | 大小 |
|---|---|---|
| `.../evidence/compat-all.tsv` | `.../evidence/compat-all.tsv.gz` | 38.2 MB → 5.7 MB |
| `.../evidence/layers-all.tsv` | `.../evidence/layers-all.tsv.gz` | 35.6 MB → 5.3 MB |
| `.../evidence/sensor-all.tsv` | `.../evidence/sensor-all.tsv.gz` | 26.2 MB → 3.8 MB |

`codec=gzip` 的语义必须保持（`fpga/current/README.md` 第 22 行有约定）：

```
name          = 逻辑路径（.tsv）        ← export 时写这个路径
stored        = 仓库里真正存的文件（.tsv.gz）
bytes/sha256  = 【解压后】内容的长度与哈希
stored_sha256 = .gz 本身的哈希
```

写成 `codec=raw` 的话 `export` 只会把 `.gz` 原样拷出去，而 `check_engine_compat.py`
找的是 `.tsv` —— 导出目录里当场失效。

## 5. 审计做了什么

| # | 检查 | 结果 |
|---|---|---|
| 1 | 逐条重算：`stored_sha256` 对仓库里那个文件、`bytes`/`sha256` 对解压后内容 | PASS（358/358） |
| 2 | 反向检查：`git ls-files`（已跟踪 + 未跟踪但未忽略）里有没有漏登记的 | PASS（0 个漏登记） |
| 3 | 官方校验器 `tools/scripts/engineering.py check` | `PASS, files=358` |
| 4 | 实际导出一次 `--area fpga` | 271 个文件；黄金轨迹恢复为 `.tsv`，sha256 `7e73583d…` 与 manifest 记录一致 |
| 5 | 在导出目录里跑 `tools/run_all_checks.py --fast` | **11/11 PASS**（证明导出是自洽可跑的，不是"导出来但跑不了"） |

## 6. 这次顺带修的两个"manifest 永远过不了"的坑

1. **`check()` 把生成物当漏登记**
   `check_*.py` 每跑一次都会重写 `fpga/current/evidence/`（编译日志、输入哈希），
   而 `check()` 原本要求 `area/current` 下**每个**文件都在 manifest 里。
   结果：跑过一次测试，manifest 就永远 check 不过。
   已改为跳过 `.gitignore` 忽略的路径（`git check-ignore -z --stdin`）。

2. **`MANIFEST` 常量还指着 20261023**
   已指向 `engineering-sources-20261025.json`。旧文件保留，用于追溯。

## 7. 这次**没有**动的东西

- `hardware` 与 `host` 两个 area 只是重算哈希，内容零改动（各 1 个 / 0 个新增）。
- 没有重采 `check_engine_compat.py` 的金标。它现在能跑但**对不上**：
  193475 行里 56495 行与当前 RTL 不同，且在引入它的那次提交（`f18ccbb4`）上就已经对不上。
  金标是"行为基线"，重采等于承认行为变了 —— 留给产品层拍板，详见 `fpga/current/TEST-REGISTRY.md` §2.1。
- `validation_inherited` 与 `product_acceptance` 全部保持 `false`：
  本 manifest 只登记**输入身份**，不代表已发布、不代表产品验收。

