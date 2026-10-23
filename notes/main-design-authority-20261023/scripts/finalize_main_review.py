"""One-time registration of the inspected main-authority review.

It records the actual observation time; it does not claim new RTL/CAD tests.
"""
from pathlib import Path
import json
import zipfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools/scripts'))
import design_governance as g


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def replace(path, before, after):
    raw = path.read_bytes()
    if before.encode('utf-8') not in raw:
        raise ValueError('Missing expected text: ' + str(path))
    path.write_bytes(raw.replace(before.encode('utf-8'), after.encode('utf-8')))


def main():
    root = g.ROOT
    folder = root / 'project/reviews/20261023-main-authority'
    if (folder/'review.json').exists():
        raise ValueError('Review already finalized; do not renew by rerunning')
    observation = g.read_json(folder/'observation.json')
    changes = g.read_json(folder/'changes-from-v2.json')
    evidence = folder/'evidence'
    # Preserve the old requirement as history, without editing the old report.
    (evidence/'historical-dual-screen.md').write_bytes((root/'docs/02-技术方案/87-Nano20K完整功能可行性与预算-2026-10-22.md').read_bytes())
    archive_manifest=g.read_json(root/'project/versions/latest-design-inputs-20261023.json')
    with zipfile.ZipFile(root/archive_manifest['archive']) as z:
        raw=z.read('hardware/single-touch/SCOPE-CHANGE.md')
        if g.digest(raw)!=archive_manifest['files']['hardware/single-touch/SCOPE-CHANGE.md']['sha256']:
            raise ValueError('Preserved scope evidence mismatch')
        (evidence/'single-touch-scope.md').write_bytes(raw)
    def cite(path, authority):
        return dict(path=path, sha256=g.digest((root/path).read_bytes()), authority=authority)
    base='docs/02-技术方案/49-最终收敛设计总纲-2026-10-15.md'
    ledger=dict(schema=1, rule='Accepted decisions persist until explicitly superseded with evidence; proposals do not change scope', decisions=[
        dict(id='D-001-CORE',status='accepted',statement='Tang Nano20K, 32 groups x16 partials shared across four target layers',
             facts=dict(platform='Tang Nano20K',groups=32,partials_per_group=16,layer_target=4),
             evidence=cite(base,'Existing user-confirmed product definition in 49; no new architecture approval inferred')),
        dict(id='D-002-LEFT',status='accepted',statement='Two rows of per-note pitch strips plus independent octave selector; per-finger expression; 25/26 endpoint details remain open',
             evidence=cite(base,'Existing user-confirmed panel direction in 49')),
        dict(id='D-003-RIGHT',status='accepted',statement='Whole-chord continuous harmonic modification, release holds state, RESET restores smoothly; precise SKU/CTP and defaults remain open',
             evidence=cite(base,'Existing later interaction decisions summarized in 49; no return-to-centre rollback')),
        dict(id='D-004-DUAL-SCREEN',status='superseded',statement='Historical requirement to preserve both physical displays',
             evidence=cite('project/reviews/20261023-main-authority/evidence/historical-dual-screen.md','Historical 87 requirement, superseded only in the physical visualization display scope')),
        dict(id='D-005-J10-ONLY',status='accepted',supersedes='D-004-DUAL-SCREEN',
             statement='Cancel physical music visualization display J11; retain harmonic construction touchscreen J10',
             facts=dict(physical_music_visualization_display=False,right_harmonic_touchscreen='J10 retained'),
             evidence=cite('project/versions/design-decision-20261023.json','Direct human message, thread 01a15ee5-fa24-7501-8475-ad28a0f08939 / turn 01a1640c-8a1b-7771-bd4c-f3e81fa500f3')),
        dict(id='D-006-SENSOR-CAPACITY',status='accepted',statement='Preserve 84 sensor capability in current hardware scope; not measured touch/pressure capability',
             facts=dict(sensor_capacity=84), evidence=cite('project/reviews/20261023-main-authority/evidence/single-touch-scope.md','Recorded retained hardware scope accompanying the human single-screen change')),
        dict(id='D-007-SAVE-RECORD',status='accepted',statement='Retain custom instrument/device editing/nonvolatile save and actual audio recording/playback plus live performance; detailed workflow remains open',
             evidence=cite(base,'Existing confirmed targets in 49; no management feature reduction')),
        dict(id='P-008-DECAY2-GLOBAL',status='proposed',statement='Candidate uses global second-decay breakpoint/slope, default disabled; implementation choice and author tests are not a new accepted product rule',
             evidence=cite('project/reviews/20261023-main-authority/evidence/fpga/DECAY2-20261023.md','Independent FPGA author implementation note; no direct human acceptance located in this review'))
    ])
    write(root/'project/decisions.json',ledger)
    review=dict(schema=1, reviewed_at=observation['observed_at'], observer_thread='01a15f25-dfc1-7442-988a-322c7fc7911b',
                baseline_main_commit='a056ec44a819b9acfaab295063764905e3393711',
                scope='Declared FPGA input/context directories and listed hardware entries/recovery ZIPs; not every file or unknown session',
                verdict='REVIEWED_WITH_DECLARED_WIP', raw_observation='project/reviews/20261023-main-authority/observation.json',
                raw_observation_sha256=g.digest((folder/'observation.json').read_bytes()),
                evidence=changes['evidence'], producers=observation['producers'],
                assessment=dict(fpga='New decay2 candidate observed in source and design note; author claims 7/7 tests. No new functional validation inherited or performed here; new source not promoted into v2 archive.',
                  hardware='Observed construction-state 40c8175b /54 connection errors/14 nets/602 vias and PRESET0 progress; 9 control nets pending. Top narrative/cache can be older. No CAD/DRC/SI/physical verification run here.',
                  decisions='No new confirmed product-scope change found in the inspected recent hardware messages/documents beyond recorded J11 cancellation; decay2 global design remains a proposal.',
                  owner_gaps='FPGA session identity still unregistered. Both active producer branches are unpublished. Host is dormant, requiring review before activation.'),
                product_acceptance=False, new_rtl_tests=False, new_cad_operations=False,
                publication_gaps=['New active FPGA changes are not a new recoverable source archive', 'Active hardware copy is not promoted over retained baseline or released for fabrication'])
    write(folder/'review.json',review)
    design=g.read_json(root/'project/design-state.json')
    design.update(design_version='design-20261023-v3',entry_branch='main', updated_at=observation['observed_at'],
                  governance='project/governance.json', decision_ledger='project/decisions.json',producer_registry='project/producers.json',
                  current_inputs_manifest_role='Historical v2 recoverable candidate, not current live source')
    design['latest_observed_fpga']=dict(review_record='project/reviews/20261023-main-authority/review.json', producer='fpga',
                  status='UNPUBLISHED_LIVE_WIP',validation_inherited=False,complete_product_top=False)
    design['freshness']=dict(authority='actual remote main', review_policy='project/governance.json',
                  live_workspaces='Read-only live check required to assert current observation; otherwise NOT_CHECKED',
                  historical_tags=['handoff/20261022-management-v1','handoff/20261023-design-v2'])
    for name in design['reviewed_design_sources']:
        design['reviewed_design_sources'][name]=g.digest((root/name).read_bytes())
    write(root/'project/design-state.json',design)
    handoff=g.read_json(root/'project/handoff.json')
    handoff.update(entry_branch='main',entry_tag=None,updated_at=observation['observed_at'],governance='project/governance.json',
                   entry_commit_resolution='Query actual private remote main and compare controlled entry content; dated branch is compatibility only',
                   main_status='PR #1 merged. Subsequent management changes require main integration; actual remote main is authoritative.',
                   current_scope='Reviewed decisions, explicit recovery checkpoints and observed unpublished WIP; expiry and live visibility are separate checks')
    handoff['recoverable_fpga_v2']=handoff['latest_observed_fpga']
    handoff['latest_observed_fpga']=dict(review_record='project/reviews/20261023-main-authority/review.json',producer='fpga',validation_inherited=False)
    handoff['historical_tags']=['handoff/20261022-management-v1','handoff/20261023-design-v2']
    write(root/'project/handoff.json',handoff)
    state=g.read_json(root/'project/state.json')
    state['active_fpga_profile']='fpga_live_unpublished'
    state['profiles']['fpga_latest_observed_20261023']['status']='Historical v2 recovery archive; later live changes recorded separately'
    state['profiles']['fpga_live_unpublished']=dict(role='development-wip',review_record='project/reviews/20261023-main-authority/review.json',
                       producer_registry='project/producers.json',product_accepted=False,validation_inherited=False,programming_allowed=False)
    state['governance']='project/governance.json'
    write(root/'project/state.json',state)
    policy=dict(schema=1,authority=dict(remote=g.REMOTE,branch='main'),decision_ledger='project/decisions.json',
                producer_registry='project/producers.json', review_record='project/reviews/20261023-main-authority/review.json',
                review_sha256=g.digest((folder/'review.json').read_bytes()),reviewed_at=review['reviewed_at'],review_max_hours=24,
                required_scope_facts=['platform','groups','partials_per_group','layer_target','physical_music_visualization_display','right_harmonic_touchscreen','sensor_capacity'],
                source_visibility='GitHub cannot inspect local roots; six-hour producer observations expire. No perpetual freshness inferred.',controlled_files={})
    controlled=['project/decisions.json','project/producers.json','project/MAINTAINING-MAIN.md','project/DESIGN-CURRENT.md']
    controlled += [p.relative_to(root).as_posix() for p in folder.rglob('*') if p.is_file() and p.name!='review.json']
    for name in controlled:
        policy['controlled_files'][name]=g.digest((root/name).read_bytes())
    write(root/'project/governance.json',policy)
    print(json.dumps(dict(reviewed_at=review['reviewed_at'],decisions=len(ledger['decisions']),controlled_files=len(controlled),new_product_acceptance=False)))


if __name__=='__main__':
    main()
