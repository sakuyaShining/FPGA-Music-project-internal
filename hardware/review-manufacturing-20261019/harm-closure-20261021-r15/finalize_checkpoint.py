"""Promote a verified routing candidate, retain fabrication holds, and mirror evidence."""
from pathlib import Path
from datetime import datetime,timezone
import sys,json,hashlib,zipfile,copy,csv,shutil
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;R14=ROOT/'freerouting-comparison-20261021-r14'
DELIVERY=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')
sys.path.insert(0,str(BASE));from native_project import PROJECT,info,SESSION
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
review=read(BASE/'actual-layout-review.json');pcb=PROJECT/'pcb/PCB1.epcb2'
assert sha(pcb)==review['pcb_sha256']
assert review['native_drc']=={'Connection Error':58} and review['vias']==530
assert review['source_r7_19_files_unchanged'] and review['all_changed_copper_matches_declared_plan']
assert len(review['actual_ground_stitch_contacts'])==5
files={p.relative_to(PROJECT).as_posix():sha(p) for p in PROJECT.rglob('*') if p.is_file()}
assert len(files)==19
for rel,h in info['source_files'].items():assert sha(Path(info['source_project'])/rel)==h
activepath=ROOT/'ACTIVE-ROUTING-CANDIDATE.json';archive=BASE/'previous-active-r7.json'
if not archive.exists():
    old=read(activepath);assert old['pcb_sha256']==info['source_pcb_sha256'];shutil.copy2(activepath,archive)
old=read(archive)
assert read(activepath)['pcb_sha256'] in [old['pcb_sha256'],review['pcb_sha256']]
outzip=DELIVERY/'native-4L-230-0clear-58open-harm-r15-20261021-CANDIDATE.zip'
if not outzip.exists():
    with zipfile.ZipFile(outzip,'w',zipfile.ZIP_DEFLATED) as z:
        for rel in files:z.write(PROJECT/rel,rel)
with zipfile.ZipFile(outzip) as z:
    assert z.testzip() is None and set(z.namelist())==set(files)
    assert all(hashlib.sha256(z.read(rel)).hexdigest()==h for rel,h in files.items())
