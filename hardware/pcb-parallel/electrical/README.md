# E3 电气、接口与可装配性合同（951 原生 PCB）

角色：E3　版本：`e3-2026-10-25.3`　作者：本会话（用户 2026-10-25 指派）
输入源：`hardware/checkpoints/pcb-951ce88a-20261025/native/pcb/PCB1.epcb2`
源 SHA256：`951ce88a1a2fcc2d758f9a53222a400cbddd3bc5b689cc2a37c98b8303d9ca4d`

本目录只读设计源，不修改 RTL、原理图、候选 PCB 或正式板。所有结论绑定上述 SHA；
源一变，本版约束全部失效，须递增版本号。

> **版本 .3（2026-10-25）**：补做 V4 IR-03 的下游影响审计。E3 目录内无残留，但目录外 3 处文档
> 仍把 IOtail 派生源的「单删分成 5+42」当成 951 的红线理由（见 `CORRECTIONS-20261025.md` C-06、
> `D-10`）。这三处不在 E3 写入路径内，已给出逐条替换文本待治理提交。
> 同轮把九条 IR 的全仓库残留扫了一遍，另发现 IR-08 的统计口径遗留（`D-11`，归 M0）。

> **版本 .2（2026-10-25）**：按 V4 独立审查的 IR-01 / IR-02 / IR-04 / IR-05 / IR-06 修订本目录。
> 三条原结论被撤销（R67 缺陷、J10.11 矛盾、IO848 判据失效），一条被升级为 G1 阻断（上电合同）。
> 逐条对照见 `CORRECTIONS-20261025.md`。

## 一分钟结论

1. **951 上没有 FPGA**。J5/J6 是 2×20P 母座，插 Nano20K 模块；`3V3_IO`（46 元件焊盘 + 测试点 TP6 = 47 端点）**只由模块供入**，板上没有该轨稳压器。
2. **限流链是完整的**：U17(TPS2553) 的 R67 = **23.7 kΩ**，在 TI 允许的 15–232 kΩ 区间内，限流点约 1.002–1.184 A，低于 PTC 的 2.20 A 跳脱点（`E3-PWR-002`，已撤销缺陷结论）。
3. **复位由 595 驱动，板上无 RC**：J10.7 = `DISP_RESET_N`（← U8.6/QG 经 U15）、J10.11 = `TP_RESET_MOD_N`（← U8.7/QH 经 U15）。任务卡所称「pin11 NC」指**模组 40 针接口**第 11 脚，与载板 J10（12 针）第 11 脚不是同一对象，**不存在矛盾**（`E3-RST-001`）。
4. **上电默认态未闭环（G1 阻断）**：U8 的 `OE̅`(pin13) 直接接地、`SRCLR̅`(pin10) 直接接 3V3_IO、`QH'`(pin9) 未连接，输出在首次有效锁存前即为活，而 SN74LV595A 上电状态不确定。`MUX_DISABLE`、`RC_DRIVE`、`ADDR0..3` 与两路复位在 FPGA 配置完成前没有已证明的默认态（`E3-RST-002`）。
5. **一处自我纠正**：U15(SN74LVC244A) 初看像「输出接电源」，核对官方 PW 封装引脚图后确认是 A/Y 交替排列的误读，**不是缺陷**（`E3-VIO-004`）。
6. **旧「IO848 / 47 脚供电桥」判据在 951 上有对象**：LINE `84827c5ae5d3dd1e`（3V3_IO、第 2 层、宽 14.14 mil）；3V3_IO 恰好 47 端点。原判「0 命中」是按文本搜 `IO848`，而它是该 LINE 的 id 前缀（`E3-MFG-004`）。
7. **但「单删分成 5+42」是 IOtail 派生源的统计，不适用于 951**。桥不能当冗余删，理由要换成 14.14 mil 载流截面 + C8 短去耦 + 底部参考/回流；「951 删桥仍连通」不构成删除许可（V4 IR-03，`E3-MFG-004`、`D-10`）。

## 交付文件

