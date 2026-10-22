# 构建与交付入口

适用于当前Tang Nano20K声音基线。新机械键、排滑音、真实右手触控与双屏尚未集成；当前包为开发快照，不是已验收成品。

## 唯一主工程

设备GW2AR-LV18QN88C8/I7，顶层`tdm_ship`，工程`src/gowin/tdm_synth/tdm_synth.gprj`，约束`src/constr/tdm_top.cst`及`tdm_top.sdc`。工程旁六份HEX表是构建输入，必须保留。9K bringup与并行合成工程不是默认发布入口；并行RTL仍用于黄金参考。

当前27MHz，512槽位，52,734.375Hz；I²S每声道16位，同一混合样本写入左右槽。当前CST仍是旧电容输入，不能直接接新键盘/DSI。

## 环境与构建

已验证综合工具为Gowin V1.9.11.03 Education。需要Windows PowerShell、Python 3、Icarus Verilog（iverilog/vvp）。依赖文件目前是必要库声明，不是锁定全部版本的环境。

在仓库根或发布包`code/`目录执行，路径替换为本机安装位置：

```powershell
$env:FPGA_MUSIC_GOWIN_HOME = 'Gowin安装目录（包含IDE和Programmer）'
$env:FPGA_MUSIC_IVERILOG = 'iverilog.exe完整路径'
$env:FPGA_MUSIC_IVERILOG_BIN = '包含iverilog.exe和vvp.exe的目录'
python -m pip install -r tools/requirements-test.txt
powershell -NoProfile -ExecutionPolicy Bypass -File tools/scripts/build_project.ps1
```

统一入口固定顶层并开启SSPI脚作GPIO，音频54/55/56脚需要此选项。通用`build_gowin.ps1`继续用于独立实验。若用上位机，另安装`tools/requirements-host.txt`，运行`python tools/host/dsp_gui.py`；模拟设备不提供实体声音。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/scripts/build_sims.ps1
python tools/scripts/regress_all.py --full
```

部分历史专项脚本仍有本机路径假设；提供它们用于复核，不宣称全环境已经迁移。测试范围、失败项与环境均须记录，不能把模块PASS当整机PASS。

## 烧录与实体运行

```powershell
# 检查路径、打印设备和码流哈希，不操作硬件
powershell -NoProfile -ExecutionPolicy Bypass -File tools/scripts/program_project.ps1
# 明确执行SRAM写入，掉电失效
powershell -NoProfile -ExecutionPolicy Bypass -File tools/scripts/program_project.ps1 -Program
```

设备GW2AR-18C；操作2为SRAM Program，依据本机Programmer --help核定。未执行本轮实际烧录。最终Flash固化另作实体验收。旧`flash.cmd`及`flash_sram.cmd`统一转到此入口，默认预览。

板载MAX98357A：EN=51、DIN=54、LRCK=55、BCK=56；实际板版号、扬声器与供电按硬件资料复核。本页不是未冻结的新前端接线图。

## 打包及正式提交

```powershell
python tools/scripts/package_release.py --version dev-20261013
python tools/scripts/package_release.py --version final --submission
```

白名单配置为`delivery/package.json`。输出`release/<版本>/`及ZIP，检查工程引用与HEX，登记每个文件的SHA256、Git状态、代码身份与证据来源。不自动综合、测试、烧录、上传；ZIP用于开发传递，不能改扩展名冒充RAR。

正式提交模式要求`delivery/status.json`记录规则复核、人工验收和实物证据，且报告/视频/授权/最终BOM及接线文件实际存在。当前缺项会拒绝正式打包。文件存在仍不代表真实验收，签字/审核由人完成。

截止2026-11-04 18:00；上传格式、匿名要求、大小和2026模板以提交平台为准。当前记录PDF/MP4/RAR/授权PDF仍须复核。视频须展示实物，仿真WAV不得冒充板上录音。

基线PnR证据源为`fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12`，只验证声音基线。最终冻结后需重做构建、板测、延迟与打包，源文件变化不自动令旧证据适用于新版。
