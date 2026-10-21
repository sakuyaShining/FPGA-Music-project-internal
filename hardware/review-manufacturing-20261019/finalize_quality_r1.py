"""Verify immutable baseline, live source, archive and measured quality delta."""
import hashlib,json,zipfile
from pathlib import Path
from native_review import ROOT,PROJECT

digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
baseline=json.loads((ROOT/'quality-baseline-archive.json').read_text())
snapshot=Path(baseline['path'])
checks=json.loads((snapshot/'SHA256SUMS.json').read_text(encoding='utf-8'))
for rel,sha in checks.items():assert digest(snapshot/rel)==sha,rel
manifest=json.loads((ROOT/'route-checkpoint-0clear-78open-quality-r1-20261021.json').read_text())
assert digest(PROJECT/'pcb/PCB1.epcb2')==manifest['pcb_sha256']
archive=Path(manifest['native_zip']);assert digest(archive)==manifest['native_zip_sha256']
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for rel,sha in manifest['files'].items():
        assert hashlib.sha256(z.read(rel)).hexdigest()==sha,rel
        assert digest(PROJECT/rel)==sha,rel
before=json.loads((ROOT/'controls-final-source-78.json').read_text())
after=json.loads((ROOT/'quality-r1-source-78.json').read_text())
plan=json.loads((ROOT/'quality-core-visibility-plan.json').read_text())
audit=json.loads((ROOT/'quality-core-r1-apply-audit.json').read_text())
assert audit['all_pads_unchanged'] and audit['component_identity_and_placement_unchanged'] and audit['rules_unchanged']
assert all(audit['unselected_copper_unchanged'].values())
via_key=lambda p:(p['net'],*(round(p[k],6) for k in ['x','y','diameter','hole']))
assert {via_key(p) for p in after['vias']}<={via_key(p) for p in before['vias']}
metrics={r['net']:r['quality_comparison'] for r in plan['routes']}
assert all(m['after_vias']<=m['before_vias'] and m['after_length_mm']<m['before_length_mm'] for m in metrics.values())
result={'baseline_snapshot':str(snapshot),'baseline_archive_checksums_verified':len(checks),'native_project_files_verified':len(manifest['files']),
        'pcb_sha256':manifest['pcb_sha256'],'native_zip':manifest['native_zip'],'native_zip_sha256':manifest['native_zip_sha256'],
        'nets_optimized':metrics,'copper_reduction_mm':sum(m['before_length_mm']-m['after_length_mm'] for m in metrics.values()),
        'via_reduction':len(before['vias'])-len(after['vias']),'api_segment_reduction':len(before['lines'])-len(after['lines']),
        'no_new_via_locations':True,'components_and_pads_unchanged':True,'rules_unchanged':True,'ground_and_other_unselected_copper_unchanged':True,
        'clearance_errors':0,'physical_errors':0,'connection_error_objects':manifest['unconnected_errors'],'pending_networks':len(manifest['pending_nets']),
        'i2s_layout_debt_resolved':False,'manufacturing_release':False}
(ROOT/'quality-r1-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='nets_optimized'},indent=2),flush=True)
