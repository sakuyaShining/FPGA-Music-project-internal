from pathlib import Path
import json,datetime,hashlib
B=Path(r'D:\FPGA-Project\codex-deliverables\dual-screen-review-20261020-v2');E=B/'module-plan-current-evidence'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
now=datetime.datetime.now().astimezone().isoformat()
report=read(E/'sensor35-numeric-review-current.json')
review=dict(at=now,user_reply='Requests all35 numeric values and manufacturer capability comparison before deciding; also requests current purchase/assembly explanation.',approval=False,reference_scope_decision_pending=True,source_sha256=report['source_sha256'],numeric_report=str(E/'sensor35-numeric-review-current.md'),numeric_evidence=str(E/'sensor35-numeric-review-current.json'),purchase_assembly_review=str(E/'purchase-assembly-user-review-current.md'),summary=report['summary'],manufacturing_release=False,complete_purchase_plan=False,whole700budget_closed=False,physical_tests='UNMEASURED')
for name in ['PCB-CURRENT-CAPACITY-RECOVERY-20261024.json','PCB-ACTIVE-WORK.json','实体交付当前入口.json','模块方案-当前证据.json']:
 p=B/name;x=read(p);x['updated_at']=now;x['sensor35_user_numeric_review_current']=review;save(p,x)
p=E/'sensor-fourlayer-progress-current.json';x=read(p)
x['at']=now;x['numeric_review_current']=review
x['reference_scope_decision_origin']='User requested detailed numeric and fabrication comparison before deciding. This reply is not approval.'
x['next_actions']=['Present35 actual numeric records and manufacturer comparison; await explicit human acceptance-scope decision. Do not replay terminal CAD jobs.','Finish control/storage/interface/power complete preweld implementation and same-source manufacturing/stack files without changing old spacing limits.','Await agreed user full screen quote; close exact AUX adapter, all accessories, preweld/freight <=700 and actual Qingyuan delivery.','Product physical wrapper/firmware integration and all12 requirement physical acceptance remain pending; no RTL writes in this chat.']
save(p,x)
p=E/'sensor84-semantic-wiring-current.json';x=read(p)
for t in x['electrodes']:
 if t['kind']=='spare':t['assembly']='安装并连接实体备用电极，标SPARE；保留采样检查，不默认为新音符或八度功能'
x['assembly_scope_correction']=dict(at=now,reason='User requires84 physical electrodes; earlier text leaving4spares unmounted would reduce assembled count to80 and is withdrawn.',physical_electrodes=84,pitch=75,octave=5,physical_spare=4,calibration_positions_separate=12,RTL_changes=False)
save(p,x)
p=E/'sensor84-semantic-wiring-current.md';s=p.read_text(encoding='utf-8-sig');old='备用原始索引80—83不装触摸电极。';assert old in s
s=s.replace(old,'备用原始索引80—83同样安装并接线为4个实体备用电极，标SPARE；保留采样检查，不默认为新音符或八度功能。此前“不装触摸电极”文字会把实体数量降成80，现已撤回，完整外部电极仍为84个。')
p.write_text(s,encoding='utf-8')
p=E/'control-power-current-plan.md';s=p.read_text(encoding='utf-8-sig')
old='若成品立体声音箱输出其标称共4W，理想5V供电也至少需0.8A，还未计损耗、屏和DAC。当前缺各模块峰值/启动电流，不能声称一定过载或已经有足够余量。应比较单独受保护的音箱5V分支或自带供电音箱；这只是待落实的供电候选，不默认删保护或放宽原限流。'
assert old in s;s=s.replace(old,'本产品以3.5mm立体声AUX输出，不把内置或USB供电喇叭加入必购清单。仅核屏、音频板和原控制/传感电路的峰值、启动电流与受保护分支；当前资料还不足以证明原限流下的整机功耗余量。外部演示接收设备如需新增，须明确计入预算，不暗算成已拥有。')
s=s.replace('同时等待屏完整报价，核成品立体声发声链与受保护电源分支。','同时等待屏完整报价，核3.5mm立体声AUX链与受保护电源分支。')
p.write_text(s,encoding='utf-8')
p=B/'模块方案-当前工作单.md';s=p.read_text(encoding='utf-8-sig');s+='\n\n## 2026-10-27 用户要求先看35项数值及装配实物\n\n当前617f550e/302线51孔源未变；35项逐条实际铜距、孔距及回流配对已保存sensor35-numeric-review-current.md/json，对照嘉立创公开普通多层加工能力。用户回复是先看数值再决定，未批准改变验收口径。采购与装配实况见purchase-assembly-user-review-current.md；六块预焊传感板、完整控制/存储/保护、屏完整报价、附件/代焊含运总价≤700仍未闭合。音频保持AUX，无内置喇叭必购。纠正旧装配文字中4备用不装电极的问题，实体84电极全部保留。无RTL/CAD/订单修改。\n';p.write_text(s,encoding='utf-8')
save(E/'sensor35-user-review-register-current.json',review)
print(json.dumps(review,ensure_ascii=True))
