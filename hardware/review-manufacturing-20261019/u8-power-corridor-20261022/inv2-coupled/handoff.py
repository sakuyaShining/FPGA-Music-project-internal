"""Publish the verified construction checkpoint and a byte-verified local mirror."""
from pathlib import Path
import json,csv,hashlib,shutil
O=Path(__file__).resolve().parent;B=O.parent;R=B.parent
rd=lambda p:json.loads(p.read_text(encoding='utf8'))
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=rd(O/'checkpoint-review.json');cap=rd(O/'checkpoint-capture.json');assert a['native_drc']['connection']==57
assert sha(Path(a['project'])/'pcb/PCB1.epcb2')==a['pcb_sha256']
with (B/'probe-map-current-UNMEASURED.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
remaining={r['net'] for r in csv.DictReader((O/'remaining-networks.csv').open(encoding='utf-8-sig'))}
for r in rows:
 p=next(p for p in cap['pads'] if p['id']==r['native_pad_id'])
 assert p['net']==r['net'] and abs(p['x']*.0254-float(r['x_mm']))<1e-6 and abs(p['y']*.0254-float(r['y_mm']))<1e-6
 r['native_net_status']='native_open_UNMEASURED' if r['net'] in remaining else 'native_connected_UNMEASURED'
with (O/'probe-map-current-UNMEASURED.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
write(O/'probe-map-audit.json',dict(source_pcb_sha256=a['pcb_sha256'],native_drc=a['native_drc'],testpoints=len(rows),pad_mapping_and_locations_verified=True,physical_tests_executed=False,map_sha256=sha(O/'probe-map-current-UNMEASURED.csv')))
text=f'''# INV2 原生连通修复 · 已保存重开验证，未投板放行

当前施工工程：`{a['project']}`。PCB SHA256 `{a['pcb_sha256']}`。
相对上一已验证 59 项检查点，INV2（U7.6 → R13.1）完整闭合。严格原生 DRC 保存重开后为 **0 间距 / 0 物理 / 57 未连通，12 网**。未完成网络见 remaining-networks.csv；35 项仍属于 ADDR0–3/MUX_DISABLE，BUS_MOSI 仍未闭合。

为释放 U7 出口，局部抬升 3V3_PERIPH 顶层主干并保持 15.74 mil 宽；局部迁移 VIS_DC 换层孔并恢复原铜。VIS_DC 原有两焊盘岛仍为两岛，未冒称已闭合。INV2 使用 8 mil 线路、两个 24/12 mil 过孔，另增一个同规格 GND 缝合孔。R13 是 INV2 至 SENSE_2 的 220 Ω 串联电阻；本批未移动它，原 SENSE_2 铜保留。引脚角色此前依据 TI SN74LVC14A 数据表表 5-1 核对：https://www.ti.com/lit/ds/symlink/sn74lvc14a.pdf 。

## 核验结果

- 原生实际铜与声明变更逐网逐层几何对账，最大偏差 {a['declared_actual_copper_max_deviation_mm']:.9f} mm；558 孔逐个核对尺寸与位置，230 器件、1079 焊盘保持。
- 新 GND 孔在重建并重开后的实际地铜 15/2 均有有效铜环接触；INV2 顶层参考 15、内层 16 参考底层 2，排除各自换层孔周围 1 mm 后，线路中心线投影连续覆盖。排除范围、数值和铜环面积见 checkpoint-review.json。
- 原传感/音频及其他未受影响网络铜保持；115 个底层敏感/音频网络在同一排除掩模下比较实际内层16地铜投影，无覆盖退化。原有缺口不因本项比较而关闭。
- 两处 INV2 信号孔距合格参考地孔约 2.212 / 1.900 mm，未满足项目 1.5 mm 偏好，保留开放。几何覆盖与距离检查均不是 SI/EMC 或实物功能认证。
- 原63项施工源与稳定R15源文件哈希核对不变。本工程非PCB设计文件不变；描述文件仅更新PCB保存时间/版本元数据。

## 可恢复交付与下一入口

native-inv2-repair-WORK-IN-PROGRESS.zip 是同一施工工程完整原生包，ZIP CRC 和包内 PCB SHA 均验证。checkpoint-review.json、checkpoint-capture.json、checkpoint-drc.json 是同一57项源；probe-map-current-UNMEASURED.csv 复核21个测点但没有实物测量。

唯一当前施工入口为上级上级 REGIONAL-WORK-IN-PROGRESS.json。旧 8b9b68a5 源上的27个地址候选及旧DSN/SES不得直接导入，需对新57项源重检。固定布局地址出口、单邻线ripup和两根传感底层线局部重路由均未恢复全部所需网络；下一方法必须联合移动受影响布局/整束铜与去耦，或重新分配可恢复的出线通道，不重复相同局部搜索。

稳定 ACTIVE-ROUTING-CANDIDATE.json 仍为R15，本施工版没有制造放行。尚需闭合全部剩余网络、整板电气/参考地与DFM复核、屏幕/机械/装配同版资料核实和最终制造导出；上电、满载、屏幕/触摸、84路传感和音频均未实物验证。最终固件容量与集成由另一聊天独立推进，本批未修改RTL。
'''
(O/'README.md').write_text(text,encoding='utf8')
p=rd(R/'REGIONAL-WORK-IN-PROGRESS.json');p.pop('pending_trial',None)
p.update(updated_at=a['updated_at'],session=a['session'],pcb_sha256=a['pcb_sha256'],source_capture=str(O/'checkpoint-capture.json'),drc=str(O/'checkpoint-drc.json'),review=str(O/'checkpoint-review.json'),readme=str(O/'README.md'),native_drc=a['native_drc'],status='saved_reopened_copper_and_actual_reference_verified_construction_not_released',router_status='All owned routing jobs terminal. INV2 coupled power/VIS_DC repair verified in native saved/reopened project; no old address candidates imported.',next_action='Joint address/MUX pin escape plus affected local layout/copper recovery on this57-item source. Old8b9 source address candidates require full revalidation; do not repeat fixed-layout MOSI/R64 or failed one/two-sensor ripups. Preserve actual sensing/audio reference and power/ground.')
p['closed_nets_this_recovery']=list(dict.fromkeys(p['closed_nets_this_recovery']+['INV2']))
p['stale_offline_candidates']=dict(source_pcb_sha256=a['source_pcb_sha256'],entry=str(B/'address-next-checkpoint.json'),native_replay_forbidden=True)
write(R/'REGIONAL-WORK-IN-PROGRESS.json',p)
notice=f"{a['updated_at']} 更新：INV2完整闭合，联合恢复局部3V3_PERIPH/VIS_DC并新增1个真实地缝合孔；保存重开严格DRC为0/0/57（12网）。实际铜/声明变更对账、115个敏感/音频网参考地无退化、原63及R15哈希核对通过。可恢复原生包及逐项证据见u8-power-corridor-20261022/inv2-coupled/README.md。唯一当前入口REGIONAL-WORK-IN-PROGRESS.json；8b9旧地址候选不可重放。制造未放行、实物未测。\n\n"
for path in [R/'AUTONOMOUS-CURRENT.md',Path('C:/Users/Sakuya/.codex/worktrees/4a4b/FPGA-Music-project/notes/2026-10-22-PCB-skill沿用说明.md')]:
 old=path.read_text(encoding='utf8')
 if not old.startswith(notice):path.write_text(notice+old,encoding='utf8')
with (R/'release-open-items.csv').open(encoding='utf-8-sig',newline='') as f:items=list(csv.DictReader(f))
for r in items:
 if r['id']=='H05':
  r['remaining']='Stable R15 remains0/0/58 across11nets. Current U8BusWork saved/reopened0/0/57 across12nets. INV2 fully closed; BUS_SCK and INPUT_LOAD_N retained. Address/disable35 objects and BUS_MOSI remain open; other controls in remaining-networks.csv. SI/PI/sensor/mechanical/manufacturing/physical verification remain open.'
  r['closure_evidence']='u8-power-corridor-20261022/inv2-coupled/checkpoint-review.json and README.md; source6509803e; actual ground/copper reconciliation; no manufacturing release or physical test.'
with (R/'release-open-items.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(items[0]));w.writeheader();w.writerows(items)
dest=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2/u8-power-corridor-20261022/inv2-coupled');dest.mkdir(parents=True,exist_ok=True)
files=['README.md','checkpoint-review.json','checkpoint-capture.json','checkpoint-drc.json','native-inv2-repair-WORK-IN-PROGRESS.zip','remaining-networks.csv','probe-map-current-UNMEASURED.csv','probe-map-audit.json','native-state.json','native-before.json','native-apply.json','validated-copper-plan.json','full-preflight.json']
for name in files:shutil.copy2(O/name,dest/name);assert sha(O/name)==sha(dest/name)
write(O/'mirror-verified.json',dict(destination=str(dest),files={name:sha(dest/name) for name in files}))
print('PROMOTED_CONSTRUCTION_57_AND_MIRRORED',str(dest),flush=True)
