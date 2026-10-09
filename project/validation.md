# 整合候选验证

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
