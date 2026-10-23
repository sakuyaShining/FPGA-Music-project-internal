"""Prepare the management entry for the reviewed 2026-10-23 design capture.

This edits management files in this checkout only. No functional source or CAD
workspace is changed. Source archives retain their separate validation boundary.
"""
from pathlib import Path
import datetime, hashlib, json

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()


def read(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))


def write(name, data):
    (ROOT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def replace(name, before, after):
    p = ROOT / name
    raw = p.read_bytes()
    # Keep the previous body byte-for-byte apart from the targeted text.
    a, b = before.encode('utf-8'), after.encode('utf-8')
    if a not in raw:
        raise ValueError('Missing expected text in ' + name)
    p.write_bytes(raw.replace(a, b))


def main():
    if (ROOT / 'project/design-state.json').exists():
        raise ValueError('Already registered; review a new version rather than overwriting this one-time capture')
    for name in ('38-代码盘点与实现基线-2026-10-09.md', '39-最新设计构想与落地差距-2026-10-09.md', '49-最终收敛设计总纲-2026-10-15.md'):
        p = ROOT / 'docs/02-技术方案' / name
        prefix = '> **2026-10-23 当前范围覆盖提示**：先读[最新设计入口](../../project/DESIGN-CURRENT.md)及`project/design-state.json`。用户已取消J11实体音乐可视化屏，保留J10泛音触控屏；本文旧双屏要求与旧状态不覆盖后续决定。新观察FPGA候选和旧已验检查点分列，本轮未修改产品RTL。\n\n'
        p.write_bytes(prefix.encode('utf-8') + p.read_bytes())
    replace('README.md', '**从 [project/CURRENT.md](project/CURRENT.md) 开始。**', '**先读[当前设计](project/DESIGN-CURRENT.md)与[快速取得版本](project/QUICKSTART.md)，再读 [project/CURRENT.md](project/CURRENT.md)。**')
    replace('AGENTS.md', '# 项目工作入口', '# 项目工作入口\n\n**2026-10-23 v2：先读`project/DESIGN-CURRENT.md`及`project/design-state.json`。用户在硬件会话已明确取消J11实体音乐可视化屏，保留J10泛音构造触控屏；旧双屏红线仅这一项被覆盖。最新观察FPGA候选与旧已验证源必须分开，不把任何旧PASS继承到新源。快速获取见`project/QUICKSTART.md`。**')
    replace('AGENTS.md', 'handoff/20261022-management-v1', 'handoff/20261023-design-v2')
    replace('docs/00-协作/AGENT-BOARD.md', '最后更新：2026-10-22 00:55（WorkBuddy 建立）', '管理覆盖更新：2026-10-23（见§10）。§1及旧交接中的计数/所有者标签为历史，接手先查当前设计与版本身份。\n\n最初建立：2026-10-22 00:55（WorkBuddy）')
    replace('docs/00-协作/AGENT-BOARD.md', '新建工作树请从 `main` 拉，不要从旧提交（如 `2770e63`）拉，否则看不到本板。', '本管理PR合入前，新工作树从已发布`codex/project-management-20261022`起步；合入后可用包含该入口的main。禁止从旧提交（如`2770e63`）推断当前设计。')
    replace('docs/00-协作/AGENT-BOARD.md', '1. **双屏保留，不合屏、不缩小推子。** RA8875 出推子/编辑/曲谱，ILI9341 出完整音乐可视化。（Codex 87 号 §4.6）', '1. **现行范围：保留J10右手泛音触控屏，用户已取消J11实体音乐可视化屏。** 2026-10-22硬件会话直接人类决定覆盖旧双屏红线，原话及turn见`project/versions/design-decision-20261023.json`。不据此削减其他功能；旧双屏实验保留历史。')
    replace('docs/00-协作/AGENT-BOARD.md', '**新建工作树从 `main` 拉**，不要从 `2770e63` 拉。', '**新建工作树从已发布管理分支拉**；PR合入后再用包含新入口的main，不要从`2770e63`拉。')
    p = ROOT / 'docs/00-协作/AGENT-BOARD.md'
    with p.open('ab') as f:
        f.write(('\n\n## 10. 2026-10-23 最新设计与Git接手修复\n\n'
                '- 做了什么：本会话继续管理轴，仅修改4d37入口、保全/恢复工具与管理文档。核对硬件会话人类决定，修正J11取消/J10保留；保全D盘新观察FPGA源码、测试、设计说明和所列硬件恢复包。\n'
                '- 在飞什么：独立FPGA会话仍在改D盘候选，owner会话身份未完全登记；硬件会话“查看 huangyongtao 最新进展”（01a15ee5-fa24-7501-8475-ad28a0f08939）继续写06df及U9施工副本。本管理会话不接管它们。\n'
                '- 卡在哪：没有完整产品顶层验收；原100输入的旧专项PASS不签收新候选；硬件总入口缓存与下级施工状态存在先后差异，必须核对实际原生哈希。\n'
                '- 需要对方什么：各owner收工提交命名分支、精确输入/结果身份和源截止时间；未来修改不能隐含纳入本批已发布检查点。main继续按§4由用户合并。\n'
                '- 下一手从哪读：`project/DESIGN-CURRENT.md`、`project/design-state.json`、`project/QUICKSTART.md`，发布分支`codex/project-management-20261022`；提交由实际远程分支及v2冻结标签解析，禁止凭日期冒充当前。\n').encode('utf-8'))
    capture = read('project/versions/latest-design-inputs-20261023.json')
    decision = read('project/versions/design-decision-20261023.json')
    design = dict(schema=1, design_version='design-20261023-v2', updated_at=NOW,
                  entry_branch='codex/project-management-20261022', entry='project/DESIGN-CURRENT.md',
                  quickstart='project/QUICKSTART.md', current_inputs_manifest='project/versions/latest-design-inputs-20261023.json',
                  authority=dict(human_scope_decision='project/versions/design-decision-20261023.json', thread_id=decision['thread_id'], turn_id=decision['turn_id']),
                  scope=dict(platform='Tang Nano20K', groups=32, partials_per_group=16, layer_target=4,
                             physical_music_visualization_display=False, right_harmonic_touchscreen='J10 retained', sensor_capacity=84,
                             other_features_reduced_by_management=False, rtl_scope_alignment='not completed across all profiles'),
                  latest_observed_fpga=dict(role='unmerged WIP; not the validated 100-input checkpoint',
                      source_root='D:/FPGA-Project/codex-builds/fpga-m1-agent-work', build_inputs=len(capture['effective_build_inputs']),
                      removed_registered_inputs=[x for x in capture['changed_registered_inputs'] if x not in capture['effective_build_inputs']],
                      validation='Original author receipts preserved as scoped claims; not rerun or inherited by management',
                      complete_product_top=False, owner='Independent active FPGA session; exact session identity unconfirmed'),
                  hardware=dict(owner_thread=decision['thread_id'], live_entry='C:/Users/Sakuya/.codex/worktrees/06df/FPGA-Music-project/hardware/review-manufacturing-20261019/REGIONAL-WORK-IN-PROGRESS.json',
                      scope='Listed context and existing native recovery ZIPs only, not full current hardware tree',
                      observation='Top cached construction pointer and lower-level state can differ; verify actual native hash before work',
                      manufacturing_release=False, physical_tests='UNMEASURED'),
                  freshness=dict(published_entry='Read actual remote entry_branch and compare entry fingerprints',
                      live_workspaces='Not continuously synchronized; this capture has an explicit cutoff',
                      frozen_tag='handoff/20261023-design-v2'),
                  reviewed_design_sources={})
    for name in ('project/DESIGN-CURRENT.md', 'project/versions/design-decision-20261023.json',
                 'docs/02-技术方案/38-代码盘点与实现基线-2026-10-09.md',
                 'docs/02-技术方案/39-最新设计构想与落地差距-2026-10-09.md',
                 'docs/02-技术方案/49-最终收敛设计总纲-2026-10-15.md'):
        design['reviewed_design_sources'][name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    write('project/design-state.json', design)
    handoff = read('project/handoff.json')
    handoff.update(updated_at=NOW, entry_tag='handoff/20261023-design-v2', design_entry='project/DESIGN-CURRENT.md',
                   design_state='project/design-state.json', current_scope='Latest published reviewed design plus captured WIP; excludes future live edits')
    handoff['previous_frozen_tag'] = 'handoff/20261022-management-v1'
    handoff['latest_observed_fpga'] = dict(manifest=design['current_inputs_manifest'], archive=capture['archive'],
                 archive_sha256=capture['archive_sha256'], captured_at=capture['captured_at'], validation_inherited=False)
    handoff['fpga_handoff']['current_role'] = 'Historical validated 100-input checkpoint; newer observed WIP is separate'
    handoff['rules']['physical_visualization_display'] = False
    handoff['rules']['right_harmonic_touchscreen'] = 'J10 retained'
    handoff['rules']['feature_reduction'] = 'Only direct human cancellation of physical visualization screen; no other management reduction'
    write('project/handoff.json', handoff)
    state = read('project/state.json')
    state['updated_at'] = NOW
    state['design_state'] = 'project/design-state.json'
    state['active_fpga_profile'] = 'fpga_latest_observed_20261023'
    state['profiles']['fpga_latest_observed_20261023'] = dict(role='development-candidate',
             archive=capture['archive'], manifest=design['current_inputs_manifest'], validation_inherited=False,
             status='已实现待验证；仅所列新增与修改，不表示全功能产品完成', product_accepted=False, programming_allowed=False)
    state['profiles']['m1_current_registered']['status'] = 'Historical validated checkpoint; not current mutable WIP'
    state['profiles']['hardware_wip']['current_context_manifest'] = design['current_inputs_manifest']
    state['profiles']['hardware_wip']['snapshot_role'] = 'Historical 20261022 recovery input; not current live hardware'
    write('project/state.json', state)
    dep = read('project/dependencies.json')
    dep['additional_archives'].append(dict(path=capture['archive'], sha256=capture['archive_sha256'], role='Observed WIP source/context and listed hardware recovery ZIPs; not product acceptance'))
    write('project/dependencies.json', dep)
    print('Registered design-20261023-v2; functional workspaces untouched')


if __name__ == '__main__':
    main()
