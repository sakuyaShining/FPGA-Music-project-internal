# 事件通路验收证据

RTL 实现 3520270，事件测试 494e278，检查器修正 f24aa0a。

- 一次全量：50/51，exit=1；唯一新增失败是环境相关的 24 leakcheck 自检。
- 该检查器修正后专项 PASS，exit=0；RTL、数据表和事件激励未变，未重复长仿真。
- 组合验收：51 项硬判据均有通过证据，2 项已知失败（I²C v2、混响 C0），2 项 INFO。
- 当前出货顶层 PnR：setup +10.218 ns、hold +0.313 ns，TNS 0/0；仍保留 clk_d 布线告警。

raw-evidence.zip 保存原始全量结果、专项日志、原版 FIFO 失败对照、PnR 资源/时序报告及原 Tcl。
EVIDENCE_SHA256.json 校验 ZIP 内原始文件的字节内容；不为消除行尾检查告警而改写日志。
三份 JSON 在目录中另留可读副本。原始工作日志仍在 sim_build/event_repair/。
