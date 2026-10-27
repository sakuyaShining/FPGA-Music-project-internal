from pathlib import Path
import json,hashlib,datetime
B=Path(r'D:\FPGA-Project\codex-deliverables\dual-screen-review-20261020-v2');E=B/'module-plan-current-evidence'
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
now=datetime.datetime.now().astimezone().isoformat()
plan=read(E/'sensor-electrode-channel-plan-current.json');probe=read(E/'sensor-electrode-bounded-route-current.json')
native=read(E/'control-power-current-plan.json')['native_file_checks']
assert all(hashlib.sha256(Path(r['file']).read_bytes()).hexdigest()==r['actual'] for r in native)
stage=dict(at=now,state='OFFLINE_ESD14_BRIDGES_PASS_AND84_MAPPING_PROPOSAL_FULL_ROUTING_NOT_PROVED',
 plan=str(E/'sensor-electrode-channel-plan-current.md'),evidence=str(E/'sensor-electrode-channel-plan-current.json'),bounded_probe=str(E/'sensor-electrode-bounded-route-current.json'),
 NC_external_bridges=14,candidate_PAD_changes=22,logical84_bijection_pass=True,left8_cross_order_pairs_before=28,left8_cross_order_pairs_after=0,
 full_group_route_pass=False,terminal_stop='E03 J1.4-to-D1.5 per-branch160000 expansion cap; prefix3 physical-pass branches only; no global impossibility claim',
 native_applied=False,native40_unchanged=True,source_PCB2_sha256=plan['source_sha256'],native_remaining_nets=21,native_connection_items=56,
 native_live_identity_rechecked_this_stage=False,whole700budget_closed=False,physical_tests='UNMEASURED',complete_purchase_plan=False)
next_action='Read electrode channel plan and terminal bounded probe. Analyze E03 J1.4-D1.5 channel and prefix occupancy jointly for all14; no native22PAD changes until complete planned route proof. Do not rerun terminal probe. Continue remaining control/power preweld sourcing, full price/delivery, screen user quote and firmware interface contract.'
for n in ['PCB-CURRENT-CAPACITY-RECOVERY-20261024.json','PCB-ACTIVE-WORK.json','实体交付当前入口.json','模块方案-当前证据.json']:
 p=B/n;d=read(p);d['updated_at']=now;d['electrode_current_stage']=stage
 if n!='模块方案-当前证据.json':
  d['next_action']=next_action
  d['latest_followup']=str(B/'模块方案-当前证据.json')
  d['read_first']=list(dict.fromkeys([stage['plan'],stage['evidence'],stage['bounded_probe']]+d.get('read_first',[])))
 else:
  d['complete_purchase_and_assembly_plan']=False
  for f in ['sensor-electrode-channel-plan-current.json','sensor-electrode-channel-plan-current.md','sensor-electrode-bounded-route-current.json','TI-TPD4E02B04-SLVSD85B.pdf']:
   d.setdefault('evidence_sha256',{})[f]=hashlib.sha256((E/f).read_bytes()).hexdigest()
 write(p,d)
text='''\n## 当前电极整组通道候选（10月27日）\n\n离线核出14个ESD封装NC直通出口的真实外部短桥，按原厂NC说明、当前150PAD/91段铜/36孔及实际Bottom地铜核物理距离和全线宽参考通过。候选另将R3—R10输入侧反序并补偿外部接线，84个逻辑索引/实体位置一一对应，左8路交叉顺序从28降到0；总22个PAD候选赋网，需要原理图/PCB/线束同步。**没有实施原生改网，不能把该候选表当当前接线表。**\n\n一次离线有界全组探查在前三条J1—ESD支路物理通过后，于E03/J1.4—D1.5达到160000节点上限停止；14网完整可布通尚未证明。失败不是全局无解证明；不重跑终态作业，不以局部短桥通过替代整板。下一步先分析该通道和先前路径占用，再作明确整组扇出/布局改变。源PCB2仍83b238df、21网56项未连接，原951/14页及当前小板40项原生文件哈希未变。详见module-plan-current-evidence/sensor-electrode-channel-plan-current.md与sensor-electrode-bounded-route-current.json。完整采购与预焊/总价/交期仍未闭合，UNMEASURED。\n'''
p=B/'模块方案-当前工作单.md';t=p.read_text(encoding='utf-8');marker='\n## 当前电极整组通道候选';p.write_text(t.split(marker)[0]+text,encoding='utf-8')
files=['sensor-electrode-channel-plan-current.py','sensor-electrode-channel-plan-current.json','sensor-electrode-channel-plan-current.md','sensor-electrode-bounded-route-current.py','sensor-electrode-bounded-route-current.json','sensor-electrode-checkpoint-current.py','TI-TPD4E02B04-SLVSD85B.pdf','TPD4E02B04-pin-table-page3-current.png','TPD4E02B04-layout-current.png']
write(E/'sensor-electrode-stage-file-map-current.json',dict(at=now,evidence_files=files,state=stage['state'],native_file_checks=native,original227functions_retained=True,not_for_fabrication=True))
print(json.dumps(stage,ensure_ascii=False))
