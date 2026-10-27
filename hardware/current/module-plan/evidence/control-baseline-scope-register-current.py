from pathlib import Path
import json,hashlib,datetime,re,html
B=Path(r'D:\FPGA-Project\codex-deliverables\dual-screen-review-20261020-v2');E=B/'module-plan-current-evidence'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
now=datetime.datetime.now().astimezone().isoformat();control=read(E/'control-power-current-plan.json');rows={r['reference']:r for r in control['original56_allocation']}
spec=Path(r'D:\FPGA-Project\maintenance-20261026\repo\project\PRODUCT-SPEC.md')
native_checks=[]
for r in control['native_file_checks']:
 p=Path(r['file'])
 if 'U9ControlWork' in str(p) and p.name in ['02_Shift_and_memory.esch2','06_Controls.esch2']:
  assert sha(p)==r['actual'];native_checks.append(dict(file=str(p),sha256=sha(p),unchanged=True))
assert len(native_checks)==2
proof=dict(at=now,status='CORRECTION_OF_UNAUTHORIZED_EXTRA_CONTROL_PURCHASE_NOT_PRODUCT_ACCEPTANCE',withdrawn='13buttons,8additionalphysicalharmonicbuttons,andsecond165',actual_schematic_baseline=dict(preset_buttons=4,EDIT_buttons=1,encoder_with_push=1,LV165=1,LV595=1,harmonic_zones_on_J10_touchscreen=8),U9_pin_nets=rows['U9']['original_pin_nets'],U8_pin_nets=rows['U8']['original_pin_nets'],spec_file=str(spec),spec_sha256=sha(spec),original_schematic_checks=native_checks,independent_edit_operations_contract='STILL_PENDING; no automatic press reuse/key removal/newGPIO',readable_report=str(E/'control-baseline-scope-review-current.md'),no_CAD_RTL_changes=True,whole_purchase_ready=False,whole700budget_closed=False,reference_scope_approval=False)
save(E/'control-baseline-scope-review-current.json',proof)
s=(E/'harness-56dz2839-current.html').read_text(encoding='utf-8');v=json.loads(html.unescape(re.search(r'data-icheck-info="([^"]+)"',s).group(1)))['data']
wire=dict(at=now,status='EXACT_SELLER_VARIANTS_FOUND_NOT_FINAL_HARNESS_ACCEPTANCE',source='https://www.56dz.com/p/2839.html',source_file='harness-56dz2839-current.html',source_SHA=sha(E/'harness-56dz2839-current.html'),variants=v,seller_pack_conductors=40,provisional_sensor_J2_need=96,if_20cm_geometry_and_connector_fit_verified=dict(SKU='XC-56-37',configuration='female-female20cm40conductors',pack_quantity=3,buy_conductors=120,spare_after_J2=24,listed_parts_CNY='5.40'),not_closed=['2.54mm contact dimensions absent from seller text; fit proof pending','wire gauge, contact resistance and power branch rating unspecified','20cm length and routing/parasitic budget need actual panel geometry','Qingyuan freight/dispatch not quoted; aggregate stock not delivery promise','Not complete sensor electrode/screen/control/power harness'],DFRobot_FIT0030_reference=dict(source='https://www.dfrobot.com.cn/goods-366.html',configuration='10female-female20cmwires',search_index_listed_CNY='6.00',search_index_current_limit_mA_lt=1000,direct_web_open='timeout; no repeated retry or stock guarantee'),search_165_595_result='No qualified preweld compatible3V3 module found in this bounded query; unrelated schematics/community examples rejected. Not a proof that market has none.',requests_attempt='requests module unavailable before network; urllib publicGET succeeded200 once',order_or_outbound_message=False)
save(E/'harness-sourcing-current.json',wire)
stage=read(E/'sensor-fourlayer-progress-current.json')
for n in ['PCB-CURRENT-CAPACITY-RECOVERY-20261024.json','PCB-ACTIVE-WORK.json','实体交付当前入口.json','模块方案-当前证据.json']:
 p=B/n;x=read(p);x['updated_at']=now;x['sensor_fourlayer_trial_current']=stage;x['control_baseline_scope_correction_current']=proof;x['harness_sourcing_current']=str(E/'harness-sourcing-current.json')
 if 'Ground_thermal_trial_current' in x:x['Ground_thermal_trial_current']['superseded_by_current_progress']=str(E/'sensor-fourlayer-progress-current.json')
 save(p,x)
p=B/'模块方案-当前工作单.md';s=p.read_text(encoding='utf-8-sig')
s+='\n\n## 控制采购数量纠正（2026-10-27）\n\nPRODUCT-SPEC R03的8泛音区属于J10触屏，原图U9仅一片165、串入脚接地。上轮把它扩成8额外实体按钮、13按钮/两片165，现撤回。原图基线5按钮+按压编码器，保存/取消等独立操作合同仍待补齐，不因此宣称R06已完成，不改RTL/原理图。当前采购说明和control-baseline-scope-review-current.md/json已一致纠正。仅作为配线候选的新价格证据：伍陆XC-56-37母母20cm40线1.80元/条，3条120导体5.40元可覆盖96个J2导体位置的数量，但接头尺寸、20cm安装/电容预算、运费交期未证，不列最终配线。\n'
p.write_text(s,encoding='utf-8');print('Control scope corrected; source schematics SHA unchanged; harness exact variant saved pending fit/freight.')
