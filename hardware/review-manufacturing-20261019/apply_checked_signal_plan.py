"""Apply a complete-net signal plan only after source and geometry checks."""
import argparse,hashlib,json,subprocess,sys,time,zipfile
from pathlib import Path
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
import grid_route as grid
from native_review import ROOT,PROJECT,invoke

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('plan');parser.add_argument('--stage',required=True)
options=parser.parse_args()
path=Path(options.plan)
if not path.is_absolute():path=ROOT/path
plan=json.loads(path.read_text(encoding='utf-8'))
assert plan['nets'] and all(r['independent_geometry_pass'] and r['real_pad_continuity_pass'] for r in plan['routes'])
if any('quality_comparison' in r for r in plan['routes']):assert plan.get('batch_final_geometry_pass'),'Quality candidate lacks final combined geometry audit'
assert not any(plan.get('ground_removals',{}).values()),'Use the scoped ground-exchange applier for this plan'
assert all(p['width']>=5.9999 for p in plan['lines'])
assert set(plan['nets'])=={r['net'] for r in plan['routes']}
board=PROJECT/'pcb/PCB1.epcb2'
assert hashlib.sha256(board.read_bytes()).hexdigest()==plan['native_pcb_sha256']
source_path=Path(plan['source_file']);source=json.loads(source_path.read_text(encoding='utf-8'))
assert hashlib.sha256(source_path.read_bytes()).hexdigest()==plan['source_sha256']
canonical=lambda d:{k:sorted(d[k],key=lambda p:p['id']) for k in ['pads','lines','vias']}
assert canonical(grid.capture())==canonical(source),'Native copper/pads changed during planning'
identity_code="return {components:(await eda.pcb_PrimitiveComponent.getAll()).map(c=>[c.getState_PrimitiveId(),c.getState_Designator(),c.getState_X(),c.getState_Y(),c.getState_Rotation()]).sort((a,b)=>a[0].localeCompare(b[0])),rules:(await eda.pcb_Drc.getCurrentRuleConfiguration()).config};"
before=invoke(options.stage+'-before-identity',identity_code,timeout=60)
assert len(before['components'])==230
backup=ROOT/'offline-resume-20261020'/('before-'+options.stage+'-'+str(time.time_ns())+'-CANDIDATE.zip')
with zipfile.ZipFile(backup,'x',zipfile.ZIP_DEFLATED) as archive:
    for p in sorted(PROJECT.rglob('*')):
        if p.is_file() and 'review-exports' not in p.relative_to(PROJECT).parts:
            archive.write(p,p.relative_to(PROJECT))
print('BACKUP',str(backup),flush=True)
subprocess.run([sys.executable,str(ROOT/'apply_grid_plan.py'),str(path)],check=True)
after=grid.capture();identity=invoke(options.stage+'-after-identity',identity_code,timeout=60)
(ROOT/(options.stage+'-applied-source.json')).write_text(json.dumps(after,indent=2),encoding='utf-8')
selected=set(plan['nets'])
untouched={kind:sorted([p for p in source[kind] if p['net'] not in selected],key=lambda p:p['id'])==sorted([p for p in after[kind] if p['net'] not in selected],key=lambda p:p['id']) for kind in ['lines','vias']}
result={'nets':plan['nets'],'plan_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'backup':str(backup),
        'all_pads_unchanged':canonical(source)['pads']==canonical(after)['pads'],
        'component_identity_and_placement_unchanged':before['components']==identity['components'],
        'rules_unchanged':before['rules']==identity['rules'],'unselected_copper_unchanged':untouched,
        'api_counts_after':{k:len(v) for k,v in after.items()},'requires_ground_rebuild_and_native_drc':True,
        'manufacturing_release':False}
(ROOT/(options.stage+'-apply-audit.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2),flush=True)
assert result['all_pads_unchanged'] and result['component_identity_and_placement_unchanged']
assert result['rules_unchanged'] and all(untouched.values())