drc=read(BASE/'native-drc.json');pending=[p['name'] for p in drc[0]['list']]
assert len(pending)==11 and 'HARM_CS_N' not in pending
assert sum(len(p['list']) for p in drc[0]['list'])==58
with (BASE/'remaining-networks-58open-r15.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['net','native_connection_error_objects','status'])
    w.writerows((p['name'],len(p['list']),'pending') for p in drc[0]['list'])
active=copy.deepcopy(old)
active.update(updated_utc=datetime.now(timezone.utc).isoformat(),role='Active R15 routing candidate: HARM closure and local reference stitches verified; archived procurement baseline remains R3',project=str(PROJECT),session=SESSION,checkpoint=BASE.name+'/native-candidate-checkpoint.json',source_capture=BASE.name+'/native-verified-capture.json',source_capture_sha256=sha(BASE/'native-verified-capture.json'),pcb_sha256=sha(pcb),api_lines=review['api_lines'],native_copper_line_records=review['native_copper_lines'],native_microtracks=28,vias=530,clearance_errors=0,physical_errors=0,unconnected_errors=58,pending_nets=pending,closed_pending_nets=old['closed_pending_nets']+['HARM_CS_N'],native_zip=str(outzip),native_zip_sha256=sha(outzip),files=files,previous_checkpoint=old['checkpoint'],previous_active_pcb_sha256=old['pcb_sha256'],components_moved=['C35','R30'],original_r7_source_files_unchanged=True,legacy_CPL_stale_designators=['C35','R30'],legacy_CPL_R30_position_stale=True,harm_routing_review=BASE.name+'/actual-layout-review.json',harm_length_mm=review['harm_length_mm'],new_signal_vias=5,new_ground_stitches=5,reference_gap_review=BASE.name+'/remaining-reference-gaps.json',harm_si_signoff=False,manufacturing_release=False)
write(BASE/'native-candidate-checkpoint.json',active)
write(activepath,active)
write(BASE/'native-mutation-state.json',dict(state='verified_saved_reopened_routing_candidate',pcb_sha256=sha(pcb),native_drc='native-drc.json',audit='native-apply-audit.json',ground_audit='ground-stitch-apply-audit.json',manufacturing_release=False))
write(BASE/'ground-stitch-final-verification.json',dict(pcb_sha256=sha(pcb),planned=5,created=5,native_clearance_errors=0,native_physical_errors=0,actual_reference_layers=[15,2],actual_annular_contacts=review['actual_ground_stitch_contacts'],signal_to_ground_distances=review['signal_reference_change_ground_vias'],geometry_pass=True,si_signoff=False,manufacturing_release=False))
r14text='''# R14：经过校准的 Freerouting 有界比较

输入是R7原生几何派生的离线DSN，不是嘉立创原生导出。校准采用不对称多边形、内层矩形及强制通孔，验证单位/方向/层映射；仅为交换校准。已有2.5.0 JAR SHA256 f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7，未下载新程序。

保留3290段真实原生铜线（含28微短线）、520孔、1079焊盘与437个逐段保护区；只有顶层1和内层16可布。传感/音频保护范围未取消，未导入其他网/器件移动。8轮/2分钟作业上限，运行结束并保留日志；非无限后台搜索。

结果仅闭合J6.17/U11.6/U15.8三个端点，R30.2仍孤立，5孔、67.500607mm；独立最小几何间距通过，但整网未闭合，因此本阶段自身未通过。工具因忽略其他网络/不含真实地铜而报告的总未布数和942项初始冲突，不能视为嘉立创原生DRC。

后续R15在独立原生副本移动同一上拉R30（保留3V3_IO，不改为3V3_PERIPH），加入约4.77mm支路和5个接地缝合孔后完整闭合，并重建实际地铜/保存重开/原生DRC。最新源与结论只读 ../harm-closure-20261021-r15/README.md，不可把R14 partial输出直接制造或重放到新源。
'''
(R14/'README.md').write_text(r14text,encoding='utf-8')
text=f'''# R15：HARM 闭合与局部回流复核

当前继续工作的原生工程：`{PROJECT}`，专用 `native_project.py`，会话 `{SESSION}`。ACTIVE-ROUTING-CANDIDATE.json 已晋升R15。采购数量基线 CURRENT-STATE.json 仍保留R3，不能用其旧PCB/CPL制造当前候选。

## 已验证结果

- 原生保存、四层地铜重建、关闭重开及完整DRC：**0间距 / 0物理 / 58未连通对象，剩11网**；此前R7为62对象/12网。230组件、1079焊盘、3288 API线+28原生微短线=3316段铜、530孔、4铜层。
- HARM_CS_N整网几何及原生连通，72.272362mm，5个新信号孔；R30移到实际焊盘中点87.69858/44.80052mm、270°，型号/值/焊盘/网络不变。R30.1仍接3V3_IO。所有原3V3_IO铜记录精确保留，未改供电拓扑。
- 新增5个GND孔，24mil盘/12mil钻孔，分别离信号换层点约0.9mm；每孔环形铜均实际接入内1与底层参考地，各层接触面积约0.204mm²。0.9mm为几何结果，1.5mm筛选目标不是标准或SI验收。
- 另外229个器件/焊盘、所有非HARM铜线、原520孔、规则、物理叠层、网络值、原理图及17个支持文件不变。原R7全部19文件哈希保持；音频铜及参考地投影未恶化。
- 原生清理合并HARM一段0.001mil短片，几何差异明确限于25.4nm；非HARM铜记录逐项精确相等。见actual-layout-review.json，不把API遗漏的28条微短线忽略。

![原生几何回流检查](harm-native-review.png)

图为真实保存源的几何重绘，绿色保留地铜孔洞；不是编辑器截图或实测。图已视觉检查，局部范围不代表整板制造图。

## 仍未关闭

HARM顶层对内1参考地投影98.22%，内2对底层89.19%（排除换层孔1mm及通孔焊盘0.5mm区域）；剩余投影空缺约0.417/3.903mm，最长单处0.417/1.487mm。已定位到remaining-reference-gaps.json。未建模实际边沿、线缆负载及回流波形，**不认定SI通过**。原I²S参考覆盖不足问题仍在。

剩余网络：{', '.join(pending)}。H05仍in_progress；机械配准、感应寄生、电源负载/热、准确屏幕出货配置/到手价、完整产品固件集成及最终工厂叠层仍需关闭。双屏和84电极能力保留，本轮未改产品RTL。

历史CPL的**C35、R30两行失效**。当前API读取/修改/DRC可用，但原生外部文件导出权限拒绝尚未获恢复证据；不再盲试或改权限绕过。最终同版Gerber/钻孔/BOM/CPL和平台匹配仍未齐，不能下单制造。采购Excel数量/料号未因本轮布线变化而更改。

## 保存、失败边界与继续方法

PCB SHA256 `{sha(pcb)}`；原生ZIP `{outzip}`，SHA256 `{sha(outzip)}`。19文件完整SHA清单在native-candidate-checkpoint.json，ZIP逐文件哈希与CRC已验证。改前R7快照 `{info['source_snapshot']}`；补地前R15在pre-ground-native-source.zip。所有旧版本保留。

R12/R13的长绕行比较未导入。R14只得到三个端点的部分路径；R15移动同一上拉后完整闭合。最初重复大几何联合的慢搜索已停止，使用等价预筛算法，详见search-performance-change.json；不是物理无解。原生清理冗余电源短片，最终原电源铜完全未变。

接续只用当前R15捕获/哈希和专用wrapper，先联合评估ADDR/PRESET/显示网络；如用Freerouting，必须从R15重新生成DSN，不重放R7输入或覆盖已闭合HARM。保留保护区，比较总长度/孔数/回流与原生DRC，避免只降低未连通数。未发生付款/下单/联系供方/下载固件/账户变更。

automation-2在当前用户目录仍ACTIVE每小时；防休眠helper已结束，不保证休眠唤醒。goal查询仍返回paused，但本轮最新人类“继续工作”授权已恢复工作意图；无主动resume接口，不更改账户或伪造状态，不标complete。目标未完成。
'''
(BASE/'README.md').write_text(text,encoding='utf-8')
openpath=ROOT/'release-open-items.csv'
if not (BASE/'pre-r15-release-open-items.csv').exists():shutil.copy2(openpath,BASE/'pre-r15-release-open-items.csv')
with openpath.open(encoding='utf-8-sig',newline='') as f:reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
for row in rows:
    if row['id']=='H05':
        row.update(status='in_progress',remaining='Active R15 verified 4-layer/3-dielectric, native 0 clearance/0 physical/58 open objects across11 nets,530 vias. HARM closed; I2S/HARM reference gaps, sensor loading and factory process remain unqualified; R3 baseline preserved',closure_evidence='harm-closure-20261021-r15/actual-layout-review.json: R30 moved;72.272362mm HARM/5 signal vias+5 GND stitches;actual reference-plane contacts;all unselected copper and229 other components unchanged;reopened native DRC0/0/58;not for fabrication')
    elif row['id']=='H06':
        row.update(remaining='217 SMT+13 through-hole per board unchanged; active R15 inherited C35 move and moved R30, so both historical CPL rows are stale. Final same-revision native CPL export, platform matching and costs pending',closure_evidence='harm-closure-20261021-r15/native-candidate-checkpoint.json and actual-layout-review.json;228 placements same as archived R3 except inherited C35 and new R30. Purchase workbook remains R3 quantity/material baseline;no manufacturing release')
with openpath.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
header=f'''> 最新工作版：**R15**，harm-closure-20261021-r15/README.md、native-candidate-checkpoint.json。HARM整网已闭合，完整原生保存重开DRC **0间距/0物理/58未连通，11网，530孔**。PCB SHA `{sha(pcb)}`。只用R15/native_project.py，会话 `{SESSION}`；不要用旧wrapper修改R3/R7。5信号孔+5参考地缝合孔，R30移动但3V3_IO原铜精确不变；原R7全部19文件未变。C35/R30历史CPL失效，制造未放行。原生包/回流空缺/下一步见R15 README。下文R7/R12/R13及旧goal状态均为历史。
>
> 接续：从R15源重新规划剩余11网，不重放R7 DSN。HARM仍有参考地空缺，音频原缺口未变，保留SI/传感/工厂/机械/报价/最终固件开放项。R5旧会话已正常关闭，R3/R7源保留。automation-2配置仍ACTIVE；goal接口最新返回paused而人类本次已明确继续，无resume接口可调用，不改配额/不标完成。防休眠helper未运行。

'''
for name in ['LATEST.md','AUTONOMOUS-CURRENT.md']:
    p=ROOT/name;prior=p.read_text(encoding='utf-8')
    if not prior.startswith('> 最新工作版：**R15**'):p.write_text(header+prior,encoding='utf-8')
write(BASE/'procurement-boundary.json',dict(active_routing_checkpoint=active['checkpoint'],archived_procurement_baseline='CURRENT-STATE.json',counts_unchanged=dict(board_references=230,SMT=217,through_hole=13,external_rows=32),workbook=str(DELIVERY/'硬件采购准备-r1.xlsx'),workbook_sha256=sha(DELIVERY/'硬件采购准备-r1.xlsx'),stale_CPL_designators=['C35','R30'],final_same_revision_native_export_pending=True,manufacturing_release=False))
assert read(BASE/'procurement-boundary.json')['workbook_sha256']=='59938d7887492c61e1b0c32ae14069d3dd1bbcf2c4da1ded779b480d0a9aee5b'
manifest={}
for folder in [R14,BASE]:
    for p in folder.rglob('*'):
        if not p.is_file() or any(q.startswith('runtime-') or q=='__pycache__' for q in p.relative_to(folder).parts):continue
        rel=p.relative_to(ROOT);dest=DELIVERY/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);assert sha(p)==sha(dest);manifest[rel.as_posix()]=sha(dest)
