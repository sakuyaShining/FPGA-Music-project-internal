from pathlib import Path
import json,hashlib,datetime
B=Path(r'D:\FPGA-Project\codex-deliverables\dual-screen-review-20261020-v2');E=B/'module-plan-current-evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
specs=[Path('D:/FPGA-Project/maintenance-20261026/repo/project/PRODUCT-SPEC.md'),Path('D:/FPGA-Project/wb-sync-20261026/project/PRODUCT-SPEC.md'),Path('D:/FPGA-Project/authoritative-20261024/project/PRODUCT-SPEC.md')]
base=specs[0];source_rows={}
for line_no,line in enumerate(base.read_text(encoding='utf-8-sig').splitlines(),1):
 if line.startswith('| R'):
  cols=[x.strip() for x in line.strip('|').split('|')];source_rows[cols[0]]=dict(requirement=cols[1],source_line=line_no)
assert len(source_rows)==12
pitch=Path('D:/FPGA-Project/authoritative-20261024/project/reviews/20261024-pitch-endpoints-25/evidence/user-decision.json')
c5=pitch.with_name('c5-three-electrode.json')
assert sha(pitch)=='fc54a567a72d480f2d0b0be2dd53702ed8c8180575d97db175f0a6fb88f0ac5f'
assert sha(c5)=='a29b266329462791424f2d844a5be887a5051c36190cad8705ce9ed93d03d566'
sources={}
for n,k in [('firmware-readonly-interface-current.json','inputs'),('audio-registered-source-current.json','read_sources')]:
 for p,v in read(E/n)[k].items():sources[p]=dict(expected=v['sha256'],actual=sha(Path(p)),unchanged=sha(Path(p))==v['sha256'])
