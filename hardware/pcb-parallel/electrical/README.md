# E3 电气、接口与可装配性合同（951 原生 PCB）

角色：E3　版本：`e3-2026-10-25.1`　作者：本会话（用户 2026-10-25 指派）
输入源：`hardware/checkpoints/pcb-951ce88a-20261025/native/pcb/PCB1.epcb2`
源 SHA256：`951ce88a1a2fcc2d758f9a53222a400cbddd3bc5b689cc2a37c98b8303d9ca4d`

本目录只读设计源，不修改 RTL、原理图、候选 PCB 或正式板。所有结论绑定上述 SHA；
源一变，本版约束全部失效，须递增版本号。

## 一分钟结论

1. **951 上没有 FPGA**。J5/J6 是 2×20P 母座，插 Nano20K 模块；`3V3_IO`（46 焊盘）**只由模块供入**，板上没有该轨稳压器。
2. **一个已确认缺陷**：U17(TPS2553) 的限流电阻 R67 = 2.37 kΩ，低于数据手册 15 kΩ 下限，**限流功能实际失效**（`E3-PWR-002`，待用户批准改为 26 kΩ）。
3. **一处文字与几何冲突**：任务卡写「J10 pin11 NC」，但原生网表里 J10.11 = 触控复位 `TP_RESET_MOD_N`；J10.7 也不是 RC 复位，而是 595 输出经缓冲（`E3-RST-001`）。
4. **一处自我纠正**：U15(SN74LVC244A) 初看像「输出接电源」，核对官方 PW 封装引脚图后确认是 A/Y 交替排列的误读，**不是缺陷**（`E3-VIO-004`，保留记录避免 V4 重复提出）。
5. **一处判据失效**：CONTRACT 里的「IO848 47 脚供电桥」在 951 上检索为 **0 命中**，该判据只对 `offline/IOtail` 派生源有效（`E3-MFG-004`，需 M0 界定）。

## 交付文件

| 文件 | 内容 |
|---|---|
| `constraints.json` | **主产物**。32 条约束，每条含性质/状态/单位/适用对象/判据/来源/失效条件 |
| `open-decisions.md` | 8 项待决，含选项、影响、推荐；其中 5 项阻断 G1 |
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
- **V4**：可直接用 `constraints.json` 的 `criterion` 字段做核对清单；`summary.g1_blocking_ids` 是 G1 的必关项。`E3-VIO-004` 已排除 U15，不必重复提出。
- **R1/R2**：候选里若触及 5V 主链、底层 3V3_IO 桥、U13/U18 输入输出、J10 周边，先看对应约束的 `criterion`。

## 本版未做的事（明确边界）

- 未运行原生 DRC（本机 LCEDA Pro 4.1.71 的 CLI 可用，但客户端未初始化，headless 会话不存活；详见本会话 G0 记录）。
- 未做阻抗控制叠层；未做 EMC/ESD 仿真；未做热仿真。
- `final-electrical-review.json` 需等 M0 的 Bfinal 才能出，本版不伪造。
- 未下单、未询价、未联系供应商；`SOURCES.json` 里所有价格/库存类信息均未采集。
