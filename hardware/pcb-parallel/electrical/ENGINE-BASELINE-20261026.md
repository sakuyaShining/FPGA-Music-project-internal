# 引擎侧基线：首次原生 DRC（951）

角色：E3　版本：`e3-2026-10-26.1`　日期：2026-10-26
源绑定：`hardware/checkpoints/pcb-951ce88a-20261025/native/pcb/PCB1.epcb2`
源 SHA256：`951ce88a1a2fcc2d758f9a53222a400cbddd3bc5b689cc2a37c98b8303d9ca4d`

> 本文记录的是**引擎自己给出的结果**，不是我的解析器推算。这是本项目第一次跑通嘉立创EDA 的原生 DRC。
> 在此之前，历次角色（含 V4 独立审查）记录的都是「原生 DRC 不可用 / 客户端从未初始化」。

---

## 0. 一句话结论

**原生 DRC 报告 42 项违例，全部是 `Connection Error`，分布在 12 个网络上，没有任何其它类别的违例。**
这个数字与项目里长期引用的「42 项未连通」完全一致，但现在有了引擎侧的独立确认。

---

## 1. 引擎是怎么连上的

走的**不是** `lceda-pro` 内置 CLI（那条路 `open --path` 返回 `ok:true` 但工程永远停在 Start Page），
而是 `easyeda-api` 技能提供的 WebSocket 桥：

```
AI  ←HTTP→  桥服务 Node.js (127.0.0.1:49620)  ←WebSocket→  嘉立创EDA + run-api-gateway.eext
```

三个条件缺一不可，前两个是环境准备，第三个是本次真正卡住的地方：

| # | 条件 | 本次状态 |
|---|---|---|
| 1 | 桥服务运行（端口 49620–49629，握手 `service: "easyeda-bridge"`） | 由 `scripts/bridge-server.mjs` 启动，依赖仅 `ws` |
| 2 | EDA 安装 `run-api-gateway.eext` 扩展 | v1.0.6，已安装 |
| 3 | 该扩展的 **允许外部交互（External Interactions）** 打开 | 曾为 `false`，打开后重启 EDA 才连上 |

第 3 项是 GUI-only 权限，API 无法设置（参考文档里没有任何 `ExternalInteraction` 接口）。
权限变更**不会**触发重连——扩展在 `onStartupFinished` 时连接，权限在启动后打开时那次连接已经失败。

**关键发现**：`dmt_Project.getAllProjectsUuid()` 无参调用永远返回 `[]`。
正确用法是传入**工程目录路径**（在本环境里它就是 `team.uuid` 的值）：

```javascript
const teams = await eda.dmt_Team.getAllTeamsInfo();      // 实际是 ["…\projects", "…\example-projects"]
const ids   = await eda.dmt_Project.getAllProjectsUuid(teams[0].uuid);
```

这一步之前一直卡着，是因为文档示例里的「team」在本环境被实现成了目录路径。

---

## 2. 事实交叉验证：引擎 vs 独立解析器

我的解析器（`tools/extract_design_facts.py`）与引擎逐项对照。两者完全独立：一个读 `.epcb2` 文本日志，一个走编辑器 API。

| 事实 | 引擎（API） | 我的解析器 | 一致 |
|---|---|---|---|
| 器件数 | `pcb_PrimitiveComponent` = **227** | 227 | ✅ |
| 焊盘数 | `pcb_PrimitivePad` = **1063** | 1038 元件焊盘 + 25 板级 = 1063 | ✅ |
| 过孔数 | `pcb_PrimitiveVia` = **649** | 649 | ✅ |
| 走线段数 | `pcb_PrimitiveLine` = **3606** | 各层合计 3606 | ✅ |
| 铺铜数 | `pcb_PrimitivePour` = **4** | 4（全为 GND） | ✅ |
| 网络数 | `pcb_Net.getAllNetsName()` = **256** | 256 | ✅ |
| 铜层 | Layer 1 / 2 / 15 / 16 | Top / Bottom / Inner1 / Inner2 | ✅ |

> 焊盘 1063 的分解可复核：`derived/design-facts.json` 里 `components[*].pads` 共 **1038** 个槽位，
> 其中**有网 899**（= `counts.pads_with_net`）、**无网 139**；再加 `board_level_pads` 25 = 1063。
> 注意 `counts` 只暴露了 899 这个「有网」子集，直接拿它和引擎的 1063 比会差 164，那不是不一致，是口径不同。

上表七项于归档后**重新实测一遍**（`probes/facts.js`），返回 227 / 1063 / 649 / 3606 / 4，
网长 16 条逐条复现（含三条 0）。即：这些数字不是一次性快照。

**网长（`pcb_Net.getNetLength()`，单位 mil）**——这是最关键的交叉验证：

