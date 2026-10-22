from pathlib import Path
import datetime,hashlib,json,zipfile
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
paths=[next((P/'docs/02-技术方案').glob(prefix+'*.md')) for prefix in ('38-','39-','49-')]
B=N/datetime.datetime.now().strftime('before-%Y%m%d-%H%M%S');B.mkdir()
before={p.relative_to(P).as_posix():sha(p) for p in paths}
with zipfile.ZipFile(B/'before.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in paths:z.write(p,p.relative_to(P).as_posix())
with zipfile.ZipFile(B/'before.zip') as z:
    assert z.testzip() is None
    for rel,digest in before.items():assert hashlib.sha256(z.read(rel)).hexdigest()==digest
summary='''**2026-10-17在手硬件更正**：用户最新明确当前只有Tang Nano 20K和喇叭，暂无屏幕与实体触控；以此覆盖较早“已有显示屏”的在手清单，不能安排立即点屏/实体触控实测，也不将屏幕候选视为已购买/已到手。约7英寸右手泛音显示触控、逐音滑条及可视化功能目标保持；接口/面板仍待选型闭环与实物验证。73号板载音频限定实测继续有效，原RTL/包/快照未改。后续优先推进不依赖新增外设的完整乐器配置/逐层包络及主机参数应用，使用虚拟输入和仿真继续验证，再将已接合路径上板；录放/存储仍按资源与接口证据推进，不能把板载TF卡座当作已有存储卡。此为开发顺序建议，不替用户冻结音乐行为、取消功能或发起采购。详情见`notes/hardware-availability-20261017/CURRENT.md`。'''
for p in paths:
    text=p.read_text(encoding='utf-8');assert '**2026-10-17在手硬件更正**' not in text
    if p.name.startswith('38-'):
        anchor='## 0. 最重要的发现：最新成果并不都在 main\n';assert anchor in text;text=text.replace(anchor,anchor+'\n'+summary+'\n',1)
    else:
        first,rest=text.split('\n',1);text=first+'\n\n> '+summary+'\n'+rest
    p.write_text(text,encoding='utf-8')
current='''# 当前可用硬件与继续开发边界 · 2026-10-17

用户最新确认：仅有Tang Nano 20K和喇叭，暂无屏幕和实体触控。以此为最新在手清单；此前YT240L008N/ILI9341的选型信息可作候选资料，不能当作当前可接线实物，也不推断其采购/所有权状态。

## 状态

- Tang Nano 20K＋喇叭：在手；73号限定板载音频检查**已验证**，不是完整产品验收。
- 可视化屏、约7英寸泛音触摸显示、音高滑条/电容前端：本轮无实物可用，实体**待实现/待验证**；产品功能目标保持。
- 完整自定义乐器配置、逐层包络、GUI/实体完整应用、四层同时、非易失保存和伴奏录放/曲谱：继续**部分实现/待实现**；不能因音频诊断通过而上调状态。
- 未确认在手的TF存储卡、编码器、其他外设不作为当前实测前提。开发板自带卡座不代表有卡。

## 下一步建议

先完成完整乐器配置/逐层包络的隔离实现与资源、回归检查，再接主机参数应用；通过虚拟输入/触控报告和显示接口模型继续验证，已接合部分可使用现有板与喇叭试听。录放/同步接口及存储资源可先仿真，持久介质与真实输入/显示的验证等待对应实物。

上述是开发顺序建议，不裁定未决音乐交互、不将诊断镜像当完整GUI固件、不发起采购，不改变约500元预算或取消实体功能。本轮只更新文档，未打开串口/下载/改RTL、参数表、约束或旧快照。

38/39/49入口本轮有授权范围内的清单更新；旧72/73交付中的文档哈希属于历史快照，预期显示这些入口的文档漂移，不能为消除提示覆盖旧清单。源码/二进制/板级证据继续保持。本目录delivery.json记录变更前后SHA与原因。
'''
(N/'CURRENT.md').write_text(current,encoding='utf-8')
record=dict(status='在手清单已记录；后续实现顺序为建议',time=datetime.datetime.now().astimezone().isoformat(),user_statement='暂无屏幕和实体触控 目前仅有硬件是tangnano20k和喇叭',source_main='fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12',before=before,after={p.relative_to(P).as_posix():sha(p) for p in paths},backup=dict(path=B.relative_to(P).as_posix(),zip_sha256=sha(B/'before.zip')),files={p.relative_to(P).as_posix():sha(p) for p in (Path(__file__).resolve(),N/'CURRENT.md')},previous_hardware_delivery_sha256=sha(P/'notes/board-audio-hardware-20261017/delivery.json'),rtl_changed=False,serial_opened=False,fpga_programmed=False,flash_read_or_written=False,tests='文档核对；main192身份PASS；修改前73号679项交付检查PASS。未重复运行无关仿真/硬件测试。')
(N/'delivery.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS inventory recorded; three entry documents updated; source/artifacts unchanged')
