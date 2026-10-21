"""Bind completed evidence to unchanged native files and produce a checksum index."""
import hashlib,json,py_compile,shutil
from pathlib import Path
from spice_runner import ROOT,ENGINE,VENDOR,COMPAT,digest

manifest=json.loads((ROOT.parent/'route-checkpoint-0clear-78open-quality-r1-20261021.json').read_text(encoding='utf-8'))
project=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019')
native={name:digest(project/name)==sha for name,sha in manifest['files'].items()}
assert len(native)==19 and all(native.values())
summary=json.loads((ROOT/'spice-validation-summary.json').read_text(encoding='utf-8'))
dynamic=json.loads((ROOT/'dynamic-model-checks.json').read_text(encoding='utf-8'))
assert summary['pcb_sha256']==manifest['pcb_sha256'] and summary['pcb_unchanged']
assert (summary['i2c_executed_cases'],summary['power_executed_cases'])==(16,32)
assert not summary['manufacturing_release'] and not dynamic['manufacturing_release']
assert dynamic['datasheet_timing_sanity']['basic_timing_within_3ms']
assert dynamic['refined_peak_agreement_within_2_percent']
accepted=[m['case'] for m in summary['i2c_results']+summary['power_results']]
accepted+=['gates_original','gates_compatible','cal_disabled','cal_enabled','cal_uvlo','cal_current_limit',
           'datasheet_timing','collapse_refine_100ns','collapse_refine_50ns']
for name in accepted:
    folder=ROOT/'cases'/name
    p=json.loads((folder/'process.json').read_text(encoding='utf-8'))
    assert p['returncode']==0 and p['engine_sha256']==digest(ENGINE)
    assert p['circuit_sha256']==digest(folder/'circuit.cir')
assert len(accepted)==57
for script in ROOT.glob('*.py'):py_compile.compile(str(script),doraise=True)
provenance=Path('D:/FPGA-Project/codex-tools/ngspice-condaforge-41/download-source.json')
shutil.copy2(provenance,ROOT/'ngspice-download-source.json')
datasheet=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2/sources/TI-TPS2553.pdf')
evidence={'native_files_unchanged':native,'pcb_sha256':manifest['pcb_sha256'],
          'matrix_cases_complete':48,'additional_completed_process_cases':9,
          'expected_rejected_semantic_negative_control':'gates_original',
          'incomplete_attempt_excluded':'collapse_refine_20ns (90s timeout)',
          'python_sources_compile':True,'engine_sha256':digest(ENGINE),
          'original_model_sha256':digest(VENDOR),'syntax_adapter_sha256':digest(COMPAT),
          'datasheet':{'file':str(datasheet),'sha256':digest(datasheet),'identity':'SLVS841F, August 2016'},
          'manufacturing_release':False}
(ROOT/'final-verification.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
index={p.relative_to(ROOT).as_posix():digest(p) for p in sorted(ROOT.rglob('*'))
       if p.is_file() and '__pycache__' not in p.parts and p.name!='evidence-sha256.json'}
(ROOT/'evidence-sha256.json').write_text(json.dumps(index,indent=2),encoding='utf-8')
print(f'Verified 19 unchanged native files, 48 matrix + 9 additional completed process cases, {len(index)} indexed evidence files; manufacturing release FALSE.',flush=True)
