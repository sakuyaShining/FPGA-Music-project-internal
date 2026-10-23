"""One-time, bounded late-day review registration; never run to renew a date.

The assessments below follow actual inspection of the changed design notes and
hardware state. This performs no RTL/CAD validation or source promotion.
"""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools/scripts'))
import design_governance as g


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf8'))


def main():
    root = g.ROOT
    folder = root / 'project/reviews/20261023-team-handoff'
    if folder.exists():
        raise ValueError('Immutable review already exists')
    policy = g.read_json(root / 'project/governance.json')
    previous = policy['review_record']
    old = g.reviewed_producers(root, g.read_json(root / previous))
    producers = {p['id']: p for p in g.read_json(root / 'project/producers.json')['producers']}
    observation = g.observe(folder / 'observation.json')
    changes = {}
    for ident, state in observation['producers'].items():
        if state['status'] != 'OBSERVED' or state['omissions']:
            raise ValueError('Unstable/incomplete producer observation: ' + ident)
        delta = g.compare_files(old[ident]['files'], state['files'])
        changes[ident] = delta
        for name in delta['added'] + delta['modified']:
            if Path(name).suffix.lower() == '.zip':
                continue  # Exact identity observed; not a new recovery archive.
            raw = (Path(producers[ident]['root']) / g.relative(name)).read_bytes()
            if g.digest(raw) != state['files'][name]['sha256']:
                raise ValueError('Source changed during capture: ' + ident + '/' + name)
            dest = folder / 'evidence' / ident / g.relative(name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
    review = dict(
        schema=1, reviewed_at=observation['observed_at'],
        observer_thread='01a15f25-dfc1-7442-988a-322c7fc7911b',
        previous_review=previous, previous_review_sha256=g.digest((root / previous).read_bytes()),
        raw_observation=(folder / 'observation.json').relative_to(root).as_posix(),
        raw_observation_sha256=g.digest((folder / 'observation.json').read_bytes()),
        producer_ids=list(observation['producers']), changes_since_previous_review=changes,
        verdict='REVIEWED_WITH_DECLARED_WIP',
        assessment=dict(
            fpga='Per-slot velocity table candidate, table generator, note tool and design/procurement proposals added. Five RTL/table/test files changed. Raw evidence preserved, identity checked; no functional regression/PnR/programming performed by this review. Author-reported reduced-wrapper 12562 Logic/8265 CLS/15 BSRAM/10 DSP and +11.300ns setup do not budget the full product.',
            product='Full product top, four-layer behavior, device editing/save, J10 and 84-node integration remain unaccepted. A/B/C milestone scopes and derisk cuts are proposals, not authorized removal of full goals. Q1..Q6 human-choice assertions require their original direct evidence before adoption.',
            hardware='Observed construction e098c5db /47 connection errors/13 nets/227 components/616 vias; retained aaa37 baseline distinct. BUS_MOSI author-recorded closed; nine control nets unfinished. Three Bottom SMT components mean old single-side assembly outputs are stale. Offline U9/C9 relocation/clock/PDN candidates are not native acceptance. No CAD operations or fabrication release.',
            collaboration='Direct private GitHub collaboration requires repository access; offline source/task packages and returned patches do not. No invitations, external transmissions or new collaborator package produced. Exact active FPGA owner identity and branch remain unregistered.'),
        known_inconsistent_producer_documents=[
            'DECISIONS-20261023.md: RA8875 abandonment superseded by direct human D-010.',
            'AUX-SCREEN-PRODUCT-BOM-20261023.md: empty-PCB claim reads old four-strip prototype, not active carrier construction. Proposed pin remapping, reduced sense lanes, PCF8575/buttons and AUX-only scope are not authorized by this review; current hardware contract controls.',
            'LAYER4-RULES-DRAFT-20261023.md: two instrument banks described as strike/sustain, while EDIT-MODE-DESIGN describes atomic update buffering; resolve against actual RTL before implementation.',
            'Author-reported all-green checks, programmed build and GUI never-tested claims have not been bound to exact inputs or independently reconciled in this management review.'
        ],
        publication_gaps=['Latest full source recovery archive remains v2, before these live changes.',
                          'Neither active producer has a registered published source branch/commit.'],
        product_acceptance=False, new_rtl_tests=False, new_cad_operations=False)
    write(folder / 'review.json', review)
    new_review = (folder / 'review.json').relative_to(root).as_posix()
    for name in ['project/design-state.json', 'project/handoff.json', 'project/state.json']:
        data = g.read_json(root / name)
        if 'latest_observed_fpga' in data:
            data['latest_observed_fpga']['review_record'] = new_review
        if 'profiles' in data:
            data['profiles']['fpga_live_unpublished']['review_record'] = new_review
        data['updated_at'] = observation['observed_at']
        if 'reviewed_design_sources' in data:
            for path in data['reviewed_design_sources']:
                data['reviewed_design_sources'][path] = g.digest((root / path).read_bytes())
        write(root / name, data)
    policy.update(review_record=new_review, reviewed_at=review['reviewed_at'],
                  review_sha256=g.digest((folder / 'review.json').read_bytes()))
    policy['controlled_files'][previous] = g.digest((root / previous).read_bytes())
    policy['controlled_files']['project/COLLABORATING.md'] = g.digest((root / 'project/COLLABORATING.md').read_bytes())
    for path in folder.rglob('*'):
        if path.is_file() and path.name != 'review.json':
            policy['controlled_files'][path.relative_to(root).as_posix()] = g.digest(path.read_bytes())
    for name in policy['controlled_files']:
        policy['controlled_files'][name] = g.digest((root / name).read_bytes())
    write(root / 'project/governance.json', policy)
    print(json.dumps(dict(review=new_review, observed_at=observation['observed_at'], changes=changes)))


if __name__ == '__main__':
    main()