| 文件 | 内容 |
|---|---|
| `constraints.json` | **主产物**。32 条约束，每条含性质/状态/单位/适用对象/判据/来源/失效条件 |
| `open-decisions.md` | 11 项待决（D-05 已撤销、D-09/D-10/D-11 新增），含选项、影响、推荐；其中 5 项阻断 G1 |
| `CORRECTIONS-20261025.md` | 按 V4 独立审查的逐条纠错记录：撤销 3 条、升级 1 条、修正范围 2 条（含 IR-03 下游审计） |
| `INTERFACES.md` | J5/J6/J10/J12/J13/J20–J25 逐针网络表（脚本生成） |
| `MECHANICAL.md` | 板框/安装孔/禁布区/叠层/过孔/测试点/贴边器件（脚本生成） |
| `POWER-BUDGET.md` | 供电拓扑、压降、各轨负载、保护链、热、未实测项 |
| `TEST-PLAN.md` | TP-01…TP-12 实物判据，全部 UNMEASURED |
| `SOURCES.json` | 9 份来源（含官方手册编号/修订日期/URL/访问日期）与未验证清单 |
| `derived/*.json` | 派生事实，可复现，不含手抄数据 |
| `tools/*.py` | 解析与报表生成器（只读） |

## 复现

```bash
cd hardware/pcb-parallel/electrical
python tools/extract_design_facts.py     # 解析 epcb2 → derived/design-facts.json
python tools/generate_reports.py         # → derived/{interfaces,mechanical,rails}.json + INTERFACES.md + MECHANICAL.md
```

`extract_design_facts.py` 会打印源 SHA 与计数，可用于核对输入身份：

```
pcb_sha256 951ce88a1a2fcc2d758f9a53222a400cbddd3bc5b689cc2a37c98b8303d9ca4d
board 140.0 x 100.0 mm
components 227 | pads_with_net 899 | nets 256 | vias 649
```

227 件 / 899 节点 / 649 过孔 与检查点基线一致，可作为输入未漂移的独立旁证。

## 解析要点（给后续 Agent 省时间）

- `.epcb2` 是**日志文档**：每行 `{head}||{payload}|`，同 `(type,id)` 取 `ticket` 最大者；`payload` 为空串表示删除。
- 数组型 id 是**双重编码**（`"[\"PAD_NET\",...]"`），需二次 `json.loads`。
- PCB 图元坐标单位是 **mil（0.001 in）**，不是格式文档写的 0.01 in；按 139 mm 铺铜边界与 1.6 mm 焊盘反算确认。
- `REGION` 的 `["R", x, y_top, w, h]` 中 `y` 是**上边**，向下延伸 `h`；按此才能对上安装孔中心。
- `LAYER_PHYS.thickness` 也是 mil（1.378 = 35 µm 铜），合计 61.251 mil = **1.556 mm**。

## 给 M0 / V4 的接口

- **M0**：K1/K2/K3 批次必须遵守 `E3-MEC-003`（角部禁布区）、`E3-MFG-002`（线宽/过孔下限）、`E3-PWR-006`（5V 链 ≥0.5 mm）；任何约束变更请递增版本并通知 E3 重算受影响项。
- **V4**：可直接用 `constraints.json` 的 `criterion` 字段做核对清单；`summary.g1_blocking_ids` 是 G1 的必关项。
  `E3-VIO-004` 已排除 U15，不必重复提出。
  **本版已按 V4 的 2026-10-25 审查修订**：`E3-PWR-002`（R67）、`E3-MFG-004`（IO848）、`E3-RST-001`（pin11）
  三条原结论已撤销，`E3-RST-002`（上电合同）升为 G1 阻断。逐条见 `CORRECTIONS-20261025.md`，
  请勿再按 .1 版的三条旧结论核对。
- **R1/R2**：候选里若触及 5V 主链、底层 3V3_IO 桥、U13/U18 输入输出、J10 周边，先看对应约束的 `criterion`。

## 本版未做的事（明确边界）

- 未运行原生 DRC（本机 LCEDA Pro 4.1.71 的 CLI 可用，但客户端未初始化，headless 会话不存活；详见本会话 G0 记录）。
- 未做阻抗控制叠层；未做 EMC/ESD 仿真；未做热仿真。
- `final-electrical-review.json` 需等 M0 的 Bfinal 才能出，本版不伪造。
- 未下单、未询价、未联系供应商；`SOURCES.json` 里所有价格/库存类信息均未采集。
