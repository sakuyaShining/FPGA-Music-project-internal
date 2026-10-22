# 审计复现与证据

源基线：`90e891db4c0d3e086889d9ccd476bae4e9e16266`。日期2026-10-06，时区Asia/Shanghai。产品文件保持原样；所有新反例只在仿真中运行，没有接触串口、烧录器或真实电极。

## 数字反例

执行：

```powershell
python tools/scripts/audit_probe_20261006.py
```

运行器使用项目原有 `D:\iverilog\bin`，源路径由脚本自身解析，产物写到忽略的 `sim_build/audit_20261006`。**退出0只表示诊断完成，不表示产品通过；反例的expected/received差异才是证据。** [results.json](results.json) 是本轮原始输出；各同名子目录内 probe.v 是实际编译的激励。参数缩短的 strip 测试按时钟拍数验证状态逻辑，不是测量真实100ms。

| 反例 | 关键输出 |
|---|---|
| i2s_standard | expected1234，received2468，标准接收模型等待一个完整BCK后开始下一字 |
| pad_chord | 8键触摸，seen00000ff，active00000003；证明消费和记边沿不一致 |
| note_map / busy | 两事件紧邻，active00000001，仅首事件保留 |
| note_map / refresh | slot0首泛音50→187，使用了最后另一个音符的力度 |
| note_map / note-off | slot0首泛音50→200，关门分支绕过力度与谱形 |
| note_map / Nyquist | MIDI108、16倍比例，完整21308176，截断4530960，kill0 |
| allocator | 持60，按放61..91后按92；slot0从60变92，其他组未按住 |
| group_boundary | 同组load跨周期；slot0..7的pp1/ppr1与slot8..15相反，消费横跨两轮 |
| warm_reset | 音符后拉低再释放rst_n，active00000001，预期复位静音00000000 |
| strip_switch | 候选换格继承计时导致过早提交；已提交后连续换格不再提交 |

serial_probe.json记录一个**进程内假串口**：请求0x60，收到回显0xEE和值0xAB，SerialLink仍返回0xAB。没有实际打开串口。

## Git与工具证据

- inventory.json：基线跟踪数量、Python AST解析、公开树共同文件内容差异。只依据已提交树，不把后来新增的审计文件算进基线。
- git_probe.json：独立合成Git测试库的发布脚本输出。已有public分支时apply退出1；内容检查发现1项命中后仍提交且退出0。测试库在忽略的sim_build/audit/git_fixture，不是产品库。
- detached dry补充实测：在上述测试库执行 `git checkout --detach` 后 `make_public.py --dry`，结束HEAD变为main。普通feature分支的dry则保留feature；真实工作树没有执行该发布脚本。
- tdm_synth.log.audit.txt：此次重新综合的日志，明确Current top module为tdm_ship。
- tdm_synth.rpt.txt.audit.txt：PnR结果，2026-10-06 17:14:07，Gowin V1.9.11.03 Education，PlaceOpt2/RouteOpt2、SSPI释放。
- tdm_synth.timing_paths.audit.txt：此次SETUP slack15.229ns，原始关键路径。文件新鲜度检查在17:14通过。
- selftest_report.txt.audit.txt：本轮GUI离屏自测FAIL，定序器测试仍期望0x05；产品和CLI实际使用0x01。
- extra_results.json：现有LED、I²C、pad_pitch测试的原始输出。LED和pad_pitch通过；I²C三个用例失败，vvp退出0。该结果不能单靠进程退出码当作通过。
- regctl_judge.audit.txt：本次09 regctl完整判据，唯一失败是E7旧LED数值协议；音符起落与音频非零比例的原始统计同在该文件。
- regress_result.audit.txt：本轮完整回归汇总，30/31通过、进程退出1；唯一失败09 regctl。F1谱外能量1.99%，峰位最大偏差1.61Hz；16组TDM黄金参考均0/2495不符。
- manifest.json：源SHA和审计文档、复现脚本、证据文件SHA256，用于识别本次归档内容。

## 运行命令与边界

```powershell
git status --short --branch
git fsck --full
git ls-remote --heads internal
git ls-remote --heads public
git diff public main

powershell -NoProfile -ExecutionPolicy Bypass -File tools/scripts/build_sims.ps1
python tools/scripts/regress_all.py --full
powershell -NoProfile -ExecutionPolicy Bypass -File tools/scripts/build_gowin.ps1 -Project src/gowin/tdm_synth/tdm_synth.gprj -SspiAsGpio -PlaceOpt 2 -RouteOpt 2
python tools/scripts/check_timing.py --require-fresh
python tools/scripts/cst_audit.py

$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONIOENCODING = 'utf-8'
python tools/host/dsp_gui.py --selftest
```

build_sims第一次在新checkout输出目录缺失，22项失败、1项成功，退出1。仅补其目标父目录后重跑23项编译成功，退出0。没有修改RTL或该构建脚本。不能用“补目录后通过”覆盖首次干净构建失败记录。

全量回归最终为**30/31通过，退出1**，对应副本已保存。F1运行目录缺vel_wtab.hex仍通过，是测试模式绕开演奏装载链的结果。完整回归即使全部绿，也只能证明它实际包含的判据；标准I²S、和弦busy、声部释放/回收、暖复位和组边界等新增反例不在其现有判据中。

GUI和综合生成的三个原有跟踪文件（gui_preview.png、selftest_report.txt、gprj.user）已在保存本次证据后恢复。没有真实Git暂存/提交/发布/推送，没有烧录和硬件验收。
