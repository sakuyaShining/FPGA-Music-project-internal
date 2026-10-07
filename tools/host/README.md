# 上位机（PyQt5 + QSS）使用说明

## 新增：完整配置文件基础（2026-10-07）

`instrument_config.py` 已提供独立的 JSON 配置草稿创建、校验、保存与读取 API，
不依赖 Qt，不连接设备，不发送帧。当前 GUI 的文件按钮和硬件应用适配器尚未接入。

配置包含名称、预设身份、16 分量谱/模式、持续/瞬间/混合方式与包络草稿、颤音和效果参数。
时间为毫秒，颤音/合唱速率为毫赫兹，颤音深度为音分；反馈为 Q8。数据范围只是格式校验，
不代表当前 RTL 能支持全部范围。混合分量分组为候选表达，模板的 8/8 分组与默认参数不是已批准的产品决定；
后续试听若选择不同混合模型，应迁移 schema，不能静默丢弃旧参数。

```powershell
# 本地创建草稿，路径由用户选择；不写入 FPGA
python tools/host/instrument_config.py new sim_build/my_config.json --name "我的音色" --mode hybrid
python tools/host/instrument_config.py check sim_build/my_config.json

# 文件往返、非法输入和写入失败验证
python -m unittest discover -s tools/host -p test_instrument_config.py -v
```

读取先完整验证并返回独立对象；非法字段、重复字段、不支持版本和不合法数值报可读错误。
保存先校验，再用同目录临时文件原子替换；失败不覆盖已有配置。
CLI 失败退出码为 1。文件不包含 PCM、按住的音符、振荡器相位或效果器缓冲。

目前完成的是 R02 的文件层。文件校验通过不能代替设备能力检查、GUI 导入/应用闭环或 RTL 验收。

> 单文件 exe：`tools/host/dist/dsp_gui.exe`（约 37.7 MB，免装 Python）
> 源码运行：`python tools/host/dsp_gui.py`

## 一、文件构成

| 文件 | 作用 |
|---|---|
| `dsp_gui.py` | 主界面 v2（键盘+八度 / 表情轴 / 手绘画谱+逐声部塑形 / 定序器 / 电极遥测 / 寄存器表 / 日志） |
| `serial_link.py` | 通信层：**真串口**+**模拟设备**，外加量程判定与打包路径解析 |
| `theme.qss` | 主题样式表（"好看"全部集中在这里，改一行即换肤） |
| `build_exe.py` | 一条命令打包成单文件 exe，并**自测产物**|

## 二、三种"设备"状态（顶部徽标一眼可分）

| 徽标 | 含义 | 能做什么 |
|---|---|---|
| 🟢**真实串口**| 真的在跟板子说话 | 全部功能；声音由**FPGA**产生 |
| 🟡**模拟设备**| 进程内模拟：只存寄存器 + 合成遥测数字 | 走流程、看字节/回读/遥测柱判定；**不出声**|
| ⚪**未连接**| — | 只能点，不发帧 |

**模拟设备不是"电脑在算音频"**—— 它**根本不产生声音**。详细的边界见文末"硬底线"。

## 三、怎么用

1.**开发/无板**：端口选「【模拟设备】」→ 连接 → 随便点（键盘、塑谱、扫描 16 路）
2.**连板子**：装好驱动 → 刷新端口 → 选 `COMx` → 连接 → 顶部应显示 🟢**真实串口**
3.**上板第一件事**：点**扫描 16 路**—— 按 §1 的判据逐根看判定颜色：
 - 🟢 量程可用（松手 raw∈[20,2000]，按住 raw ≥1.3×base）
 - 🔴 封顶（RC 太慢）／太快（分辨率不足）⇒ 先调外接 R/C（建议每根**1 MΩ + 22 pF**）
4.**导出帧序列**：把界面上做过的所有帧写成一个文本文件 （**与 `dsp_host.py --emit` 同格式**，
 可被仿真测试台原样重放 —— 界面行为因此可复现、可回归）

## 四、自测（可证伪）

```powershell
python tools/host/dsp_gui.py --selftest      # 源码模式
tools\host\dist\dsp_gui.exe --selftest       # exe 模式（--windowed 无 stdout，结果落盘）
```

产物（`sim_build/gui/`）：
- `gui_preview.png` —— 界面截图（离屏渲染）
- `selftest_report.txt` —— 含**`RESULT gui_selftest=PASS`**与十项**帧一致性**检查

十项检查的含义：界面发出的字节必须与 `dsp_host.py` 的对应命令**逐字节相同**（音符/八度、塑谱全刷与逐声部、效果器、遥测、表情轴、定序器播放与停止、预设）
（地址表与帧构造直接 `import dsp_host`，**不另抄一份**—— 从根上防"上位机与 RTL 各改各的"）。

## 五、重新打包

```powershell
python tools/host/build_exe.py
```

它会：检查/安装依赖 → `PyInstaller --onefile --windowed` →**运行 exe 的 `--selftest` 验证产物**。

要点/坑（都踩过）：
-**`pyserial` 必须在打包前就装好**—— exe 冻结后**不能**再用系统里的 pyserial；
 打包时没装 ⇒ exe 只能"模拟设备"（自测报告里会明写 `打包内含 pyserial = 无 ✗`）
-**`--add-data` 必须用绝对路径**—— PyInstaller 3.6 会按 `--specpath` 目录解析相对路径，
 拼成 `tools\host\tools\host\...` 找不到
- 三份 data 缺一不可：`theme.qss`（主题）、`dsp_host.py`（协议表，缺了 exe 里 import 不到）、
 `regmap_baseline.csv`（模拟设备的真实上电默认值，缺了会全 0）
-**本机 pip 的系统是坏的**（`ProxyError` / `getaddrinfo failed`）：`NO_PROXY=*` 可绕过
 （`build_exe.py` 已自动设置 ；手工装包时这样写：
 `$env:NO_PROXY='*'; python -m pip install pyserial`）
- 打包中间产物 `tools/host/build/`（约 41 MB）可随时删

## 六、硬底线（用户定的，必须守）

>**有板子的时候，电脑仅仅是展示界面，不是计算工具。**

| # | 约束 | 现状 |
|---|---|---|
| 1 | 协议里**没有**音频样本口 | 地址表 44 项全是参数/遥测（`dsp_host.py --check-map` 可对账） |
| 2 | 音频样本通路**永不经过 PC**| PC 只发参数级数据（实测 26 帧=52 B / 2.84 s ≈ 18 B/s） |
| 3 | 若将来加"本地发声引擎"，**连上真串口必须强制停用**| ⏳ 接口预留（`SerialLink` 与本地引擎互斥） |
| 4 | 界面/日志/导出文件三处标注设备类型 | 徽标 + 日志 + 导出表头 |
| 5 | 备好"脱机自证"演示动作（拔数据线，板子自己弹） | ✅ v2 底部**定序器面板**：下载曲谱→▶播放→拔线，片上定序器自己演奏 |

另注：项目复核记载**M1 判定为"现场演示可分别操控，PC 端不算"**——
所以上板演示时应用**触摸电极**操控，PC 键盘只作故障兜底 。
