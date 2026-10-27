from pathlib import Path
import json,datetime,hashlib,sys
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
from shapely.geometry import Point,LineString,box
from shapely.affinity import rotate
from shapely import union_all
B=Path(r'D:\FPGA-Project\codex-deliverables\dual-screen-review-20261020-v2');E=B/'module-plan-current-evidence'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
r=read(E/'sensor-header-fanout-current.json');plan=read(E/'sensor-electrode-channel-plan-current.json')
assert r['all14_header_fanouts_physical_pass'] and r['all_left8_ESD_to_series_physical_pass'] and r['moved14vias_physical_pass'] and not r['violations']
pads=read(E/'sensor-front-exact-source-pads-14nets-current.json')['pads'];by={(p['ref'],p['pin']):p for p in pads}
for ch in plan['proposed_pad_net_changes']:by[(ch['ref'],ch['pin'])]['net']=ch['proposed']
def shape(p):
 s=p['shape'];w=s['width']*.0254;h=s['height']*.0254
 return Point(p['x_mm'],p['y_mm']).buffer(w/2,quad_segs=256) if s['padType']=='ELLIPSE' and abs(w-h)<1e-6 else rotate(box(p['x_mm']-w/2,p['y_mm']-h/2,p['x_mm']+w/2,p['y_mm']+h/2),p['angle'],origin=(p['x_mm'],p['y_mm']))
islands={}
for i in range(14):
 net=f'L0_E{i:02}'
 g=union_all([shape(p) for p in pads if p['net']==net]+[LineString(c['points']).buffer(c['width_mm']/2,quad_segs=256) for c in r['checks'] if c['net']==net])
 islands[net]=len(g.geoms) if hasattr(g,'geoms') else 1
assert all(islands[f'L0_E{i:02}']==1 for i in range(8))
assert all(islands[f'L0_E{i:02}']==2 for i in range(8,14))
r['candidate_E00_to_E07_all_pad_islands']=islands;r['candidate_left8_four_pad_connectivity_pass']=True
r['candidate_geometry_terminal']=True
write(E/'sensor-header-fanout-current.json',r)
now=datetime.datetime.now().astimezone().isoformat()
stage=dict(at=now,state='OFFLINE14_HEADER_FANOUT_AND8_COMPLETE_ELECTRODE_PATHS_PASS_REALGROUND_PENDING',
 plan=str(E/'sensor-header-fanout-current.md'),evidence=str(E/'sensor-header-fanout-current.json'),preview=str(E/'sensor-left8-whole-candidate-current.png'),
 header_fanout_paths=14,NC_bridges=14,complete_electrode_net_paths=8,remaining_electrode_net_paths=6,new_candidate_segments=68,
 proposed_PAD_net_changes=22,proposed_Ground_via_moves=14,max_TH_return_distance_mm=r['max_signal_TH_return_distance_mm'],
 native_applied=False,native40_unchanged=True,source_PCB2_sha256=r['source_sha256'],native_remaining_nets=21,native_connection_items=56,
 provisional_Ground_not_accepted=True,whole700budget_closed=False,complete_purchase_plan=False,physical_tests='UNMEASURED')
