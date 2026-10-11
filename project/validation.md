# 整合候选验证

2026-10-10：下表是保留的20261009-06已验底座，已在本日重跑55/55、退出0。
新增完整32组板测入口20261010-01全量回归56/56通过、退出0，T60与2项INFO单列；PnR通过，setup+10.527ns、hold+0.211ns、TNS0。
01已SRAM下载，COM6确认D3/revision2/proto11/scope32；板测run01为9/15通过、6/15失败，退出1，不能签收。
失败包括MIDI127与FREE冲突、样本短读及部分音色/频谱判据；证据保留在`evidence/full32-20261010/hardware-run01/`。
当前源码20261010-02是向前修复，完整流/MIDI127专项通过退出0，全回归56/56于04:24:37完成退出0；T60 KNOWN-FAIL与2 INFO单列，证据`evidence/full32-fix02-20261010/`。02新PnR已启动，尚未下载；不沿用01证据签收02。
02 PnR第一轮place2/route2失败退出1（PR0004，一条网络未布通）；失败证据保留`evidence/full32-fix02-20261010/pnr-attempt01/`。尚无02码流可下载，改用place1/route2继续验证同一完整32组源码。
02第二轮place1/route2也因PR0004退出1，保留`pnr-attempt02/`；第三轮place2/route1正在运行。02没有被下载。
第三轮place2/route1也失败，PR0004有189条未布通网络，证据`pnr-attempt03/`保留；第四轮place0/route2正在运行。02未下载，时序/板级尚未验。
第四轮place0/route2成功退出0，setup+11.111ns、hold+0.214ns、TNS0、违例端点0，PR1014保留；30端口明确约束，完整32组。绑定`board-build-20261010-02.json`且下载前check-build通过，02已SRAM下载，hardware-run02运行中。
02 hardware-run02退出1，12/15通过、3失败；MIDI127/静音/力度已板验，短流与两指组号失败保留。追加RAM索引读/流对比及独立两指诊断，不能套用诊断结果抹掉原失败。
隔离RAM索引读证实两指独立反向频谱（预期峰比1.0/0.99889），只覆盖干净输入场景；stream20次中6次在前13字节删除/替换，Win32错误标志0，传输仍未闭环。正进行读取时机对照，不将根因提前归到RTL或驱动。
进一步随机60流无等待对照：请求前设置timeout30/30精确，请求后26/30精确，结合pyserial重新SetCommState定位主机流中重配置竞争。当前04修复配置顺序及每例finally清理，3项主机判据通过，加入原41号，不缩减56门禁。03新增门禁日志目录变量错误被主动发现并中止，保留快照，无通过证据；04全回归运行中，板上仍02，04新构建/板验待完成。
04完整回归56/56于05:57:41完成退出0，41号同时包含完整UART/32组/MIDI127和3项主机判据；T60与2INFO单列。证据`evidence/full32-hostfix04-20261010/record.json`绑定226输入。新PnR运行中，板上仍02，04板级待验。
04新PnR退出0，setup+11.111ns/hold+.214ns/TNS0，30端口约束、PR1014保留。构建绑定`board-build-20261010-04.json`，check-build后已SRAM下载04，hardware-run04运行中；本版板验尚待完整报告。
04 hardware-run04完成15/15退出0，原样本流/音色/两指失败在修复后通过，输入/数字样本/原始流报告保留；两指反向实测273.585/376.582Hz、移动不触发note-on。追加实际主机capture对RAM索引读及100次逐字节稳定性正在运行，旧失败不覆盖。该板级证据仅内部数字路径，不确认真实DAC/触控或未实现设计。
04追加稳定性完成退出0：实际2048样本capture与索引RAM一致，100/100完整流逐字节一致，无重试/额外读等待。最终绑定记录`evidence/full32-hostfix04-20261010/delivery.json`；本轮受控数字板测闭环完成。原01/02失败及03中止保留，真实DAC/触控/10ms和未实现设计不升级。本轮自动跟进停用，源码与来源工作树继续保留。
实时状态见[state.json](state.json)，配置见[board-test-20261010.md](board-test-20261010.md)。

当前源码身份由state指向的不可变清单确定。Git提交可继续增加文档，但源码/表/GUI/约束/工具有任何变化都会导致身份检查失败。

