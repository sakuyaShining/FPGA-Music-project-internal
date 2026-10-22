"""Archive completed offline trials without promoting or mutating any native PCB."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
HW = HERE.parent
DELIVERY = Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
active = json.loads((HW / 'ACTIVE-ROUTING-CANDIDATE.json').read_text(encoding='utf-8'))
project = Path(active['project'])
checked = {rel: sha(project / rel) for rel in active['files']}
assert checked == active['files'], 'Active native source changed: stop, do not archive as unchanged'
raw = HERE / 'shielded-inner-trial/plan.json'
plan = json.loads(raw.read_text(encoding='utf-8'))
assert plan['source_pcb_sha256'] == active['pcb_sha256']
assert not plan['native_imported'] and not plan['manufacturing_release']
assert sha(Path(plan['source_capture'])) == plan['source_capture_sha256']
now = datetime.now(timezone.utc).isoformat()
assessment = {
    'utc': now,
    'source_pcb_sha256': active['pcb_sha256'],
    'source_files_verified_unchanged': checked,
    'active_candidate_remains': 'local-layout-20261021-r7',
    'raw_plan_sha256': sha(raw),
    'native_imported': False,
    'native_six_layer_project_created': False,
    'manufacturing_release': False,
    'goal_status_observed': 'usageLimited',
    'finished_process': {'session_id': 49084, 'exit_code': 0},
    'offline_routes_only': [dict(net=r['net'], new_vias=len(r['vias']),
                                summed_line_length_mm=r['length_mm']) for r in plan['routes']],
    'failed': plan['failed'],
    'decision': 'Do not adopt these routes or select six-layer manufacturing from this experiment.',
    'failure_boundaries': [
        'R8 initial raster failed to preserve polygon holes; those failures are invalid evidence of physical impossibility. Corrected v2 and mesh fanout trials are retained separately.',
        'R8 HARM_CS_N mixed-layer diagnostic connects geometrically with 13 new vias /150.520189mm; rejected against engineering via target <=6, not a factory rule.',
        'R9 PRESET3 4 vias/157.273000mm and ADDR1 7 vias/322.249112mm are offline candidates only; obvious detours were not accepted.',
        'R9 No inner16 route is a stale error label: actual proposed trunk layer is17 after source16->17 remap. It means the bounded search failed, not that six layers are physically impossible.',
        'Raw R9 actual_four_layer_connected is also an inherited field name. The imported helper is six_layer_geometry; it lacks independent positive/negative cross-layer regression, so the field is not native connectivity evidence.',
        'R9 proposes S/G/G/S/G/S with control layer17 and GND15/16/18. No native physical stack, rebuilt planes, actual return coverage, sensing capacitance, factory approval or price has been established.',
        'Candidate summed segment lengths may include shared/overlapping branches; no optimized copper-length claim is made.',
        'No native PCB edits occurred, so R7 DRC0/0/62 remains the last native result; no new DRC is claimed.'
    ],
    'next_after_normal_usage_recovery': [
        'Inspect continuous free-space components at each HARM anchor on proposed layer17, and record the exact foreign copper that separates components; check raster endpoint aliasing before further routing.',
        'Retain R7 as active. Compare local GND/power-stub cleanup in an isolated 4-layer candidate before adding manufacturing cost. Preserve all existing net continuity, widths and rules.',
        'For any six-layer continuation, first independently test same-XY/different-layer nonconnection and through-via positive connection; only create a native candidate if route quality justifies it.',
        'Before any promotion rebuild real ground planes, save/reopen and run full native DRC, verify sensor/I2S reference geometry and all unchanged sources. Export fresh same-version CPL: historical C35 placement is stale.',
        'Keep purchasing, source quotes, physical measurements and firmware integration gates open; do not replay rejected plans.'
    ]
}
(HERE / 'CURRENT-TRIAL-RESULTS.json').write_text(json.dumps(assessment, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
readme = '''# R8/R9 离线布线对照检查点

当前原生工作源仍为 R7，PCB SHA256 `2cec51920011e0e8512956064d1c3b396bc4b98b98a94989432e883b30029eae`。本轮逐文件核对19个原生文件，全部未变；最后原生 DRC 仍为0间距/0物理/62未连通、520过孔。本轮没有新原生修改或制造放行。

R8 修正了栅格障碍物忽略多边形孔洞的问题，并增加连续三角网出线。HARM_CS_N 混合层诊断可连通，但需13个新过孔、约150.52mm走线，未采纳；六孔目标是工程质量限制，不是工厂规则。旧搜索失败不能当成物理无解。

R9 仅对照试算六层 S/G/G/S/G/S：已有内16信号映射至17，设15/16/18为地层。PRESET3 得到4孔、157.27mm，ADDR1 得到7孔、322.25mm，另外三网搜索失败。这些绕行方案均未采纳，没有创建六层原生工程，也没有决定层数或增加采购预算。线长是各段求和，可能包含公共支路重叠。

原始计划中的 `actual_four_layer_connected`、`No inner16 route` 是继承的旧字段/提示；实际调用六层几何辅助模块、计划主干为17层。这些字段不构成原生验证。跨层辅助模块仍需独立正负对照；真实地铜、I²S回流、传感寄生、叠层与报价都未验证。

下一步：先检查 HARM 各端点连续自由空间的连通分区和实际阻挡铜，排除栅格端点误差；再比较四层局部地线/电源支路整理。不要重复运行旧计划，不要为搜索失败直接加层。后续原生修改须隔离副本、保持规则及已连通网络、重建地铜、保存重开并完整DRC。

当前目标工具返回 `usageLimited`，保存本检查点等待正常额度恢复，不改目标状态、不消耗重置权益。自动接续沿用已有 automation-2。采购与制造仍未完成；历史C35贴片坐标已失效，必须最终同版原生CPL。

详细源哈希、各试算结果、失败边界和下一步见 `CURRENT-TRIAL-RESULTS.json`；四层诊断见相邻 `control-closure-20261021-r8`。SD卡精确型号仅新增候选，尚未确认卖家、库存或人民币到手价，未改采购主清单。
'''
(HERE / 'README.md').write_text(readme, encoding='utf-8')
entry = '''> 最新离线检查点：`six-layer-comparison-20261021-r9/README.md`。R8/R9绕行方案未采纳，未创建六层原生工程；ACTIVE仍R7，19源文件哈希未变，最后原生0/0/62。下一步先诊断连续自由空间与局部电源/地支路阻挡，不要盲目加层。目标当前返回usageLimited，等待正常恢复；不标完成、不改配额。\n\n'''
for name in ['AUTONOMOUS-CURRENT.md', 'LATEST.md']:
    path = HW / name
    text = path.read_text(encoding='utf-8')
    if not text.startswith(entry): path.write_text(entry + text, encoding='utf-8')
for source_dir in [HW / 'control-closure-20261021-r8', HERE]:
    dest = DELIVERY / source_dir.name
    for source in source_dir.rglob('*'):
        if not source.is_file() or '__pycache__' in source.parts: continue
        target = dest / source.relative_to(source_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
for name in ['AUTONOMOUS-CURRENT.md', 'LATEST.md']:
    shutil.copy2(HW / name, DELIVERY / name)
shutil.copy2(HW / 'six_layer_geometry.py', DELIVERY / 'six-layer-comparison-20261021-r9/six_layer_geometry.py')
manifest = {}
for name in ['control-closure-20261021-r8', 'six-layer-comparison-20261021-r9']:
    for source in (DELIVERY / name).rglob('*'):
        if source.is_file() and source.name != 'delivery-manifest.json':
            manifest[source.relative_to(DELIVERY).as_posix()] = sha(source)
out = DELIVERY / 'six-layer-comparison-20261021-r9/delivery-manifest.json'
out.write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
assert all(sha(DELIVERY / rel) == digest for rel, digest in manifest.items())
assert {rel: sha(project / rel) for rel in active['files']} == checked
print(json.dumps({'native_files_unchanged': len(checked), 'delivery_files_verified': len(manifest),
                  'assessment': str(HERE / 'CURRENT-TRIAL-RESULTS.json'),
                  'active_unchanged': 'r7', 'manufacturing_release': False}, indent=2))
