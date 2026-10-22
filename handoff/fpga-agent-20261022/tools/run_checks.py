"""Run one suite with a fresh evidence directory, preserving all previous runs."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,re,runpy,sys,traceback
from verify import verify

P=Path(__file__).resolve().parents[1]
SUITES={'native':'check_native.py','pitch':'check_pitch.py','engine':'check_engine_compat.py',
        'joint':'check_joint.py','renderer':'check_renderer.py','scan':'check_scan_store.py',
        'delta':'check_delta.py','sensor':'check_sensor.py',
        'envelope':'check_envelope.py','phase_wrap':'check_phase_wrap.py'}
ap=argparse.ArgumentParser();ap.add_argument('--workspace',required=True);ap.add_argument('--suite',choices=SUITES,required=True)
ap.add_argument('--run-id',required=True);ap.add_argument('--preflight-only',action='store_true');a=ap.parse_args()
verify(P);W=Path(a.workspace).resolve();marker=json.loads((W/'HANDOFF-WORKSPACE.json').read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert marker['package_manifest_sha256']==sha(P/'MANIFEST.json'),'Workspace belongs to another package identity'
assert Path(marker['workspace']).resolve()==W
assert re.fullmatch(r'[A-Za-z0-9_-]+',a.run_id),'Invalid run id'
for rel,h in marker['protected_test_inputs'].items():
    assert sha(W/rel)==h,'Protected reference/test input changed: '+rel+'; add new tests under new names'
case=W/'evidence'/(a.run_id+'-'+a.suite);assert not case.exists(),'Never overwrite evidence; choose a new run id'
script=W/SUITES[a.suite];assert script.is_file()
sys.path.insert(0,str(W))
spec=importlib.util.spec_from_file_location('common',W/'common.py');common=importlib.util.module_from_spec(spec)
sys.modules['common']=common;spec.loader.exec_module(common)
for tool in (common.IV,common.VVP):assert Path(tool).is_file(),'Missing tool: '+tool
if a.preflight_only:
    print(json.dumps(dict(status='PASS preflight only; no simulation',script=str(script),evidence_would_be=str(case))));sys.exit(0)
case.mkdir(parents=True);common.E=case
inputs=common.sources()+list((W/'engine/src').glob('*.hex'))+list((W/'engine/src').glob('*.vh'))+[script,W/'common.py']
before={str(p):sha(p) for p in inputs};status='FAIL';error=None
os.chdir(W);sys.argv=[str(script)]
try:
    runpy.run_path(str(script),run_name='__main__')
    assert all(sha(Path(p))==h for p,h in before.items()),'DUT/checker changed during test'
    status='PASS scoped regression only'
except BaseException:
    error=traceback.format_exc();print(error,file=sys.stderr)
finally:
    receipt=dict(status=status,suite=a.suite,error=error,source_inputs=before,
        source_changed_from_bootstrap=[rel for rel,h in marker['rtl_source_identities'].items() if not (W/rel).is_file() or sha(W/rel)!=h],
        product_qualified=False,hardware_programmed=False)
    (case/'suite-run.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status=status,suite=a.suite,evidence=str(case)),ensure_ascii=False))
sys.exit(0 if status.startswith('PASS') else 1)