assert all(r['unchanged'] for r in sources.values())
data=[
('R01','目标保留；完整产品未签收','Nano20K、共享32组×16分量、四槽分层目标不改。旧两层限制不能当产品上限，已有四槽隔离候选也不是整机通过。','四槽组合、完整资源/时序、真实物理输入和音频输出共同运行。'),
('R02','目标保留；物理语义/表情链未闭合','84路前端容量保留。已核直接用户记录：25音位，每音位含C5均3电极，75+5八度档+4备用=84；不采用旧26音位示例。','现有row*6+lane只是采集索引双射，尚须明确75+5+4物理用途、25音位连续位置/逐指力度、滑音/颤音/推弦、八度行为及真实标定/串扰。'),
('R03','目标保留；采购/驱动整链未签收','保留单J10约7英寸电容多点触控泛音屏、整和弦修饰、松手保持和RESET平滑恢复，不换成电脑或位图按键。','完整ER-TFTM070-5V4配置报价/线束、RA8875与FT5316驱动、复位和整机效果验收。'),
('R04','方案遵循；曲谱页面尚未交付','不恢复J11实体可视化屏，曲谱指引由J10承接；不因此取消PC可视化。','J10页面切换、曲谱来源/录入及演奏中指引接合。'),
('R05','目标保留；完整编辑/激发未签收','频谱/激发、包络/表情响应及四快捷槽组合保留，不因模块化改成固定音色播放器。','完整逐槽激发/参数编辑/试听/组合与实时演奏接合；不把加法合成概括成已完成通用物理建模。'),
('R06','目标保留；独立操作接口合同未闭合','保留编辑键→选槽→编辑激发和音色、独立操作键。不默认用菜单取代独立键，不引入未批准16键/PCF8575/GPIO表。','按钮/编码器具体预焊实现、全部独立操作分配及逐针合同，与产品编辑流程一致。'),
('R07','目标保留；存储闭环未签收','正式定义/编辑草稿/运行修饰/在响实例分离及断电保存保留，双bank仍为原子更新，16词完整性不删。','试听/应用/保存/取消语义，24LC256两字节地址/分页/ACK轮询、提交保护与断电恢复。'),
('R08','目标保留；录放与曲谱两链未完成接合','保留真实声音PCM录制/回放、曲谱播放同时现场演奏；同等共享32组，空闲→松键尾音→最早按住音，整音符回收/完整起音。','TF卡/文件/SDRAM/最终混音/音频事件配对及真实源到分配器；不能用记音符代替录声音，也不自动降两层。'),
('R09','按原规格AUX方向；物理链未完成','AUX接外部有源音箱，尊重不装机内喇叭偏好；独立功放/裸喇叭不是AUX必购。原图功放支路不据此自动删除。','线路DAC到3.5mm TRS的准确转接/面板件、滤波保护、时钟格式/初始化/电平及上电静音；耳机口不冒充线路输出。'),
('R10','目标保留；独立整机运行未签收','Nano承担核心演奏/编辑/保存，不新增电脑、树莓派或计算MCU依赖；PC可视化/调试仍可选。','脱离电脑后自主启动、DAC/屏/触摸初始化、实体编辑保存及录放完整闭环。'),
('R11','目标保留；从未完成整机实测','最坏触摸到声音≤10ms目标没有放宽。扫描/滤波/全部通道/共享总线/混音/DAC均计入。','真实84通道、触屏和录放并发最坏延迟测量；电容/面积代理不自动等于真实测力，数字力度阶数不是精度证明。'),
('R12','制造形式依后续明确授权调整；完整交付未完成','用户10月26日允许不用自制主PCB，改模块/必要简单预焊小板；完整可装整机与功能要求仍保留。不能把原227件功能账直接作废。','模块精确SKU/预焊/数量/接口与唯一采购接线版本；必要自制小板仍需同版原理图/PCB/BOM/CPL/制造装配文件、机械/线束/报价，全部费用≤700并核清远交期。')]
records=[]
for key,status,plan,gap in data:records.append(dict(id=key,**source_rows[key],current_plan=status,scope=plan,remaining=gap,full_product_acceptance=False,function_deletion_authorized=False))
now=datetime.datetime.now().astimezone().isoformat()
r=dict(at=now,spec_source=str(base),spec_sources=[dict(path=str(p),sha256=sha(p)) for p in specs],
 version_resolution='maintenance and wb-sync copies identical; authoritative copy has direct25pitch/C5 decisions and newer product annotations despite older folder name. Requirements12 body used as baseline; user-direct postbaseline authorization controls R12. Do not import old e098/a3 hardware counts as current.',
 pitch_decision_sources=[dict(path=str(pitch),sha256=sha(pitch)),dict(path=str(c5),sha256=sha(c5))],
 decision_ID_collision_note='D-021/D-022 numerical prefixes are reused in separate local lines (pitch vs maintenance windows). Refer full IDs, direct evidence and source SHA; never merge by number alone.',
 requirements=records,registered_source_SHA_recheck=sources,registered_source_files_checked=len(sources),other_chat_or_unregistered_candidate_latest_state_claimed=False,
 main_conclusion='R01-R11 remain targets, not accepted function-equivalence proof. R12 manufacturing form adjusted by explicit user authority; full coherent assembly still required. R09 already favors AUX/no internal speaker; previous reliance on older61spec was incomplete.',
 previous_schedule_scope='Earlier rough duration ranges are not a complete R01-R12 work breakdown and cannot guarantee all12 requirements orNov4 delivery.',
 native_CAD_RTL_build_flash_changed=False,orders_payments_messages=False,physical_tests='UNMEASURED',complete_purchase_plan=False)