| 验证对象 | 本轮结果 | 能确认的范围 |
|---|---|---|
| GUI/配置/串口故障单元与真实Qt控件 | 30项通过 | 配置草稿保存恢复、非法文件隔离、串口短写/回读地址等；不代表完整配置已应用设备 |
| GUI帧一致性与主机地址对账 | 通过 | 主机与GUI生成相同命令，协议版本默认表为0x11 |
| 组合协议判据 | 通过 | 草稿不发布、整谱发布、刷新原力度、曲谱指针复位、停曲off、活动音复位 |
| 最新源事件判据 | padfast/event_sources/evhold_stream通过 | 保留各源4槽、轮转与溢出读回，不恢复旧单槽 |
| 逐指音高 | 单元与顶层通过 | 组0/31、绑定、位置连续、释放/重用、16泛音一致；真实多指输入未验 |
| I²C | basic/contract通过 | 模型下读写、顺序、NACK、拉伸、超时、复位；产品顶层未接器件 |
| 版本检查自身 | 7项通过 | 空清单、漏约束、数据/GUI漂移、新增源码、码流替换、旧输出绑定新快照被拒绝 |
| 全量回归 | 55/55通过；1项已知失败、2项信息审计不计入通过数 | 原始结果已归档为[evidence/integration-06-regress_result.txt](evidence/integration-06-regress_result.txt)；KNOWN-FAIL为T60，INFO为gatecov/deadparam审计 |
| 产品PnR | 已完成快照后的新构建，身份核对通过 | 最终本版报告setup +12.037ns、hold最差+0.208ns、setup/hold TNS=0、违例端点0；PR1014时钟布线告警保留 |
| 产品板级 | 未执行 | 本聊天未下载候选，不把另一个聊天的diagnostic_v4结果套到产品 |

Logic 15179/20736（74%），CLS 8968/10368（87%），BSRAM 31/46。
产品构建为tdm_ship、GW2AR-LV18QN88C8/I7、27MHz、fs=52734.375Hz、FINGER_EXPR默认0、SSPI GPIO、place/route=2。
逐指启用的数字仿真通过不代表默认包装已连接真实触控；另一个诊断版仅启用两组的限制没有引入产品。

T60已知失败、旧LFO跳变、异步复位同步释放、真实触摸/音频/I²S电气/最坏10ms持续挂账。
必须读具体行为，不能把KNOWN-FAIL、INFO或审计PASS当作全部需求实现。

本次按用户选择只保留整合分支，未接入或打断主目录板测。原main仍是来源工作区，候选验证完成后再接收板测的新成果。

最终码流记录：[product-build-20261009-06.json](versions/product-build-20261009-06.json)。原始源码对应证据与码流保存在[evidence/integration-06-evidence.zip](evidence/integration-06-evidence.zip)。

## 2026-10-10用户现场接续检查

用户确认连接Nano20K且持续未断电，COM5/COM6枚举。本轮核对04源/构建PASS，另一板测空闲，COM6独占读回D3/proto11/rev2/scope32；未下载、未复位、未写Flash。标签不能独立区分02/04，04归属结合原下载记录与用户连续供电陈述，不宣称从FPGA读出了完整码流SHA。

证据[session-check02/report.json](evidence/bench/20261010-session-check02/report.json)：5/5通过、退出0。覆盖清理后的2048样本静音、五档音符开关/MIDI127独立、完整32组分配/抢占/释放、A4内部数字频谱与单指移动、两指反向变调且不新增note-on。所有capture保留6145字节原始流和样本，结束活动音符0、串口关闭、所改控制参数恢复。不是上电默认/实体触控/DAC/I²S电气/10ms验收。

首轮[session-check01/report.json](evidence/bench/20261010-session-check01/report.json)退出1，4/5通过；生命周期项因探测脚本使用本机Python不支持的int.bit_count未执行完，不是已定位RTL故障。改用同义bin.count写法后以新目录完整复跑，原失败/脚本/流均保留，未降低判据。

2026-10-11重新上电恢复实测：完整04源隔离副本check-build通过，当前GUI03源228检查通过；原04码流SRAM重载exit0，COM6身份D3/rev2/proto11/scope32。A4产生2048非零样本、释放后active0；用户实际GUI采样并显示波形成功，显示倍率4，测试音已释放，保留最近快照。证据[evidence/reload-test-20261011/record.json](evidence/reload-test-20261011/record.json)。本轮未改产品源码；短音漏过周期采样/实体DAC仍未闭环。

2026-10-11 desktop live06: host45 PASS; FIR exact1024 output/alias rejection gate PASS; PnR setup12.644ns hold.228ns TNS0; identity-bound SRAM programmed. GUI/UART30s PASS768audioframes/10events/zero CRC,gaps,losses/active0. Evidence project/evidence/desktop-live-filtered-20261011. Full57 regression still running;05 full57 historical only. Standalone FPGA visualization and physical DAC not accepted.
# 2026-10-11松键幅度连续性修复07

当前241输入07已向前接合，512槽专项与新PnR通过（setup7.378ns/hold.198ns/TNS0、完整32组）；SRAM下载exit0，UserCode3A93/Status6020。30秒真实GUI769音频帧/10事件通过，CRC/缺帧/断点/观察损失0、active0；力度1/4/8/12、刷新、复音释放六例真实PCM峰值/RMS均未升高。

回归边界：attempt01磁盘不足中断保留；D盘同241输入attempt02原57/58、exit1，31身份检查因漏环境state.json失败。补齐非产品环境元数据后31补验exit0，原另57PASS，因此58项判据均覆盖；不覆盖原报告、不声称原完整进程exit0。T60 KNOWN-FAIL/2INFO单列。完整索引为project/evidence/release-fix07-20261011/delivery07.json，原始流及源/码流ZIP保存D盘。实体DAC、触控、独立FPGA三视图与视觉延迟仍未验。

