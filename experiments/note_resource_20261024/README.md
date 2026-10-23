# 共享音符资源管理候选

本目录由4d37会话按协作板限定范围维护。输入合同为D-019和project/NOTE-RESOURCE-CONTRACT.md；不修改D盘原FPGA、06df或三个current目录。

`rtl/note_resource_mgr.v`是已完成限定单元验证的32组/32实例/1–4层协调器候选，不是音乐顶层或可下载码流。它串行接纳请求，以显式起音顺序队列选择已释放尾音，再选择最早按住实例；不用8位标签比较年龄。32位token的bit31=0现场、1曲谱，低31位是各来源独立起音序号。每个来源须按序交回事件、单次前进小于半个序号空间，且旧事件仍可能到达时不能重用完整token；序号可跨零回绕，不用它决定资源优先级。已结束/已取消的旧ON重放会被来源序号门拒绝，仍有效实例的重复ON只回同一实例，不再起音。

## 请求与结果

- req_kind：0起音、1松键、2自然结束。req_layers为四槽位图；自然结束req_groups必须属于该token的当前组。非法/重复/迟到请求不新建或误释放别人的资源。
- rsp_code：0已发布、1已松键、2已自然结束、3迟到/失效、4非法、5重复起音、6已取消。结果保持到rsp_ready；入口在响应结束前背压，不吞事件。
- cancel_valid/token只取消尚未完成响应的起音。取消已被接纳后不复活已经退场的旧实例；准备完成前后都清退已预留/装载资源，取消发布中的音符须先完成退场确认。
- active_groups是已发布实例占用，reserved_groups是尚未发布预留；两者不得重叠。OFF不释放资源，真正结束由FINISH反馈。

## 后端两阶段接口

work_kind：0 RELEASE（写OFF但保留尾音占组）、1 RETIRE（强制整实例退场并清退在途操作）、2 PREPARE（装载所有层但尚不可听）、3 PUBLISH（所有层在统一音频边界可见）。work_layers和work_map的四个5位组号建立层映射；仅有效层可用。

后端先以work_valid/ready接收整条事务，再回done_valid/ticket/token表示实际完成。每次只有一条工作在途；错误ticket/token不能推进事务，protocol_error留痕。ticket可回绕，但不充当全局年龄，且不能接受无限期重放旧完成事件；后端需遵守一事务一次完成的合同。

本模块不擅自拿“请求已接收”代替“已退场/已装载/已发布”。目前真实音乐引擎尚缺上述后端与包络结束反馈的接合，因此即使单元通过也只证明协调器范围。全局复位必须与后端共同复位，不能单独清管理器后遗留发声组。

## 下一步

独立Python参考与RTL在2045条请求上逐事务/响应/完整实例状态对照一致；含1/2/3/4层、满32组、尾音优先、多实例回收、6类取消、源序号跨零、3位工作ticket多次回绕、重复/迟到请求，以及READY/DONE/响应背压。反转尾音优先、只退场一层、忽略完成token三项变异均被检出。新增背压监测首轮曾误把已完成握手的响应失效当错误，失败保留，修正监测边界后在新目录全量重跑，不改产品规则。

独立Gowin综合已通过：优化前REG2466/LUT6359/ALU209/BSRAM2/SSRAM44；共享元数据读口后REG1590/LUT3035/ALU213/BSRAM0/SSRAM42。两版均有独立仿真与输入身份；不能把这个独立块的数量直接相加当成完整音乐顶层预算，没有新PnR或有效STA。

```powershell
python -m unittest discover -s experiments/note_resource_20261024/tests -v
python experiments/note_resource_20261024/verify.py --fault-checks --output <不存在的新目录>
python experiments/note_resource_20261024/synthesize.py --output <另一个不存在的新目录>
```

当前只证明协调器与模拟后端协议。真实PREPARE/PUBLISH、包络真正结束、指触边沿/滑音路由和曲谱事件合并尚待适配：NR01–NR06仅有此范围的证据，NR04的实际手指不自发重触发尚未板验；NR07、完整资源/时序、抢占瞬变、实体延迟与最终码流均未签收。禁止下载、Flash或制造放行。版本、源SHA和本轮证据由project/versions/note-resource-candidate-20261024.json及governance当前review定位。