for name in ['ACTIVE-ROUTING-CANDIDATE.json','LATEST.md','AUTONOMOUS-CURRENT.md','release-open-items.csv']:
    p=ROOT/name;dest=DELIVERY/name;shutil.copy2(p,dest);assert sha(p)==sha(dest);manifest[name]=sha(dest)
for p in (ROOT/'evidence').glob('r15-harm-*'):
    if p.is_file():
        rel=p.relative_to(ROOT);dest=DELIVERY/rel;dest.parent.mkdir(exist_ok=True);shutil.copy2(p,dest);assert sha(p)==sha(dest);manifest[rel.as_posix()]=sha(dest)
write(DELIVERY/'r14-r15-delivery-manifest.json',dict(utc=datetime.now(timezone.utc).isoformat(),files=manifest,file_count=len(manifest),native_zip=str(outzip),native_zip_sha256=sha(outzip),source_pcb_sha256=sha(pcb),manufacturing_release=False))
assert all(sha(PROJECT/rel)==h for rel,h in files.items())
assert all(sha(Path(info['source_project'])/rel)==h for rel,h in info['source_files'].items())
print(json.dumps(dict(promoted=True,pcb_sha256=sha(pcb),pending_nets=pending,files_delivered=len(manifest),native_zip_sha256=sha(outzip),manufacturing_release=False),indent=2),flush=True)