| 网络 | 引擎 mil | 换算 mm | 解析器 mm | 一致 |
|---|---|---|---|---|
| `ADDR0` | **0** | **0.00** | 0 | ✅ |
| `MUX_DISABLE` | **0** | **0.00** | 0 | ✅ |
| `KEY_QH` | **0** | **0.00** | 0 | ✅ |
| `ADDR1` | 224.20 | 5.69 | 5.7 | ✅ |
| `PRESET1` | 236.20 | 6.00 | 6.0 | ✅ |
| `PRESET2` | 522.70 | 13.28 | 13.3 | ✅ |
| `EDIT` | 544.23 | 13.82 | 13.8 | ✅ |
| `ENC_B` | 473.12 | 12.02 | 12.0 | ✅ |
| `ENC_PUSH` | 687.03 | 17.45 | 17.5 | ✅ |
| `ENC_A` | 744.80 | 18.92 | 18.9 | ✅ |
| `INPUT_LOAD_N` | 930.99 | 23.65 | 23.6 | ✅ |
| `BUS_SCK` | 3705.15 | 94.11 | 94.1 | ✅ |
| `RC_DRIVE` | 13649.69 | 346.70 | 346.7 | ✅ |
| `ADDR3` | 15314.49 | 389.00 | 389 | ✅ |
| `3V3_IO` | 19164.13 | 486.77 | 486.8 | ✅ |
| `ADDR2` | 19745.72 | 501.54 | 501 | ✅ |

单位已实证：`getNetLength` 返回 **mil**（× 0.0254 = mm），与 `.epcb2` 数据坐标同单位。

**结论**：`BASELINE-STRUCTURE-20261025.md` 里「`ADDR0` / `MUX_DISABLE` / `KEY_QH` 铜量为零」的判定，
从「我的解析器算的」升级为「引擎与解析器独立同结论」。

---

## 3. 原生 DRC 基线

```
pcb_Drc.check(true, false, true)   // strict=true, 不弹 UI, 返回详细列表
规则配置："自定义配置"
检查类别：Spacing / Physics / Plane / Expansion / Copper Analysis /
          Drill Hole Analysis / Silkscreen Analysis / Solder Mask Analysis（共 30 项）
```

| 指标 | 值 |
|---|---|
| 违例总数 | **42** |
| 类别数 | **1**（仅 `Connection Error`） |
| 涉及网络 | **12** |
| 违例对象 | SMD Pad 35、Via 5、TH Pad 2 |

### 按网络分布

| 网络 | 违例数 | 已知铜量 | 判读 |
|---|---|---|---|
| `ADDR1` | 9 | 224 mil / 5.7 mm | 短桩，未布完 |
| `MUX_DISABLE` | 7 | **0** | 从未布线 |
| `ADDR0` | 7 | **0** | 从未布线 |
| `PRESET1` | 3 | 236 mil / 6.0 mm | 短桩 |
| `BUS_SCK` | 2 | 3705 mil / 94.1 mm | 半程 |
| `PRESET2` | 2 | 523 mil / 13.3 mm | 短桩 |
| `EDIT` | 2 | 544 mil / 13.8 mm | 短桩 |
| `ENC_A` | 2 | 745 mil / 18.9 mm | 短桩 |
| `ENC_B` | 2 | 473 mil / 12.0 mm | 短桩 |
| `ENC_PUSH` | 2 | 687 mil / 17.5 mm | 短桩 |
| `INPUT_LOAD_N` | 2 | 931 mil / 23.6 mm | 短桩 |
| `KEY_QH` | 2 | **0** | 从未布线 |
| **合计** | **42** | | |

原始返回：`evidence/drc-baseline-951-20261026.json`（42 条逐项含对象名、网络、坐标、错误说明）。
采集上下文（端口、扩展版本、调用参数、源 PCB SHA、归一化方式、逐项自洽校验）见
`evidence/drc-baseline-951-20261026.meta.json`；实际执行的 JS 见 `evidence/probes/`。

### 为什么「全部是 Connection Error」这件事重要

42 项里**没有一条**是间距、线宽、过孔尺寸、锐角、孔环、短路、丝印、阻焊类违例。
也就是说：**这块板在物理规则层面是干净的，缺的只是没画完的连接。**

这与「布局一开始就错了 / 太密布不下」的假设直接冲突，而与「半成品」的判断一致。

### 可复现性（已实测）

归档后同一次会话内，用同一个 `probes/drc.js`、同一个桥端口重跑了一遍：

| 比对项 | 结果 |
|---|---|
| 违例总数 42 | 相同 |
| 涉及网络 12 及逐网条数 | 相同 |
| 42 条的对象 `obj1.suffix` | 相同 |
| 42 条的 `pos` 坐标 | **逐位相同** |
| `errorType` / `errorObjType` 分布 | 相同 |
| 网络排列顺序 | 相同 |
| `globalIndex`（`errNNN`） | **不同，整体 +42** |

唯一差异是 `globalIndex`，且 42 条的偏移量全部恰好是 +42，即上一次运行的违例条数。
结论：**这是会话级单调计数器，不是稳定标识。** 跨次比对不要用它做键，请用
`(net, obj1.suffix)`。除此之外，DRC 结果完全确定、可复现。

---

## 4. 对现有结论的影响

