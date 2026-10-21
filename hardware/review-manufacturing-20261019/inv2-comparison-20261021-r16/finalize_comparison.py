"""Preserve the unsuccessful INV2 comparison without changing the active PCB."""
from pathlib import Path
import json,hashlib,shutil
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
DEST=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
active=read(ROOT/'ACTIVE-ROUTING-CANDIDATE.json');val=read(BASE/'independent-validation.json');top=read(BASE/'topology-diagnostic.json')
assert active['pcb_sha256']==val['source_pcb_sha256']==top['source_pcb_sha256']
assert not val['geometric_pass'] and val['lines']==0 and val['new_vias']==0
assert all(sha(Path(active['project'])/rel)==h for rel,h in active['files'].items())
text='''# R16：INV2 有界比较，未采用

从最新R15源重新生成离线DSN：3316段真实原生铜线、530孔、1079焊盘、437逐段保护区。已有R14的坐标/层/孔校准及相同SES解析器继续适用；没有重复原生导出权限失败，也没有导入其他网/移动器件。

Freerouting2.5.0在8轮/2分钟作业上限内正常结束，约60秒；没有生成INV2铜或过孔，仍两个焊盘孤岛，不是成功布线。日志有Simplex分割警告。941项交换模型的既有固定对象/保护区冲突与全局380未布项，不等于嘉立创原生错误。

独立连续几何检查：6mil线、0.165mm筛选间距下，R13.1位于顶层自由区40，U7.6位于区116，无共同顶层区。此为当前固定铜/孔和禁止区域模型，不证明四层物理无解。不能凭只有约12.6mm直线距离就画一条跨障碍线。

R13型号0603WAF2200T5E，2脚连接SENSE_2，1脚为INV2；它是220Ω串联元件，不是供电上拉。不得沿用R30办法随意移动并破坏已有感应布线。下一次需联合考察端点出线、合法换层区和真实地参考；用实际路径长度/孔数筛选，不重跑相同DSN。

**ACTIVE保持R15**：原生0间距/0物理/58未连通对象、11网、530孔。19文件哈希全部未变；未重复无变化的原生DRC。R15完整闭合的HARM及原快照保留，制造仍未放行。
'''
(BASE/'README.md').write_text(text,encoding='utf-8')
result=dict(utc=datetime.now(timezone.utc).isoformat(),active_checkpoint=active['checkpoint'],source_pcb_sha256=active['pcb_sha256'],outcome='not_adopted_no_route_produced',source_19_files_unchanged=True,native_modified=False,native_drc_repeated=False,native_drc_last_verified=dict(clearance=0,physical=0,connection=58),next_step='Plan joint terminal escape/layer changes for INV2 or other pending nets against R15; preserve SENSE_2 and actual reference geometry; no identical DSN replay.',manufacturing_release=False)
(BASE/'CURRENT-RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
header='''> 最新离线比较：**R16未采用，ACTIVE仍R15**。inv2-comparison-20261021-r16/README.md 与 CURRENT-RESULTS.json：从R15重新生成DSN，8轮有界结束但INV2无新铜；连续几何确认两端顶层自由区不同。R13为SENSE_2串联220Ω，不能套用R30供电上拉移动方案。原生19SHA未变，不重复相同DSN/无变化DRC。当前仍0/0/58、11网、530孔；下一步联合端点出线/合法换层及参考地，不将路由失败写成物理无解。下方R15为最新有效原生检查点。

'''
for name in ['LATEST.md','AUTONOMOUS-CURRENT.md']:
    p=ROOT/name;prior=p.read_text(encoding='utf-8')
    if not prior.startswith('> 最新离线比较：**R16'):p.write_text(header+prior,encoding='utf-8')
manifest={}
for p in BASE.rglob('*'):
    if not p.is_file() or any(x.startswith('runtime-') or x=='__pycache__' for x in p.relative_to(BASE).parts):continue
    rel=p.relative_to(ROOT);dest=DEST/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);assert sha(p)==sha(dest);manifest[rel.as_posix()]=sha(dest)
for name in ['LATEST.md','AUTONOMOUS-CURRENT.md']:
    shutil.copy2(ROOT/name,DEST/name);manifest[name]=sha(DEST/name)
# Earlier delivery inventory hashes for mutable entry documents are historical.
# Refresh the current inventory entries so it remains valid after this checkpoint.
inventory=DEST/'r14-r15-delivery-manifest.json';prior=read(inventory)
for name in ['LATEST.md','AUTONOMOUS-CURRENT.md']:prior['files'][name]=sha(DEST/name)
prior['entry_documents_refreshed_utc']=result['utc'];prior['entry_refresh_checkpoint']=BASE.name+'/CURRENT-RESULTS.json'
inventory.write_text(json.dumps(prior,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
final=dict(utc=result['utc'],files=manifest,file_count=len(manifest),active_pcb_sha256=active['pcb_sha256'],native_modified=False,manufacturing_release=False)
(DEST/'r16-delivery-manifest.json').write_text(json.dumps(final,indent=2)+'\n',encoding='utf-8')
assert all(sha(DEST/rel)==h for rel,h in prior['files'].items())
assert all(sha(DEST/rel)==h for rel,h in manifest.items())
assert all(sha(Path(active['project'])/rel)==h for rel,h in active['files'].items())
print(json.dumps(dict(delivered=len(manifest),source_unchanged=True,active_pcb_sha256=active['pcb_sha256'],manufacturing_release=False),indent=2))
