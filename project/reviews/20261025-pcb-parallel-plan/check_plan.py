"""Lint the unassigned PCB execution plan; this does not validate any PCB."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'project/pcb-parallel-20261025'
plan = json.loads((PACKAGE / 'plan.json').read_text(encoding='utf-8'))
assignments = json.loads((PACKAGE / 'assignments.json').read_text(encoding='utf-8'))
roles = {'M0', 'R1', 'R2', 'E3', 'V4', 'F5'}
assert set(plan['roles']) == set(assignments['roles']) == roles
assert plan['formal_board_writer'] == assignments['formal_board_writer'] == 'M0'
assert plan['pcb_validated'] is False
assert plan['max_heavy_concurrent_agents'] == 4
assert plan['source_commit'] == '7c344f34d7183d24bd53e2f8ceaf85a7b8f6cb2b'
assert plan['source_pcb_sha256'] == '951ce88a1a2fcc2d758f9a53222a400cbddd3bc5b689cc2a37c98b8303d9ca4d'
assert (ROOT / plan['source_manifest']).is_file()
owned = []
for role, spec in plan['roles'].items():
    assert (PACKAGE / spec['task_card']).is_file()
    assert spec['required_outputs']
    assert spec['reviewer'] != role
    assert assignments['roles'][role]['owner'] is None, 'Initial plan lint expects unassigned roles'
    for path in spec['exclusive_write_paths']:
        assert not path.startswith('/') and '..' not in path.split('/')
        for other_role, other_path in owned:
            assert not (path.startswith(other_path) or other_path.startswith(path)), (role, other_role)
        owned.append((role, path))
nets = [net for batch in plan['batches'].values() for net in batch]
expected = {'MUX_DISABLE', 'ADDR0', 'ADDR1', 'BUS_SCK', 'INPUT_LOAD_N', 'KEY_QH',
            'PRESET1', 'PRESET2', 'EDIT', 'ENC_A', 'ENC_B', 'ENC_PUSH'}
assert len(nets) == len(set(nets)) == 12 and set(nets) == expected
seen = set()
for gate in plan['gates']:
    assert gate['id'] not in seen
    assert set(gate['depends_on']) <= seen, 'Missing dependency or cycle'
    assert gate['status'] == 'NOT_RUN' and gate['evidence'] == []
    seen.add(gate['id'])
assert seen == {'G' + str(i) for i in range(7)}
links = 0
for document in PACKAGE.rglob('*.md'):
    for target in re.findall(r'\]\(([^)]+)\)', document.read_text(encoding='utf-8')):
        if '://' in target or target.startswith('#'):
            continue
        assert (document.parent / target.split('#')[0]).is_file(), (document, target)
        links += 1
template = json.loads((PACKAGE / 'templates/handoff.json').read_text(encoding='utf-8'))
assert template['is_template'] and template['verdict'] == 'NOT_RUN'
assert template['independent_review']['verdict'] == 'NOT_RUN'
assert template['native_metrics']['connection_errors'] is None
print(json.dumps({'kind': 'planning_consistency_only', 'result': 'PASS',
                  'roles': 6, 'exclusive_paths': len(owned), 'unique_nets': 12,
                  'gates': 7, 'local_links': links, 'pcb_verification': 'NOT_RUN',
                  'files': {str(p.relative_to(ROOT)).replace('\\', '/'):
                            hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted(PACKAGE.rglob('*')) if p.is_file()}},
                 ensure_ascii=False, indent=2))