write(E/'product-spec-12-comparison-current.json',r)
rows='\n'.join('| '+x['id']+' | '+x['requirement']+' | '+x['current_plan']+' | '+x['remaining']+' |' for x in records)
md='''# PRODUCT-SPEC.md 12条与当前模块/混合方案逐项对照

结论：R01—R11功能目标继续保留，但尚没有完整实体等价/验收证据；R12的制造形式已经用户后续明确允许调整为模块/必要简单预焊小板，完整可装整机仍须交付。不能把“目标未删”当“实现已满足”。

基线：D:/FPGA-Project/maintenance-20261026/repo/project/PRODUCT-SPEC.md（与wb-sync同字节）。另一份authoritative规格及两份直接用户记录明确25音位/C5三电极，已核证据SHA，故不沿用旧25/26待定。83b238df小板及951主板实际状态沿当前入口，不沿用规格表e098/47项旧计数。没有改原规格或其他聊天仓库。

| ID | 原要求 | 当前方案判断 | 未闭合项 |
|---|---|---|---|
'''+rows+'''

R09纠正：此统一规格本来就写AUX外接有源音箱及不装机内喇叭偏好。我此前优先引用旧61号并继续搜独立功放/喇叭，范围不准确；这些不再作为AUX必购/定稿前置。原图功放支路不自动删除；必要DAC/3.5mm接口/保护保留。

R02特别说明：84路row*6+lane映射双射只证明未漏采集位置，不证明25音位/C5连续位置/逐指力度/八度行为已实现。按已核直接记录的75+5+4逐一落实仍是必要工作，不应重新询问已决定的25音位或C5三电极。

实现边界：本次复核登记producer16个文件SHA均未变；不声称其他聊天或未登记隔离候选没有新实现。旧规格中两层限制不能覆盖其后四槽候选增量；反过来，候选逻辑刺激通过也不是实体全产品验收。

时间边界：此前前端/接口粗估不构成12条完整任务分解或11月4日交付保证，尤其R05—R08、R10—R11仍需产品固件接合和实物验证。不能将剩余工作缩写为“只差6路走线”。实物UNMEASURED，完整采购方案未放行。
'''
(E/'product-spec-12-comparison-current.md').write_text(md,encoding='utf-8')
for n in ['PCB-CURRENT-CAPACITY-RECOVERY-20261024.json','PCB-ACTIVE-WORK.json','实体交付当前入口.json','模块方案-当前证据.json','实体模块方案约束-current.json']:
 p=B/n;d=read(p);d['updated_at']=now;d['product_spec_12_comparison']=str(E/'product-spec-12-comparison-current.json')
 d['audio_product_scope']='R09 AUX external active speaker; user preference no internal speaker. No default new amp/speaker product requirement; do not auto-delete old schematic branch.'
 if 'read_first' in d:d['read_first']=list(dict.fromkeys([str(E/'product-spec-12-comparison-current.md')]+d['read_first']))
 write(p,d)
p=B/'模块方案-当前工作单.md';t=p.read_text(encoding='utf-8');marker='\n## PRODUCT-SPEC十二条对照'
p.write_text(t.split(marker)[0]+marker+'\n\n逐项对照已保存至module-plan-current-evidence/product-spec-12-comparison-current.md/json。R01—R11目标保留未整机签收；R12制造形式依用户后续授权调整，完整可装要求不降。R09本来就偏好AUX/不装机内喇叭，不以新增独立功放/喇叭阻塞。R02按直接用户记录落实25音位/C5三电极、75+5+4=84，当前84采集双射不等于产品表情完成。登记producer16文件SHA未变，不把旧两层状态或其他候选当最新整机结论。先前几天粗估不代表12条全功能交付承诺。\n',encoding='utf-8')
p=E/'audio-AUX-scope-current.json';d=read(p);d['current_product_spec_R09']=dict(path=str(base),line=source_rows['R09']['source_line'],requirement=source_rows['R09']['requirement']);d['historical_onboard_speaker_branch']='R09 already records preference AUX and no internal speaker. Old61 owned-speaker assumption is historical, not current required new amp/speaker procurement. Do not auto-delete schematic branch.';write(p,d)
print(json.dumps(dict(saved=str(E/'product-spec-12-comparison-current.md'),requirements=len(records),registered_sources_checked=len(sources),native_RTL_unchanged=True),ensure_ascii=False))
