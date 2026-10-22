"""Apply the reviewed four-net candidate after a fresh native capture and backup."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

sys.path.insert(0, 'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
import grid_route as grid
from native_review import ROOT, PROJECT, invoke

directory = ROOT/'offline-resume-20261020/audio-conservative075'
proposal_path = directory/'audio-route-proposal.json'
proposal = json.loads(proposal_path.read_text(encoding='utf-8'))
review = json.loads((directory/'audio-route-geometry-audit.json').read_text(encoding='utf-8'))
assert review['offline_geometry_pass'] and not review['violations']
assert review['proposal_sha256'] == hashlib.sha256(proposal_path.read_bytes()).hexdigest()
assert set(proposal['nets']) == {'I2S_BCK', 'I2S_DIN', 'I2S_LRCK', 'DAC_XSMT'}
board = PROJECT/'pcb/PCB1.epcb2'
assert hashlib.sha256(board.read_bytes()).hexdigest() == proposal['native_pcb_sha256']

canonical = lambda d: {k: sorted(d[k], key=lambda p: p['id']) for k in ['pads', 'lines', 'vias']}
source = grid.capture()
original = json.loads((ROOT/'grid-source-core-fanouts.json').read_text(encoding='utf-8'))
assert canonical(source) == canonical(original), 'Pads or API copper changed since geometry review'
source_path = ROOT/'resume-audio-api-source.json'
source_path.write_text(json.dumps(source, indent=2), encoding='utf-8')
identities_code = "return {components:(await eda.pcb_PrimitiveComponent.getAll()).map(c=>[c.getState_PrimitiveId(),c.getState_Designator(),c.getState_X(),c.getState_Y(),c.getState_Rotation()]).sort((a,b)=>a[0].localeCompare(b[0])),rules:(await eda.pcb_Drc.getCurrentRuleConfiguration()).config};"
before = invoke('resume-audio-before-identities', identities_code, timeout=60)
assert len(before['components']) == 230

backup = ROOT/'offline-resume-20261020'/('before-native-audio-'+str(time.time_ns())+'-CANDIDATE.zip')
with zipfile.ZipFile(backup, 'x', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(PROJECT.rglob('*')):
        if path.is_file() and 'review-exports' not in path.relative_to(PROJECT).parts:
            archive.write(path, path.relative_to(PROJECT))
print('BACKUP', backup, flush=True)

# The physical review used a superset containing API-omitted tiny native lines.
# Native identity checks must use this fresh API view; unrelated tiny lines are
# never selected for deletion, and the source-bound physical review is retained.
native_plan = {**proposal, 'source_file': str(source_path),
               'source_sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
               'geometry_source_file': proposal['source_file'],
               'geometry_source_sha256': proposal['source_sha256'],
               'independent_geometry_audit_sha256': hashlib.sha256(
                   (directory/'audio-route-geometry-audit.json').read_bytes()).hexdigest()}
plan_path = ROOT/'resume-native-audio-plan.json'
plan_path.write_text(json.dumps(native_plan, indent=2), encoding='utf-8')
subprocess.run([sys.executable, str(ROOT/'apply_grid_plan.py'), str(plan_path)], check=True)

after_source = grid.capture()
(ROOT/'resume-audio-applied-source.json').write_text(json.dumps(after_source, indent=2), encoding='utf-8')
after = invoke('resume-audio-after-identities', identities_code, timeout=60)
nets = set(proposal['nets'])
untouched = {}
for kind in ['lines', 'vias']:
    first = sorted([p for p in source[kind] if p['net'] not in nets], key=lambda p: p['id'])
    last = sorted([p for p in after_source[kind] if p['net'] not in nets], key=lambda p: p['id'])
    untouched[kind] = first == last
result = {'nets': proposal['nets'], 'backup': str(backup),
          'all_pads_unchanged': canonical(source)['pads'] == canonical(after_source)['pads'],
          'component_identity_and_placement_unchanged': before['components'] == after['components'],
          'rules_unchanged': before['rules'] == after['rules'],
          'unselected_copper_unchanged': untouched,
          'created_candidate_tracks': len(proposal['lines']), 'created_candidate_vias': len(proposal['vias']),
          'api_counts_after': {k: len(v) for k,v in after_source.items()},
          'pcb_sha256_after': hashlib.sha256(board.read_bytes()).hexdigest(),
          'native_imported': True, 'requires_ground_rebuild_and_fresh_drc': True,
          'manufacturing_release': False}
(ROOT/'resume-native-audio-audit.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2), flush=True)
assert result['all_pads_unchanged'] and result['component_identity_and_placement_unchanged']
assert result['rules_unchanged'] and all(untouched.values())