md='''# 传感前端：14路排针扇出与左8路完整路径离线候选

本轮没有原生PCB/原理图/RTL改动。源仍83b238df，原生仍21网56项未连。原951和14页、当前小板40项文件哈希保持。图中彩线仅为候选，不是当前接受铜。

## 已核过的具体改变

- 原14个排针信号回流地孔在排针右侧x约6.4513mm，占据J1到ESD的扇出区。候选把这14孔镜像到排针左侧x约3.5487mm；各孔y/孔径/钻孔不变，21个既有信号通孔回流约束未放宽，本次14孔对应距离最大1.45125964mm，均小于1.5mm。另22孔、91段原铜及全部器件位置保持。
- 不重跑终态网格搜索。改用明确整组几何：14路J1—ESD直达/折线路径；14段封装内外部NC直通短桥；左8路ESD—串阻在x17.5mm转为水平入焊盘。共68段候选铜、0新增信号孔，按150PAD、91原线、36候选孔以及全部候选线相互核实际间距，全部通过。
- 直接大斜率入串阻曾碰邻接R10/R9/R8焊盘（原实际距0.039761/0.053019/0.035239mm，要求0.1651mm），已明确改为x17.5水平入端；拒绝结果保存在JSON内，没有放宽规则。最终左8路额外净距最小0.00985183mm，仍需原生实际读回复核。
- 继承上轮22PAD候选改网及84路外接补偿表，仍未实施。对所有电极焊盘与候选真实铜做并集连通：E00—E07各1岛（排针/ESD IO/NC/串阻全部相连），E08—E13仍各2岛，尚缺ESD至右侧串阻部分。校准CH14/15、六路独立SENSE_OUT和单J10目标不变。

## 尚未通过的地参考与接受门

移孔后的Ground只有假设模型：用旧实际Bottom多边形填旧14个地钻孔、切新14孔，模型仍一组件；它不是原生真实重铺结果。左8条ESD—串阻在此模型全线宽缺失0，但排针扇出在通孔终端区域外仍有最大约0.000492292mm²未覆盖，因此**不把整组参考判为通过，也不扩大终端例外或阈值**。这个差异和TH过渡/原源Cu/接触/DC/细颈/机械均需在完整候选真实重铺后核验。

## 接续工作

1. 先完成右6路ESD至串阻的共同通道规划，保留这批明确扇出与左8路作为候选输入；不能把原生仍开放的8网报为已接受闭合。
2. 同时保留7个控制/采样网的通道，不能只求14电极而封死其余网络。不得重放旧grid/Top35/native apply或整段复建工程。
3. 完整候选成立后，先实时核同一工程/PCB/网关/PID、SHA/对象/规则/恢复点、软件自动保存和资源；再在同一自有工程可回滚试验，显式同步22PAD、14地孔和线束标签。
4. 实际重铺、全部源铜参考/回流/旧接触/DC及严格原生DRC、保存关闭重开全部通过后才可接受。之后才可提交同版制造与工厂预焊报价。

当前预焊报价/清远交期、控制保护、屏完整价、完整700元总价及整机固件接口仍未闭合。实物UNMEASURED。没有下单、付款、外发消息或删除功能。
'''
(E/'sensor-header-fanout-current.md').write_text(md,encoding='utf-8')
next_action='Read explicit fanout candidate:14header+14NC+left8 complete paths physical pass,14Ground returns mirrored LEFT only offline. Right6 ESD-toR plus7controls still need joint plan. Candidate Ground reference not accepted (THoutside residual0.000492292mm2); no threshold/exception changes. Do not rerun terminal grid/native apply. No native22PAD/14via write before full candidate/preflight. Continue preweld sourcing/quote/whole700budget and pending screen quote.'
for n in ['PCB-CURRENT-CAPACITY-RECOVERY-20261024.json','PCB-ACTIVE-WORK.json','实体交付当前入口.json','模块方案-当前证据.json']:
 p=B/n;d=read(p);d['updated_at']=now;d['electrode_current_stage']=stage
 if n!='模块方案-当前证据.json':
  d['next_action']=next_action;d['latest_followup']=str(B/'模块方案-当前证据.json');d['read_first']=list(dict.fromkeys([stage['plan'],stage['evidence']]+d.get('read_first',[])))
 else:d['complete_purchase_and_assembly_plan']=False
 write(p,d)
p=B/'模块方案-当前工作单.md';t=p.read_text(encoding='utf-8');marker='\n## 当前扇出明确几何候选'
p.write_text(t.split(marker)[0]+marker+'（10月27日）\n\n14个J1回流孔离线镜像到左侧后，14路排针—ESD扇出、14个外部NC短桥和左8路ESD—串阻完整路径共同物理检查通过，共68段候选线；未新增信号孔，所有器件及91段原铜保持。左8路所有4端焊盘并集各1岛，右6路仍2岛；原生未改仍21网56项。84映射/22PAD仅候选，14移孔回流距离最大1.45126mm未放宽。假设Ground模型仍有TH终端外约0.000492292mm²参考缺失，未判通过、未扩例外。右6路/7控制网、真实重铺完整验收和预焊含运报价/700元总价仍未闭合。详见module-plan-current-evidence/sensor-header-fanout-current.md及JSON/预览图。原终态搜索不重跑。\n',encoding='utf-8')
files=['sensor-header-fanout-current.py','sensor-header-fanout-current.json','sensor-header-fanout-current.md','sensor-header-fanout-current.png','sensor-left8-whole-candidate-current.png','sensor-fanout-checkpoint-current.py']
write(E/'sensor-fanout-stage-file-map-current.json',dict(at=now,evidence_files=files,native_file_checks=read(E/'control-power-current-plan.json')['native_file_checks'],stage=stage))
print(json.dumps(stage,ensure_ascii=False))