| 对象 | 变化 |
|---|---|
| `D-13`（工序口径） | 证据补强：42 项 = 12 条网未布完，不是 42 个设计缺陷。「不退化」的分母确实不存在 |
| `BASELINE-STRUCTURE-20261025.md` §2 | 三条零铜网络由引擎独立确认，不再是单方推算 |
| G0 检查点 | M0 原本要交的「实际原生 DRC」，现在有了可复现的取法与基线数字 |
| A 方案工作量 | 42 项全部落在 12 条网上，无额外返工项。`BASELINE-STRUCTURE` 估的「约 712 mm」只指 `ADDR0`/`ADDR1`/`MUX_DISABLE` 三条（各 237 mm 最小生成树），不是 12 条网的合计；引擎实测这三条**现有**铜量仅 5.7 mm（`ADDR1` 224.2 mil，另两条 0），说明 712 mm 是待施工量而非已有量 |
| V4 `connectivity-diagnostic.json` | 独立方法与引擎在「12 网 / 42 项」上一致，V4 的有限模型结论得到旁证 |

---

## 5. 口径与边界（不要超出这些）

1. **坐标不是板坐标。** DRC 返回的 `pos`（如 `x=326.48, y=169.78`）落在画布坐标系，与 `.epcb2`
   数据坐标存在偏移，本文**未做换算**。要定位对象请按 `obj1.suffix`（如 `U9_2`、`e915`）在 GUI 里查，
   **不要**用数值反推板内位置。
2. **规则启用状态不可见。** `getCurrentRuleConfiguration()` 返回 8 大类 30 个检查项及其间距表
   （`Safe Spacing` 实值 0.1524 mm = 6 mil），但**没有暴露各检查项的启用开关**。
   因此「零间距违例」只能表述为「本次返回结果中无该类违例」，不能断言「间距检查一定执行了」。
3. **`globalIndex` 不可作键。** 它是会话级单调计数器，复跑整体平移（见 §3 可复现性）。
   跨次比对请用 `(net, obj1.suffix)`，不要用 `errNNN` 或 `position` 做唯一标识。
4. **未保存、未修改。** 全过程只读。DRC 不改变几何，但可能使文档进入未保存状态；
   本次未调用 `save()`，`.epcb2` 字节未变（与 951 SHA 一致，见 §2 源绑定）。
5. **`check()` 与 `autoRouting()` 都是 beta API**（文档标注「不要用于生产环境」）。
6. **这不是制造放行。** 零连接性违例之后仍需：真实规则复核、SI/PI、热、DFM、装配验证。
   「零 DRC 不等于整机性能合格」。
7. **本文件不是 M0 签核。** E3 只提供电气侧证据；G0/G4 的签核权在 V4 与用户。

---

## 6. 复现步骤

前置：桥服务在 49620 运行、EDA 已装 `run-api-gateway` 且允许外部交互、工程已打开 PCB。

```bash
# 0. 确认链路
curl -s http://127.0.0.1:49620/health
#    → {"service":"easyeda-bridge","edaConnected":true,...}

# 1. 事实核对（器件/焊盘/过孔/线/铺铜/层/层叠）
python tools/bridge_probe.py evidence/probes/facts.js

# 2. 网表与网长
python tools/bridge_probe.py evidence/probes/netlen.js

# 3. 原生 DRC（约 10–30 秒）
python tools/bridge_probe.py evidence/probes/drc.js

# 4. 当前规则配置
python tools/bridge_probe.py evidence/probes/rules.js
```

`tools/bridge_probe.py` 会自动扫描 49620–49629、校验 `service` 标识、检查 `edaConnected`，
再 `POST /execute` 执行传入的 JS 文件并打印 JSON。

`evidence/probes/netlen.js` 里硬编码了 PCB 文档 UUID `c3fd8656cf425e9f`。工程若重新导入，
该 UUID 会变，需先跑一次文档枚举取新值，否则第 2 步会打开失败。

注意：桥服务的 `REQUEST_TIMEOUT_MS` 是 **30 秒**硬编码。首次调用 DRC 曾因超时返回 HTTP 500，
重试即成功；如需稳定长任务，应调大该常量后重启桥。

---

## 7. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| `e3-2026-10-26.1` | 2026-10-26 | 首次建立：引擎侧事实交叉验证 + 原生 DRC 基线（42 项 / 12 网 / 全为 Connection Error） |

### 本版补充（同版内修订，未另起版本号）

- 补 `evidence/drc-baseline-951-20261026.meta.json`：采集上下文、调用参数、源 PCB SHA、归一化方式、逐项自洽校验。
- 归档 `evidence/probes/`（`facts.js` / `netlen.js` / `drc.js` / `rules.js`），§6 的复现步骤改为指向真实文件。
- 归档后重跑事实、网长、DRC 三项，确认可复现；新增 §3「可复现性」与 `globalIndex` 不可作键的边界（§5.3）。
- 补焊盘 1063 的分解式（1038 元件 + 25 板级；其中 899 有网、139 无网），说明 `counts.pads_with_net` 是子集口径。
- 顺带修正 `constraints.json` 的 `summary.total`：32 → 33（条目数与 `by_status` 合计一直是 33，仅 total 未同步）。
