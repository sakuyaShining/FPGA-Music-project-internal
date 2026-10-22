# 独立接续流程

以下PowerShell命令从解压后的包根目录运行。Python脚本只用标准库。首次测试前确认磁盘空间：黄金轨迹约100MB，测试会再生成相近体量；完整Gowin构建需额外空间，优先D盘。

```powershell
python tools/verify.py
python tools/bootstrap.py --destination D:/FPGA-Project/codex-builds/fpga-m1-agent-work
```

目标必须是不存在的新目录，父目录必须存在。bootstrap复制全部源与本地参考，**逐文件确认RTL/HEX/VH未改**；只适配common/check脚本的路径和新构建目录。适配diff、源指纹及受保护测试输入写入新工作目录的`HANDOFF-WORKSPACE.json`。不会创建Git分支、提交、下载或共享旧build/evidence联接。

本机工具默认位置：

- Python：`C:/Program Files/python/python.exe`。
- Icarus：`D:/iverilog/bin/iverilog.exe`、`D:/iverilog/bin/vvp.exe`。
- Gowin：`D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe`。
- 器件：`GW2AR-LV18QN88C8/I7`，device GW2AR-18C，原构建top `joint_timing_top`、`-use_sspi_as_gpio 1`。

可通过`FPGA_IVERILOG`、`FPGA_VVP`、`FPGA_GOWIN_GW_SH`环境变量适配**安装路径**；换工具版本、器件、参数或约束须重新记录，不能继承旧物理结论。未随包重分发工具安装程序。

## 回归

```powershell
python tools/run_checks.py --workspace D:/FPGA-Project/codex-builds/fpga-m1-agent-work --suite native --run-id baseline01 --preflight-only
python tools/run_checks.py --workspace D:/FPGA-Project/codex-builds/fpga-m1-agent-work --suite native --run-id baseline01
python tools/run_checks.py --workspace D:/FPGA-Project/codex-builds/fpga-m1-agent-work --suite pitch --run-id baseline01
python tools/run_checks.py --workspace D:/FPGA-Project/codex-builds/fpga-m1-agent-work --suite engine --run-id baseline01
```

每次独立证据目录为`工作目录/evidence/运行ID-套件`，存在时拒绝覆盖。修改RTL后换运行ID，不覆盖baseline01。source_inputs和源变化列表写入suite-run.json；PASS只代表相应数字回归。脚本会从包内不可变参考复制原TB/刺激，禁止直接修改这些受保护文件；新增测试请使用新文件名。更改实现导致旧TB的内部层次接口不再适用时，保留原测试/失败，新增按外部行为比较的测试并说明覆盖关系，不能删断言或将故障反例转为通过。

| suite | 内容/使用范围 |
|---|---|
| native | 原生双异步读RAM与独立数组、4种深宽配置 |
| pitch | 4配置音高/epoch全组对照和交换RAM读口反例；重定时新增边界用例仍必须补 |
| engine | 原71号三组完整逐拍PCM/I²S/事件黄金比较，985PCM/506645拍；保留原启动未知边界 |
| envelope / phase_wrap | 独立包络参考、最大分频回绕；从78号脚本适配源目录、功能仿真宏与原生RAM模型 |
| joint | 两延迟音乐录入/图案播放、GSR与录制错误反例；有force，不是产品协议 |
| delta / sensor | 碰撞旧值/校准与位置、扫描；不是模拟资格 |
| scan | 临时DSP/RAM历史链和故障反例；不等于产品命令 |
| renderer | 8388608组像素穷举及单边界故障；改可视化时使用 |

源码table初始化依赖仿真cwd：原检查器已在需要时使用`engine/src`。不要在别的cwd直接运行vvp后忽略readmemh警告。TIMING_RTL_SIM只替代PLL作功能仿真，DSP测试需要GSR模型/上电脉冲；仿真宏不得进入实际Gowin构建。

M1涉及顶层路径时应运行native、pitch、engine，按范围追加envelope/phase_wrap及joint。配置/ADSR/协议的专项资产及本机入口另见source-map.json；包内M1套件不是整机测试全集，新增功能不能只靠985PCM兼容性签收。

## 完整PnR与审计

只在回归通过后，在新工作副本构建。每次用新标签；修改源码后重做，不重用旧run.json。

```powershell
python D:/FPGA-Project/codex-builds/fpga-m1-agent-work/build_board.py build_m1_v0 nominal
python tools/audit_build.py --workspace D:/FPGA-Project/codex-builds/fpga-m1-agent-work --label build_m1_v0 --output D:/FPGA-Project/codex-builds/fpga-m1-agent-work/evidence/m1-v0-audit.json
```

审计返回0才是**M1结构探针限定STA**通过；返回2表示失败/不完整，不能因为Python已写JSON就判通过。构建退出0但负slack仍失败。审计核对所有build输入与当前工作源、原CST/SDC、55个SIP端口、14个探针外部脚及四类slack。正常通过后再按需要构建`build_m1_stress_v0 stress`并独立审计。原超时上限900秒；超时保留结果，不得标通过或覆盖重跑。

上述build/audit只适用于M1探针。M2真实顶层必须按PCB合同更新工程和完整外部SDC，并建立相应审计；不能为了通过这个固定14脚审计而继续接假输入。当前探针hold来自临时链，M1可记录它而集中修setup，但任何完整签收仍需四类STA全部非负。

## 不可直接照跑的旧工具

冻结源还保留原prepare.py、prepare_probe.py、audit_current.py、audit_candidate.py、verify_delivery.py、budget.py等历史工具。它们有旧路径、上游白名单或生成副作用，**不能直接作为新工作副本的验收入口**。run_checks/build/audit使用上面明确给出的入口。特别是旧budget.py若重新执行，会读取动态06df状态，不再代表87号当时的冻结预算；不要重写87号预算身份来消除硬件漂移。

原始84源全量为common.sources()三个目录：engine/src、engine/rtl、rtl；不要把support、tb/vendor、reference或生成网表加入综合，避免重复module或把模型当硬件。需要Git记录时先检查所在仓库及未跟踪内容，选择性纳入新工作成果；本包没有自动提交/推送。
