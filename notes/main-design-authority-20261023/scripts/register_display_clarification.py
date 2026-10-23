"""Register a newly observed document and the direct human clarification."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools/scripts'))
import design_governance as g


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))


def main():
    root=g.ROOT
    folder=root/'project/reviews/20261023-display-clarification'
    if (folder/'review.json').exists():raise ValueError('Refuse to overwrite an existing reviewed record')
    observed=g.read_json(folder/'observation.json')
    if any(p['status']!='OBSERVED' for p in observed['producers'].values()):raise ValueError('Unavailable/unstable source')
    source=Path(g.read_json(root/'project/producers.json')['producers'][0]['root'])/'DECISIONS-20261023.md'
    data=source.read_bytes()
    if g.digest(data)!=observed['producers']['fpga']['files']['DECISIONS-20261023.md']['sha256']:
        raise ValueError('Decision document changed after observation')
    (folder/'evidence/DECISIONS-20261023.md').write_bytes(data)
    def cite(path, authority):
        return dict(path=path,sha256=g.digest((root/path).read_bytes()),authority=authority)
    ledger=g.read_json(root/'project/decisions.json')
    ledger['decisions'].extend([
        dict(id='P-009-EXTERNAL-RA8875-CANCEL',status='superseded',statement='External FPGA document interpreted the old statement as RA8875 cancellation',
             evidence=cite('project/reviews/20261023-display-clarification/evidence/DECISIONS-20261023.md','Independent session author record; disputed interpretation, not accepted here')),
        dict(id='D-010-J10-ROUTE-CLARIFIED',status='accepted',supersedes='P-009-EXTERNAL-RA8875-CANCEL',
             statement='Cancel independent visualization screen; retain J10 touchscreen and existing controller route. RA8875 remains a candidate, exact module qualification pending.',
             facts=dict(right_display_controller_route='Existing J10 / RA8875 candidate retained'),
             evidence=cite('project/reviews/20261023-display-clarification/evidence/current-user-confirmation.json','Direct human reply to the explicit controller-route ambiguity in this conversation'))
    ])
    write(root/'project/decisions.json',ledger)
    policy=g.read_json(root/'project/governance.json')
    old=g.read_json(root/policy['review_record'])
    changes={ident:g.compare_files(old['producers'][ident]['files'],obs['files']) for ident,obs in observed['producers'].items()}
    review=dict(schema=1,reviewed_at=observed['observed_at'],observer_thread='01a15f25-dfc1-7442-988a-322c7fc7911b',
                previous_review=policy['review_record'],previous_review_sha256=policy['review_sha256'],
                raw_observation='project/reviews/20261023-display-clarification/observation.json',
                raw_observation_sha256=g.digest((folder/'observation.json').read_bytes()),producers=observed['producers'],
                changes_since_previous_review=changes,verdict='REVIEWED_WITH_DECLARED_WIP',
                assessment=dict(design='New external DECISIONS document detected automatically. Human explicitly confirmed retain J10 and existing controller route; external RA8875-abandonment interpretation is superseded.',
                  layering='External note says layering rules need serious design; this agrees with existing four-layer target and unresolved switching/tail/stealing rules, not full implementation or a reduced target.',
                  schedule='External document estimates minimal demo/full-product schedules. These are author proposals/estimates, not human-approved scope reduction or completion evidence.',
                  source='Compare exact changes list; no current RTL/CAD tests rerun or source archive promoted.'),
                known_inconsistent_producer_documents=['fpga/DECISIONS-20261023.md: RA8875 cancellation interpretation superseded by D-010; original owned document left unchanged'],
                product_acceptance=False,new_rtl_tests=False,new_cad_operations=False)
    write(folder/'review.json',review)
    design=g.read_json(root/'project/design-state.json')
    design['scope']['right_display_controller_route']='Existing J10 / RA8875 candidate retained'
    design['latest_observed_fpga']['review_record']='project/reviews/20261023-display-clarification/review.json'
    design['updated_at']=observed['observed_at']
    for name in design['reviewed_design_sources']:design['reviewed_design_sources'][name]=g.digest((root/name).read_bytes())
    write(root/'project/design-state.json',design)
    handoff=g.read_json(root/'project/handoff.json')
    handoff['latest_observed_fpga']['review_record']='project/reviews/20261023-display-clarification/review.json'
    handoff['updated_at']=observed['observed_at']
    write(root/'project/handoff.json',handoff)
    state=g.read_json(root/'project/state.json')
    state['profiles']['fpga_live_unpublished']['review_record']='project/reviews/20261023-display-clarification/review.json'
    write(root/'project/state.json',state)
    policy.update(review_record='project/reviews/20261023-display-clarification/review.json',
                  review_sha256=g.digest((folder/'review.json').read_bytes()),reviewed_at=review['reviewed_at'])
    policy['required_scope_facts'].append('right_display_controller_route')
    # Old reviewed evidence stays controlled; current review supersedes its scope.
    for p in (root/'project/reviews').rglob('*'):
        if p.is_file() and p != folder/'review.json':policy['controlled_files'][p.relative_to(root).as_posix()]=g.digest(p.read_bytes())
    for name in ('project/decisions.json','project/DESIGN-CURRENT.md'):
        policy['controlled_files'][name]=g.digest((root/name).read_bytes())
    write(root/'project/governance.json',policy)
    print(json.dumps(dict(reviewed_at=review['reviewed_at'],changes=changes,confirmed_decision='D-010-J10-ROUTE-CLARIFIED'),indent=2))


if __name__=='__main__':main()
